#!/usr/bin/env bash

set -u
set -o pipefail

SCRIPT_NAME="$(basename "$0")"
FAILURES=0

usage() {
  cat <<EOF
Usage: $SCRIPT_NAME [options]

Read deployment context from terraform.tfvars and run read-only Azure smoke tests.

Options:
  --tfvars PATH             Terraform variables file (default: ./terraform.tfvars)
  --resource-group NAME     Override the derived resource group name
  --foundry-account NAME    Override the derived Foundry account name
  --foundry-project NAME    Override foundry_project_name from terraform.tfvars
  --mini-model NAME         Override the mini model deployment selected from terraform.tfvars
  -h, --help                Show this help

The overrides support validating an existing deployment whose resource names do
not follow this Terraform root's naming convention. Tenant, subscription,
location, and model configuration still come from terraform.tfvars.
EOF
}

status() {
  local result="$1"
  local resource="$2"
  local detail="$3"
  printf '%-4s | %-28s | %s\n' "$result" "$resource" "$detail"
}

pass() {
  status "PASS" "$1" "$2"
}

fail() {
  status "FAIL" "$1" "$2"
  FAILURES=$((FAILURES + 1))
}

die() {
  fail "$1" "$2"
  exit 1
}

read_tfvar_string() {
  local key="$1"
  awk -v key="$key" '
    $0 ~ "^[[:space:]]*" key "[[:space:]]*=" {
      value = $0
      sub(/^[^=]*=[[:space:]]*/, "", value)
      sub(/[[:space:]]*#.*/, "", value)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
      if (value ~ /^".*"$/) {
        sub(/^"/, "", value)
        sub(/"$/, "", value)
        print value
        exit
      }
    }
  ' "$TFVARS_PATH"
}

read_model_deployment() {
  local requested_key="$1"
  awk -v requested_key="$requested_key" '
    function brace_delta(line, copy, opens, closes) {
      copy = line
      opens = gsub(/{/, "{", copy)
      copy = line
      closes = gsub(/}/, "}", copy)
      return opens - closes
    }

    /^[[:space:]]*model_deployments[[:space:]]*=[[:space:]]*{/ {
      in_models = 1
      models_depth = brace_delta($0)
      next
    }

    in_models {
      if (!in_deployment &&
          $0 ~ "^[[:space:]]*" requested_key "[[:space:]]*=[[:space:]]*{") {
        in_deployment = 1
        deployment_depth = brace_delta($0)
        next
      }

      if (in_deployment) {
        if ($0 ~ /^[[:space:]]*deployment_name[[:space:]]*=/) {
          value = $0
          sub(/^[^=]*=[[:space:]]*/, "", value)
          sub(/[[:space:]]*#.*/, "", value)
          gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
          if (value ~ /^".*"$/) {
            sub(/^"/, "", value)
            sub(/"$/, "", value)
            print value
            exit
          }
        }
        deployment_depth += brace_delta($0)
        if (deployment_depth <= 0) {
          in_deployment = 0
        }
      }

      models_depth += brace_delta($0)
      if (models_depth <= 0) {
        in_models = 0
      }
    }
  ' "$TFVARS_PATH"
}

read_first_mini_deployment() {
  awk '
    /^[[:space:]]*deployment_name[[:space:]]*=/ &&
    tolower($0) ~ /mini/ {
      value = $0
      sub(/^[^=]*=[[:space:]]*/, "", value)
      sub(/[[:space:]]*#.*/, "", value)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
      if (value ~ /^".*"$/) {
        sub(/^"/, "", value)
        sub(/"$/, "", value)
        print value
        exit
      }
    }
  ' "$TFVARS_PATH"
}

az_json() {
  az "$@" --only-show-errors --output json 2>/dev/null
}

TFVARS_PATH="./terraform.tfvars"
RESOURCE_GROUP_OVERRIDE=""
FOUNDRY_ACCOUNT_OVERRIDE=""
FOUNDRY_PROJECT_OVERRIDE=""
MINI_MODEL_OVERRIDE=""

while (($# > 0)); do
  case "$1" in
    --tfvars)
      (($# >= 2)) || { usage >&2; exit 2; }
      TFVARS_PATH="$2"
      shift 2
      ;;
    --resource-group)
      (($# >= 2)) || { usage >&2; exit 2; }
      RESOURCE_GROUP_OVERRIDE="$2"
      shift 2
      ;;
    --foundry-account)
      (($# >= 2)) || { usage >&2; exit 2; }
      FOUNDRY_ACCOUNT_OVERRIDE="$2"
      shift 2
      ;;
    --foundry-project)
      (($# >= 2)) || { usage >&2; exit 2; }
      FOUNDRY_PROJECT_OVERRIDE="$2"
      shift 2
      ;;
    --mini-model)
      (($# >= 2)) || { usage >&2; exit 2; }
      MINI_MODEL_OVERRIDE="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown option: %s\n\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

command -v az >/dev/null 2>&1 || die "Azure CLI" "az was not found on PATH"
[[ -f "$TFVARS_PATH" ]] || die "Terraform variables" "file not found: $TFVARS_PATH"

SUBSCRIPTION_ID="$(read_tfvar_string subscription_id)"
TENANT_ID="$(read_tfvar_string tenant_id)"
LOCATION="$(read_tfvar_string location)"
NAME_PREFIX="$(read_tfvar_string name_prefix)"
RESOURCE_SUFFIX="$(read_tfvar_string resource_suffix)"
FOUNDRY_PROJECT_NAME="$(read_tfvar_string foundry_project_name)"
CHAT_MODEL_KEY="$(read_tfvar_string chat_model_deployment_key)"
VALIDATION_RESOURCE_GROUP_NAME="$(read_tfvar_string validation_resource_group_name)"
VALIDATION_FOUNDRY_ACCOUNT_NAME="$(read_tfvar_string validation_foundry_account_name)"

[[ -n "$SUBSCRIPTION_ID" ]] || die "Terraform variables" "subscription_id is missing"
[[ -n "$TENANT_ID" ]] || die "Terraform variables" "tenant_id is missing"
[[ -n "$LOCATION" ]] || die "Terraform variables" "location is missing"

if [[ -z "$RESOURCE_GROUP_OVERRIDE" || -z "$FOUNDRY_ACCOUNT_OVERRIDE" ]]; then
  [[ -n "$NAME_PREFIX" ]] || die "Terraform variables" "name_prefix is missing"
  [[ -n "$RESOURCE_SUFFIX" ]] || die "Terraform variables" "resource_suffix is missing"
fi

[[ -n "$FOUNDRY_PROJECT_NAME" ]] || FOUNDRY_PROJECT_NAME="marketplace"
[[ -n "$CHAT_MODEL_KEY" ]] || CHAT_MODEL_KEY="gpt_5_4_mini"

WORKLOAD_NAME="${NAME_PREFIX}-${RESOURCE_SUFFIX}"
RESOURCE_GROUP_NAME="${RESOURCE_GROUP_OVERRIDE:-${VALIDATION_RESOURCE_GROUP_NAME:-rg-${WORKLOAD_NAME}}}"
FOUNDRY_ACCOUNT_NAME="${FOUNDRY_ACCOUNT_OVERRIDE:-${VALIDATION_FOUNDRY_ACCOUNT_NAME:-ai-${WORKLOAD_NAME}}}"
FOUNDRY_PROJECT_NAME="${FOUNDRY_PROJECT_OVERRIDE:-$FOUNDRY_PROJECT_NAME}"
MINI_MODEL_NAME="${MINI_MODEL_OVERRIDE:-$(read_first_mini_deployment)}"
if [[ -z "$MINI_MODEL_NAME" ]]; then
  MINI_MODEL_NAME="$(read_model_deployment "$CHAT_MODEL_KEY")"
fi

[[ -n "$MINI_MODEL_NAME" ]] || die "Terraform variables" \
  "could not resolve deployment_name for chat_model_deployment_key '$CHAT_MODEL_KEY'"

printf '%-4s | %-28s | %s\n' "STAT" "TESTED RESOURCE" "DETAIL"
printf '%-4s-+-%-28s-+-%s\n' "----" "----------------------------" "----------------------------------------"

if ! az account show --only-show-errors >/dev/null 2>&1; then
  printf 'No reusable Azure CLI credentials were found; starting device-code login.\n' >&2
  az login --tenant "$TENANT_ID" --use-device-code --only-show-errors >/dev/null ||
    die "Azure CLI context" "device-code login failed"
fi

if ! az account set --subscription "$SUBSCRIPTION_ID" --only-show-errors >/dev/null 2>&1; then
  printf 'The cached credentials cannot access the target subscription; starting device-code login.\n' >&2
  az login --tenant "$TENANT_ID" --use-device-code --only-show-errors >/dev/null ||
    die "Azure CLI context" "device-code login failed"
  az account set --subscription "$SUBSCRIPTION_ID" --only-show-errors >/dev/null ||
    die "Azure CLI context" "could not select the target subscription"
fi

if ! az account get-access-token \
  --subscription "$SUBSCRIPTION_ID" \
  --resource "https://management.azure.com" \
  --only-show-errors >/dev/null 2>&1; then
  printf 'The cached Azure CLI credentials are expired; starting device-code login.\n' >&2
  az login --tenant "$TENANT_ID" --use-device-code --only-show-errors >/dev/null ||
    die "Azure CLI context" "device-code login failed"
  az account set --subscription "$SUBSCRIPTION_ID" --only-show-errors >/dev/null ||
    die "Azure CLI context" "could not select the target subscription"
fi

az_json account show >/dev/null ||
  die "Azure CLI context" "could not read the active Azure account"
ACTIVE_SUBSCRIPTION_ID="$(az account show --query id --output tsv --only-show-errors 2>/dev/null)"
ACTIVE_TENANT_ID="$(az account show --query tenantId --output tsv --only-show-errors 2>/dev/null)"
ACTIVE_SUBSCRIPTION_NAME="$(az account show --query name --output tsv --only-show-errors 2>/dev/null)"

if [[ "${ACTIVE_SUBSCRIPTION_ID,,}" == "${SUBSCRIPTION_ID,,}" &&
      "${ACTIVE_TENANT_ID,,}" == "${TENANT_ID,,}" ]]; then
  pass "Azure CLI context" "$ACTIVE_SUBSCRIPTION_NAME"
else
  die "Azure CLI context" "active tenant or subscription does not match terraform.tfvars"
fi

if az_json group show --name "$RESOURCE_GROUP_NAME" >/dev/null; then
  RESOURCE_GROUP_LOCATION="$(az group show --name "$RESOURCE_GROUP_NAME" \
    --query location --output tsv --only-show-errors 2>/dev/null)"
  RESOURCE_GROUP_STATE="$(az group show --name "$RESOURCE_GROUP_NAME" \
    --query properties.provisioningState --output tsv --only-show-errors 2>/dev/null)"
  if [[ "${RESOURCE_GROUP_LOCATION,,}" == "${LOCATION,,}" &&
        "$RESOURCE_GROUP_STATE" == "Succeeded" ]]; then
    pass "Resource group" "$RESOURCE_GROUP_NAME ($RESOURCE_GROUP_LOCATION, $RESOURCE_GROUP_STATE)"
  else
    fail "Resource group" \
      "$RESOURCE_GROUP_NAME (location=$RESOURCE_GROUP_LOCATION, state=${RESOURCE_GROUP_STATE:-unknown})"
  fi
else
  fail "Resource group" "$RESOURCE_GROUP_NAME was not accessible"
fi

if az_json cognitiveservices account show \
  --resource-group "$RESOURCE_GROUP_NAME" \
  --name "$FOUNDRY_ACCOUNT_NAME" >/dev/null; then
  FOUNDRY_ACCOUNT_STATE="$(az cognitiveservices account show \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --name "$FOUNDRY_ACCOUNT_NAME" \
    --query properties.provisioningState --output tsv --only-show-errors 2>/dev/null)"
  if [[ "$FOUNDRY_ACCOUNT_STATE" == "Succeeded" ]]; then
    pass "Microsoft Foundry account" "$FOUNDRY_ACCOUNT_NAME ($FOUNDRY_ACCOUNT_STATE)"
  else
    fail "Microsoft Foundry account" \
      "$FOUNDRY_ACCOUNT_NAME (state=${FOUNDRY_ACCOUNT_STATE:-unknown})"
  fi
else
  fail "Microsoft Foundry account" "$FOUNDRY_ACCOUNT_NAME was not accessible"
fi

FOUNDRY_ACCOUNT_ID="/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP_NAME}/providers/Microsoft.CognitiveServices/accounts/${FOUNDRY_ACCOUNT_NAME}"
FOUNDRY_PROJECT_ID="${FOUNDRY_ACCOUNT_ID}/projects/${FOUNDRY_PROJECT_NAME}"
if az rest \
  --method get \
  --url "https://management.azure.com${FOUNDRY_PROJECT_ID}?api-version=2025-06-01" \
  --only-show-errors \
  --output none 2>/dev/null; then
  FOUNDRY_PROJECT_STATE="$(az rest \
    --method get \
    --url "https://management.azure.com${FOUNDRY_PROJECT_ID}?api-version=2025-06-01" \
    --query properties.provisioningState \
    --output tsv \
    --only-show-errors 2>/dev/null)"
  if [[ "$FOUNDRY_PROJECT_STATE" == "Succeeded" ]]; then
    pass "Microsoft Foundry project" "$FOUNDRY_PROJECT_NAME ($FOUNDRY_PROJECT_STATE)"
  else
    fail "Microsoft Foundry project" \
      "$FOUNDRY_PROJECT_NAME (state=${FOUNDRY_PROJECT_STATE:-unknown})"
  fi
else
  fail "Microsoft Foundry project" "$FOUNDRY_PROJECT_NAME was not accessible"
fi

MODEL_STATE="$(az cognitiveservices account deployment show \
  --resource-group "$RESOURCE_GROUP_NAME" \
  --name "$FOUNDRY_ACCOUNT_NAME" \
  --deployment-name "$MINI_MODEL_NAME" \
  --query properties.provisioningState \
  --output tsv \
  --only-show-errors 2>/dev/null)"
if [[ $? -eq 0 && "$MODEL_STATE" == "Succeeded" ]]; then
  pass "Mini model deployment" "$MINI_MODEL_NAME ($MODEL_STATE)"
else
  fail "Mini model deployment" "$MINI_MODEL_NAME (state=${MODEL_STATE:-not accessible})"
fi

if [[ "$MODEL_STATE" == "Succeeded" ]]; then
  INFERENCE_URL="https://${FOUNDRY_ACCOUNT_NAME}.openai.azure.com/openai/v1/responses"
  REQUEST_BODY="$(printf '{"model":"%s","input":"Say hello world in 3 languages."}' "$MINI_MODEL_NAME")"
  MODEL_OUTPUT="$(az rest \
    --method post \
    --url "$INFERENCE_URL" \
    --resource "https://cognitiveservices.azure.com" \
    --headers "Content-Type=application/json" \
    --body "$REQUEST_BODY" \
    --query "output[].content[].text | [0]" \
    --output tsv \
    --only-show-errors 2>/dev/null)"
  if [[ $? -eq 0 && -n "$MODEL_OUTPUT" ]]; then
    MODEL_OUTPUT="${MODEL_OUTPUT//$'\r'/ }"
    MODEL_OUTPUT="${MODEL_OUTPUT//$'\n'/ }"
    pass "Mini model inference" "$MODEL_OUTPUT"
  else
    fail "Mini model inference" \
      "$MINI_MODEL_NAME did not return text; verify public DNS/network access and Foundry RBAC"
  fi
fi

printf '\n'
if ((FAILURES == 0)); then
  printf 'Validation passed: every executed check succeeded.\n'
  exit 0
fi

printf 'Validation failed: %d executed check(s) failed.\n' "$FAILURES"
exit 1
