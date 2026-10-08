#!/usr/bin/env bash

set -u
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_NAME="$(basename "$0")"
TFVARS_PATH="${SCRIPT_DIR}/terraform.tfvars"
RESOURCE_GROUP_OVERRIDE=""
FOUNDRY_ACCOUNT_OVERRIDE=""

declare -a SUMMARY_RESOURCES=()
declare -a SUMMARY_TESTS=()
declare -a SUMMARY_RESULTS=()
declare -a SUMMARY_DETAILS=()

FAILURES=0
NETWORK_FAILURES=0
DNS_FAILURES=0
ENDPOINT_FAILURES=0
ACCESS_FAILURES=0
RESOURCE_FAILURES=0

usage() {
  cat <<EOF
Usage: $SCRIPT_NAME [options]

Troubleshoot the private Microsoft Foundry deployment described by terraform.tfvars.
The script is read-only and continues after permission or resource-read failures.

Options:
  --tfvars PATH             Terraform variables file (default: ./terraform.tfvars)
  --resource-group NAME     Override the derived or validation resource group
  --foundry-account NAME    Override the derived or validation Foundry account
  -h, --help                Show this help
EOF
}

trim_detail() {
  local value="${1//$'\r'/ }"
  value="${value//$'\n'/ }"
  value="${value//$'\t'/ }"
  while [[ "$value" == *"  "* ]]; do
    value="${value//  / }"
  done
  printf '%.240s' "$value"
}

record_result() {
  local result="$1"
  local resource="$2"
  local test_name="$3"
  local detail="$4"
  local category="${5:-resource}"

  SUMMARY_RESULTS+=("$result")
  SUMMARY_RESOURCES+=("$resource")
  SUMMARY_TESTS+=("$test_name")
  SUMMARY_DETAILS+=("$(trim_detail "$detail")")

  printf '%-4s | %-30s | %-27s | %s\n' \
    "$result" "$resource" "$test_name" "$(trim_detail "$detail")"

  if [[ "$result" == "FAIL" ]]; then
    FAILURES=$((FAILURES + 1))
    case "$category" in
      network) NETWORK_FAILURES=$((NETWORK_FAILURES + 1)) ;;
      dns) DNS_FAILURES=$((DNS_FAILURES + 1)) ;;
      endpoint) ENDPOINT_FAILURES=$((ENDPOINT_FAILURES + 1)) ;;
      access) ACCESS_FAILURES=$((ACCESS_FAILURES + 1)) ;;
      *) RESOURCE_FAILURES=$((RESOURCE_FAILURES + 1)) ;;
    esac
  fi
}

pass() {
  record_result "PASS" "$1" "$2" "$3" "${4:-resource}"
}

fail() {
  record_result "FAIL" "$1" "$2" "$3" "${4:-resource}"
}

fatal() {
  fail "$1" "$2" "$3" "${4:-resource}"
  print_summary
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

run_az() {
  local error_file
  local rc

  error_file="$(mktemp)"
  AZ_OUTPUT="$(az "$@" --only-show-errors 2>"$error_file")"
  rc=$?
  AZ_ERROR="$(cat "$error_file")"
  rm -f "$error_file"
  return "$rc"
}

az_error_detail() {
  if [[ -n "${AZ_ERROR:-}" ]]; then
    trim_detail "$AZ_ERROR"
  else
    printf 'Azure CLI returned no readable result'
  fi
}

contains_line() {
  local haystack="$1"
  local needle="$2"
  grep -Fqx "$needle" <<<"$haystack"
}

is_private_ipv4() {
  local ip="$1"
  local first second

  IFS=. read -r first second _ _ <<<"$ip"
  [[ "$first" == "10" ]] ||
    [[ "$first" == "127" ]] ||
    [[ "$first" == "169" && "$second" == "254" ]] ||
    [[ "$first" == "192" && "$second" == "168" ]] ||
    [[ "$first" == "172" && "$second" -ge 16 && "$second" -le 31 ]]
}

resolve_ipv4() {
  local hostname="$1"
  local result=""

  if command -v getent >/dev/null 2>&1; then
    result="$(getent ahostsv4 "$hostname" 2>/dev/null | awk '{print $1}' | sort -u)"
  elif command -v nslookup >/dev/null 2>&1; then
    result="$(nslookup "$hostname" 2>/dev/null |
      awk '/^Address: / {print $2}' |
      grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' |
      sort -u)"
  elif command -v host >/dev/null 2>&1; then
    result="$(host "$hostname" 2>/dev/null |
      awk '/ has address / {print $NF}' |
      sort -u)"
  else
    return 2
  fi

  [[ -n "$result" ]] || return 1
  printf '%s\n' "$result"
}

check_dns_resolution() {
  local resource="$1"
  local hostname="$2"
  local ips
  local ip
  local all_private=true
  local resolve_rc

  ips="$(resolve_ipv4 "$hostname")"
  resolve_rc=$?
  if ((resolve_rc == 0)); then
    while IFS= read -r ip; do
      [[ -n "$ip" ]] || continue
      if ! is_private_ipv4 "$ip"; then
        all_private=false
      fi
    done <<<"$ips"

    if [[ "$all_private" == true ]]; then
      pass "$resource" "Hostname resolves privately" "$hostname -> $(tr '\n' ',' <<<"$ips" | sed 's/,$//')" dns
    else
      fail "$resource" "Hostname resolves privately" "$hostname -> $(tr '\n' ',' <<<"$ips" | sed 's/,$//')" dns
    fi
    return
  fi

  case "$resolve_rc" in
    2) fail "$resource" "Hostname resolves privately" "no DNS lookup utility is installed" dns ;;
    *) fail "$resource" "Hostname resolves privately" "$hostname did not resolve from this machine" dns ;;
  esac
}

check_role_names() {
  local resource="$1"
  local principal_id="$2"
  local scope="$3"
  local expected_roles="$4"
  local assignments
  local role

  if ! run_az role assignment list \
    --assignee "$principal_id" \
    --scope "$scope" \
    --include-inherited \
    --query "[].roleDefinitionName" \
    --output tsv; then
    fail "$resource" "Required roles readable" "$(az_error_detail)" access
    return
  fi

  assignments="$AZ_OUTPUT"
  while IFS= read -r role; do
    [[ -n "$role" ]] || continue
    if contains_line "$assignments" "$role"; then
      pass "$resource" "Required role assigned" "$role" access
    else
      fail "$resource" "Required role assigned" "$role is missing at this scope or inherited scopes" access
    fi
  done <<<"$expected_roles"
}

check_public_access() {
  local resource_name="$1"
  local resource_id="$2"
  local value

  if ! run_az resource show \
    --ids "$resource_id" \
    --query "properties.publicNetworkAccess" \
    --output tsv; then
    fail "$resource_name" "Public access inspected" "$(az_error_detail)" access
    return
  fi

  value="$AZ_OUTPUT"
  case "${value,,}" in
    disabled|false)
      pass "$resource_name" "Public access disabled" "publicNetworkAccess=${value}" access
      ;;
    enabled|true)
      fail "$resource_name" "Public access disabled" "publicNetworkAccess=${value}" access
      ;;
    *)
      fail "$resource_name" "Public access inspected" "property was empty or unsupported" access
      ;;
  esac
}

check_resource_property() {
  local resource_name="$1"
  local resource_id="$2"
  local query="$3"
  local expected="$4"
  local test_name="$5"
  local category="${6:-access}"
  local value

  if ! run_az resource show \
    --ids "$resource_id" \
    --query "$query" \
    --output tsv; then
    fail "$resource_name" "$test_name" "$(az_error_detail)" "$category"
    return
  fi

  value="$AZ_OUTPUT"
  if [[ "${value,,}" == "${expected,,}" ]]; then
    pass "$resource_name" "$test_name" "$query=$value" "$category"
  else
    fail "$resource_name" "$test_name" \
      "$query=${value:-empty}; expected=$expected" "$category"
  fi
}

print_summary() {
  local index

  printf '\nDiagnostic summary\n'
  printf '%-4s | %-30s | %-27s | %s\n' "STAT" "RESOURCE" "TEST SUMMARY" "DETAIL"
  printf '%-4s-+-%-30s-+-%-27s-+-%s\n' \
    "----" "------------------------------" "---------------------------" "----------------------------------------"

  for index in "${!SUMMARY_RESULTS[@]}"; do
    printf '%-4s | %-30s | %-27s | %s\n' \
      "${SUMMARY_RESULTS[$index]}" \
      "${SUMMARY_RESOURCES[$index]}" \
      "${SUMMARY_TESTS[$index]}" \
      "${SUMMARY_DETAILS[$index]}"
  done

  printf '\nConclusion\n'
  if ((FAILURES == 0)); then
    printf 'PASS: every executed private-endpoint diagnostic succeeded.\n'
    printf 'The Foundry resource graph, private endpoints, DNS attachments, private resolution, and checked privileges are consistent.\n'
    return
  fi

  printf 'FAIL: %d diagnostic check(s) failed. Most likely fault domain(s):\n' "$FAILURES"
  ((DNS_FAILURES > 0)) &&
    printf -- '- DNS: zone links, records, or the current client DNS path need attention.\n'
  ((ENDPOINT_FAILURES > 0)) &&
    printf -- '- Private endpoints: approval, NIC/IP, subnet placement, or DNS zone groups need attention.\n'
  ((NETWORK_FAILURES > 0)) &&
    printf -- '- Virtual network: subnet policy, delegation, NSG, or address configuration needs attention.\n'
  ((ACCESS_FAILURES > 0)) &&
    printf -- '- Access: Azure read permissions or required Foundry/service RBAC assignments are missing.\n'
  ((RESOURCE_FAILURES > 0)) &&
    printf -- '- Resources: one or more resources are absent, inaccessible, unhealthy, or not fully provisioned.\n'
}

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

command -v az >/dev/null 2>&1 ||
  fatal "Azure CLI" "Azure CLI available" "az was not found on PATH" access
[[ -f "$TFVARS_PATH" ]] ||
  fatal "Terraform variables" "Input file readable" "file not found: $TFVARS_PATH" resource

SUBSCRIPTION_ID="$(read_tfvar_string subscription_id)"
TENANT_ID="$(read_tfvar_string tenant_id)"
LOCATION="$(read_tfvar_string location)"
NAME_PREFIX="$(read_tfvar_string name_prefix)"
RESOURCE_SUFFIX="$(read_tfvar_string resource_suffix)"
FOUNDRY_PROJECT_NAME="$(read_tfvar_string foundry_project_name)"
CAPABILITY_HOST_NAME="$(read_tfvar_string capability_host_name)"
OPERATOR_PRINCIPAL_ID="$(read_tfvar_string operator_principal_id)"
VALIDATION_RESOURCE_GROUP_NAME="$(read_tfvar_string validation_resource_group_name)"
VALIDATION_FOUNDRY_ACCOUNT_NAME="$(read_tfvar_string validation_foundry_account_name)"

[[ -n "$SUBSCRIPTION_ID" ]] ||
  fatal "Terraform variables" "Subscription value present" "subscription_id is missing" resource
[[ -n "$TENANT_ID" ]] ||
  fatal "Terraform variables" "Tenant value present" "tenant_id is missing" resource
[[ -n "$LOCATION" ]] ||
  fatal "Terraform variables" "Location value present" "location is missing" resource
[[ -n "$NAME_PREFIX" ]] ||
  fatal "Terraform variables" "Name prefix present" "name_prefix is missing" resource
[[ -n "$RESOURCE_SUFFIX" ]] ||
  fatal "Terraform variables" "Resource suffix present" "resource_suffix is missing" resource

WORKLOAD_NAME="${NAME_PREFIX}-${RESOURCE_SUFFIX}"
RESOURCE_GROUP_NAME="${RESOURCE_GROUP_OVERRIDE:-${VALIDATION_RESOURCE_GROUP_NAME:-rg-${WORKLOAD_NAME}}}"
FOUNDRY_ACCOUNT_NAME="${FOUNDRY_ACCOUNT_OVERRIDE:-${VALIDATION_FOUNDRY_ACCOUNT_NAME:-ai-${WORKLOAD_NAME}}}"
FOUNDRY_PROJECT_NAME="${FOUNDRY_PROJECT_NAME:-marketplace}"
CAPABILITY_HOST_NAME="${CAPABILITY_HOST_NAME:-caphostproj}"

printf 'Microsoft Foundry private endpoint diagnostics\n'
printf 'Terraform variables: %s\n' "$TFVARS_PATH"
printf 'Target resource group: %s\n\n' "$RESOURCE_GROUP_NAME"
printf '%-4s | %-30s | %-27s | %s\n' "STAT" "RESOURCE" "TEST SUMMARY" "DETAIL"
printf '%-4s-+-%-30s-+-%-27s-+-%s\n' \
  "----" "------------------------------" "---------------------------" "----------------------------------------"

if ! az account show --only-show-errors >/dev/null 2>&1 ||
  ! az account get-access-token \
    --resource "https://management.azure.com/" \
    --only-show-errors >/dev/null 2>&1; then
  printf 'No usable cached Azure CLI credentials were found; starting device-code login.\n' >&2
  if ! az login \
    --tenant "$TENANT_ID" \
    --use-device-code \
    --only-show-errors >/dev/null; then
    fatal "Azure CLI context" "Device login succeeded" "device-code login failed" access
  fi
fi

if ! az account set \
  --subscription "$SUBSCRIPTION_ID" \
  --only-show-errors >/dev/null 2>&1; then
  printf 'Cached credentials cannot select the configured subscription; starting device-code login.\n' >&2
  if ! az login \
    --tenant "$TENANT_ID" \
    --use-device-code \
    --only-show-errors >/dev/null ||
    ! az account set \
      --subscription "$SUBSCRIPTION_ID" \
      --only-show-errors >/dev/null; then
    fatal "Azure CLI context" "Target subscription selectable" "could not select configured subscription" access
  fi
fi

if run_az account show \
  --query "[[id,tenantId,name,user.name,user.type]]" \
  --output tsv; then
  IFS=$'\t' read -r ACTIVE_SUBSCRIPTION_ID ACTIVE_TENANT_ID ACTIVE_SUBSCRIPTION_NAME ACTIVE_USER ACTIVE_USER_TYPE <<<"$AZ_OUTPUT"
  if [[ "${ACTIVE_SUBSCRIPTION_ID,,}" == "${SUBSCRIPTION_ID,,}" &&
        "${ACTIVE_TENANT_ID,,}" == "${TENANT_ID,,}" ]]; then
    pass "Azure CLI context" "Tenant subscription match" \
      "$ACTIVE_SUBSCRIPTION_NAME; $ACTIVE_USER_TYPE=$ACTIVE_USER" access
  else
    fatal "Azure CLI context" "Tenant subscription match" \
      "active tenant or subscription differs from terraform.tfvars" access
  fi
else
  fatal "Azure CLI context" "Account context readable" "$(az_error_detail)" access
fi

if [[ -z "$OPERATOR_PRINCIPAL_ID" ]] &&
  run_az ad signed-in-user show --query id --output tsv; then
  OPERATOR_PRINCIPAL_ID="$AZ_OUTPUT"
fi

if ! run_az group show \
  --name "$RESOURCE_GROUP_NAME" \
  --query "[[id,location,properties.provisioningState]]" \
  --output tsv; then
  fatal "Resource group" "Resource group readable" "$(az_error_detail)" access
fi

IFS=$'\t' read -r RESOURCE_GROUP_ID RESOURCE_GROUP_LOCATION RESOURCE_GROUP_STATE <<<"$AZ_OUTPUT"
if [[ "$RESOURCE_GROUP_STATE" == "Succeeded" &&
      "${RESOURCE_GROUP_LOCATION,,}" == "${LOCATION,,}" ]]; then
  pass "Resource group" "Provisioning state healthy" \
    "$RESOURCE_GROUP_NAME; $RESOURCE_GROUP_LOCATION" resource
else
  fail "Resource group" "Provisioning state healthy" \
    "state=${RESOURCE_GROUP_STATE:-unknown}; location=${RESOURCE_GROUP_LOCATION:-unknown}" resource
fi

if run_az resource list \
  --resource-group "$RESOURCE_GROUP_NAME" \
  --query "[].[id,name,type,properties.provisioningState]" \
  --output tsv; then
  RESOURCE_INVENTORY="$AZ_OUTPUT"
  while IFS=$'\t' read -r resource_id resource_name resource_type resource_state; do
    [[ -n "$resource_id" ]] || continue
    if [[ -z "$resource_state" || "$resource_state" == "None" || "$resource_state" == "Succeeded" ]]; then
      pass "$resource_name" "Provisioning state healthy" \
        "$resource_type; state=${resource_state:-not exposed}" resource
    else
      fail "$resource_name" "Provisioning state healthy" \
        "$resource_type; state=$resource_state" resource
    fi
  done <<<"$RESOURCE_INVENTORY"
else
  RESOURCE_INVENTORY=""
  fail "Resource group" "Resource inventory readable" "$(az_error_detail)" access
fi

FOUNDRY_ACCOUNT_ID="/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP_NAME}/providers/Microsoft.CognitiveServices/accounts/${FOUNDRY_ACCOUNT_NAME}"
FOUNDRY_PROJECT_ID="${FOUNDRY_ACCOUNT_ID}/projects/${FOUNDRY_PROJECT_NAME}"

if run_az cognitiveservices account show \
  --resource-group "$RESOURCE_GROUP_NAME" \
  --name "$FOUNDRY_ACCOUNT_NAME" \
  --query "[id,properties.provisioningState,properties.publicNetworkAccess,properties.restrictOutboundNetworkAccess,identity.userAssignedIdentities]" \
  --output json; then
  FOUNDRY_ACCOUNT_JSON="$AZ_OUTPUT"
  FOUNDRY_STATE="$(az cognitiveservices account show \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --name "$FOUNDRY_ACCOUNT_NAME" \
    --query properties.provisioningState \
    --output tsv \
    --only-show-errors 2>/dev/null)"
  FOUNDRY_PUBLIC="$(az cognitiveservices account show \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --name "$FOUNDRY_ACCOUNT_NAME" \
    --query properties.publicNetworkAccess \
    --output tsv \
    --only-show-errors 2>/dev/null)"
  FOUNDRY_OUTBOUND="$(az cognitiveservices account show \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --name "$FOUNDRY_ACCOUNT_NAME" \
    --query properties.restrictOutboundNetworkAccess \
    --output tsv \
    --only-show-errors 2>/dev/null)"

  [[ "$FOUNDRY_STATE" == "Succeeded" ]] &&
    pass "$FOUNDRY_ACCOUNT_NAME" "Provisioning state healthy" "$FOUNDRY_STATE" resource ||
    fail "$FOUNDRY_ACCOUNT_NAME" "Provisioning state healthy" "state=${FOUNDRY_STATE:-unknown}" resource
  [[ "${FOUNDRY_PUBLIC,,}" == "disabled" ]] &&
    pass "$FOUNDRY_ACCOUNT_NAME" "Public access disabled" "publicNetworkAccess=$FOUNDRY_PUBLIC" access ||
    fail "$FOUNDRY_ACCOUNT_NAME" "Public access disabled" "publicNetworkAccess=${FOUNDRY_PUBLIC:-unknown}" access
  [[ "${FOUNDRY_OUTBOUND,,}" == "true" ]] &&
    pass "$FOUNDRY_ACCOUNT_NAME" "Outbound access restricted" "restrictOutboundNetworkAccess=$FOUNDRY_OUTBOUND" network ||
    fail "$FOUNDRY_ACCOUNT_NAME" "Outbound access restricted" "restrictOutboundNetworkAccess=${FOUNDRY_OUTBOUND:-unknown}" network
  check_resource_property "$FOUNDRY_ACCOUNT_NAME" "$FOUNDRY_ACCOUNT_ID" \
    "properties.disableLocalAuth" "true" "Local authentication disabled" access
  check_resource_property "$FOUNDRY_ACCOUNT_NAME" "$FOUNDRY_ACCOUNT_ID" \
    "properties.networkAcls.defaultAction" "Deny" "Network default denied" network
else
  FOUNDRY_ACCOUNT_JSON=""
  fail "$FOUNDRY_ACCOUNT_NAME" "Foundry account readable" "$(az_error_detail)" access
fi

if run_az rest \
  --method get \
  --url "https://management.azure.com${FOUNDRY_PROJECT_ID}?api-version=2026-03-01" \
  --query "properties.provisioningState" \
  --output tsv; then
  [[ "$AZ_OUTPUT" == "Succeeded" ]] &&
    pass "$FOUNDRY_PROJECT_NAME" "Project state healthy" "$AZ_OUTPUT" resource ||
    fail "$FOUNDRY_PROJECT_NAME" "Project state healthy" "state=${AZ_OUTPUT:-unknown}" resource
else
  fail "$FOUNDRY_PROJECT_NAME" "Foundry project readable" "$(az_error_detail)" access
fi

if run_az rest \
  --method get \
  --url "https://management.azure.com${FOUNDRY_PROJECT_ID}/connections?api-version=2025-04-01-preview" \
  --query "value[].[name,properties.category,properties.provisioningState,properties.target]" \
  --output tsv; then
  if [[ -z "$AZ_OUTPUT" ]]; then
    fail "$FOUNDRY_PROJECT_NAME" "Project connections present" \
      "no project connections were returned" resource
  else
    while IFS=$'\t' read -r connection_name connection_category connection_state connection_target; do
      [[ -n "$connection_name" ]] || continue
      if [[ -z "$connection_state" || "$connection_state" == "None" || "$connection_state" == "Succeeded" ]]; then
        pass "$connection_name" "Project connection healthy" \
          "$connection_category; ${connection_target:-target not exposed}" resource
      else
        fail "$connection_name" "Project connection healthy" \
          "$connection_category; state=$connection_state" resource
      fi
    done <<<"$AZ_OUTPUT"
  fi
else
  fail "$FOUNDRY_PROJECT_NAME" "Project connections readable" "$(az_error_detail)" access
fi

if run_az cognitiveservices account deployment list \
  --resource-group "$RESOURCE_GROUP_NAME" \
  --name "$FOUNDRY_ACCOUNT_NAME" \
  --query "[].[name,properties.provisioningState,properties.model.name,properties.model.version,sku.name,sku.capacity]" \
  --output tsv; then
  if [[ -z "$AZ_OUTPUT" ]]; then
    fail "$FOUNDRY_ACCOUNT_NAME" "Model deployments present" "no deployments returned" resource
  else
    while IFS=$'\t' read -r deployment_name deployment_state model_name model_version sku_name sku_capacity; do
      [[ -n "$deployment_name" ]] || continue
      [[ "$deployment_state" == "Succeeded" ]] &&
        pass "$deployment_name" "Model deployment healthy" \
          "$model_name $model_version; $sku_name/$sku_capacity" resource ||
        fail "$deployment_name" "Model deployment healthy" \
          "state=${deployment_state:-unknown}; $model_name $model_version" resource
    done <<<"$AZ_OUTPUT"
  fi
else
  fail "$FOUNDRY_ACCOUNT_NAME" "Model deployments readable" "$(az_error_detail)" access
fi

CAPABILITY_HOST_ID="${FOUNDRY_PROJECT_ID}/capabilityHosts/${CAPABILITY_HOST_NAME}"
if run_az rest \
  --method get \
  --url "https://management.azure.com${CAPABILITY_HOST_ID}?api-version=2025-04-01-preview" \
  --query "properties.provisioningState" \
  --output tsv; then
  [[ "$AZ_OUTPUT" == "Succeeded" ]] &&
    pass "$CAPABILITY_HOST_NAME" "Capability host healthy" "$AZ_OUTPUT" resource ||
    fail "$CAPABILITY_HOST_NAME" "Capability host healthy" "state=${AZ_OUTPUT:-unknown}" resource
else
  fail "$CAPABILITY_HOST_NAME" "Capability host readable" "$(az_error_detail)" access
fi

if [[ -n "$OPERATOR_PRINCIPAL_ID" ]]; then
  check_role_names "$FOUNDRY_ACCOUNT_NAME" "$OPERATOR_PRINCIPAL_ID" "$FOUNDRY_ACCOUNT_ID" \
    $'Cognitive Services OpenAI User\nFoundry Owner'
  check_role_names "$FOUNDRY_PROJECT_NAME" "$OPERATOR_PRINCIPAL_ID" "$FOUNDRY_PROJECT_ID" \
    "Foundry Project Manager"
else
  fail "Current operator" "Principal identity resolved" \
    "operator_principal_id is absent and signed-in user lookup was denied" access
fi

if run_az network vnet list \
  --resource-group "$RESOURCE_GROUP_NAME" \
  --query "[].[id,name,provisioningState,length(dhcpOptions.dnsServers)]" \
  --output tsv; then
  VNET_ROWS="$AZ_OUTPUT"
  if [[ -z "$VNET_ROWS" ]]; then
    fail "Virtual network" "Virtual network discovered" "no VNet found in resource group" network
  fi

  while IFS=$'\t' read -r vnet_id vnet_name vnet_state dns_server_count; do
    [[ -n "$vnet_id" ]] || continue
    [[ "$vnet_state" == "Succeeded" ]] &&
      pass "$vnet_name" "Provisioning state healthy" "$vnet_state" network ||
      fail "$vnet_name" "Provisioning state healthy" "state=${vnet_state:-unknown}" network
    if [[ "$dns_server_count" == "0" ]]; then
      pass "$vnet_name" "Azure DNS configured" "uses Azure-provided DNS" dns
    else
      fail "$vnet_name" "Azure DNS configured" \
        "configured custom DNS server count: ${dns_server_count:-unknown}" dns
    fi

    if run_az network vnet subnet list \
      --resource-group "$RESOURCE_GROUP_NAME" \
      --vnet-name "$vnet_name" \
      --query "[].[id,name,provisioningState,addressPrefix,privateEndpointNetworkPolicies,networkSecurityGroup.id,delegations[0].serviceName,serviceAssociationLinks[0].link]" \
      --output tsv; then
      while IFS=$'\t' read -r subnet_id subnet_name subnet_state subnet_prefix pe_policies nsg_id delegations association_links; do
        [[ -n "$subnet_id" ]] || continue
        [[ "$subnet_state" == "Succeeded" ]] &&
          pass "$subnet_name" "Subnet state healthy" "$subnet_prefix; $subnet_state" network ||
          fail "$subnet_name" "Subnet state healthy" "$subnet_prefix; state=${subnet_state:-unknown}" network
        [[ -n "$nsg_id" ]] &&
          pass "$subnet_name" "NSG attachment present" "$(basename "$nsg_id")" network ||
          fail "$subnet_name" "NSG attachment present" "no network security group attached" network

        if [[ "$subnet_name" == *"private-endpoint"* ]]; then
          [[ "${pe_policies,,}" == "disabled" ]] &&
            pass "$subnet_name" "Endpoint policies disabled" "$pe_policies" network ||
            fail "$subnet_name" "Endpoint policies disabled" "value=${pe_policies:-unknown}" network
        fi

        if [[ "$subnet_name" == *"agent"* ]]; then
          [[ "$delegations" == *"Microsoft.App/environments"* ]] &&
            pass "$subnet_name" "Agent delegation present" "$delegations" network ||
            fail "$subnet_name" "Agent delegation present" "Microsoft.App/environments not found" network
          [[ -n "$association_links" ]] &&
            pass "$subnet_name" "Service association present" "$association_links" network ||
            fail "$subnet_name" "Service association present" \
              "no service association link; provisioning may be incomplete" network
        fi
      done <<<"$AZ_OUTPUT"
    else
      fail "$vnet_name" "Subnet inventory readable" "$(az_error_detail)" access
    fi
  done <<<"$VNET_ROWS"
else
  VNET_ROWS=""
  fail "Virtual network" "VNet inventory readable" "$(az_error_detail)" access
fi

if run_az network nsg list \
  --resource-group "$RESOURCE_GROUP_NAME" \
  --query "[].[name,id,provisioningState]" \
  --output tsv; then
  while IFS=$'\t' read -r nsg_name nsg_id nsg_state; do
    [[ -n "$nsg_id" ]] || continue
    [[ "$nsg_state" == "Succeeded" ]] &&
      pass "$nsg_name" "NSG state healthy" "$nsg_state" network ||
      fail "$nsg_name" "NSG state healthy" "state=${nsg_state:-unknown}" network

    if run_az network nsg rule list \
      --resource-group "$RESOURCE_GROUP_NAME" \
      --nsg-name "$nsg_name" \
      --query "[?direction=='Outbound' && access=='Deny'].[name,priority,destinationPortRange,destinationAddressPrefix]" \
      --output tsv; then
      if [[ -z "$AZ_OUTPUT" ]]; then
        pass "$nsg_name" "Outbound denies absent" "no custom outbound deny rules" network
      else
        fail "$nsg_name" "Outbound denies absent" "$(tr '\n' ';' <<<"$AZ_OUTPUT")" network
      fi
    else
      fail "$nsg_name" "NSG rules readable" "$(az_error_detail)" access
    fi
  done <<<"$AZ_OUTPUT"
else
  fail "Network security groups" "NSG inventory readable" "$(az_error_detail)" access
fi

declare -a PRIVATE_ENDPOINT_IPS=()
if run_az network private-endpoint list \
  --resource-group "$RESOURCE_GROUP_NAME" \
  --query "[].[id,name,provisioningState,subnet.id,networkInterfaces[0].id,privateLinkServiceConnections[0].privateLinkServiceConnectionState.status,privateLinkServiceConnections[0].privateLinkServiceId]" \
  --output tsv; then
  PRIVATE_ENDPOINT_ROWS="$AZ_OUTPUT"
  if [[ -z "$PRIVATE_ENDPOINT_ROWS" ]]; then
    fail "Private endpoints" "Endpoint inventory present" "no private endpoints found" endpoint
  fi

  while IFS=$'\t' read -r pe_id pe_name pe_state pe_subnet_id pe_nic_id pe_status pe_target_id; do
    [[ -n "$pe_id" ]] || continue
    [[ "$pe_state" == "Succeeded" ]] &&
      pass "$pe_name" "Endpoint state healthy" "$pe_state" endpoint ||
      fail "$pe_name" "Endpoint state healthy" "state=${pe_state:-unknown}" endpoint
    [[ "$pe_status" == "Approved" ]] &&
      pass "$pe_name" "Endpoint connection approved" "$pe_status" endpoint ||
      fail "$pe_name" "Endpoint connection approved" \
        "status=${pe_status:-unknown}" endpoint
    [[ "$pe_subnet_id" == *"private-endpoint"* ]] &&
      pass "$pe_name" "Endpoint subnet correct" "$(basename "$pe_subnet_id")" endpoint ||
      fail "$pe_name" "Endpoint subnet correct" "subnet=$pe_subnet_id" endpoint
    [[ -n "$pe_target_id" ]] &&
      pass "$pe_name" "Endpoint target present" "$pe_target_id" endpoint ||
      fail "$pe_name" "Endpoint target present" "target resource ID is empty" endpoint

    if [[ -n "$pe_nic_id" ]] &&
      run_az network nic show \
        --ids "$pe_nic_id" \
        --query "ipConfigurations[].privateIPAddress" \
        --output tsv; then
      pe_ips="$AZ_OUTPUT"
      private_ip_ok=true
      while IFS= read -r pe_ip; do
        [[ -n "$pe_ip" ]] || continue
        PRIVATE_ENDPOINT_IPS+=("$pe_ip")
        if ! is_private_ipv4 "$pe_ip"; then
          private_ip_ok=false
        fi
      done <<<"$pe_ips"
      if [[ -n "$pe_ips" && "$private_ip_ok" == true ]]; then
        pass "$pe_name" "Private IP assigned" "$(tr '\n' ',' <<<"$pe_ips" | sed 's/,$//')" endpoint
      else
        fail "$pe_name" "Private IP assigned" "NIC has no RFC1918 private IP" endpoint
      fi
    else
      fail "$pe_name" "Endpoint NIC readable" "$(az_error_detail)" access
    fi

    if run_az network private-endpoint dns-zone-group list \
      --endpoint-name "$pe_name" \
      --resource-group "$RESOURCE_GROUP_NAME" \
      --query "[].[name,privateDnsZoneConfigs[].privateDnsZoneId]" \
      --output tsv; then
      if [[ -n "$AZ_OUTPUT" ]]; then
        pass "$pe_name" "DNS zone group attached" "$(tr '\n' ';' <<<"$AZ_OUTPUT")" dns
      else
        fail "$pe_name" "DNS zone group attached" "no private DNS zone group found" dns
      fi
    else
      fail "$pe_name" "DNS zone group readable" "$(az_error_detail)" access
    fi
  done <<<"$PRIVATE_ENDPOINT_ROWS"
else
  PRIVATE_ENDPOINT_ROWS=""
  fail "Private endpoints" "Endpoint inventory readable" "$(az_error_detail)" access
fi

EXPECTED_DNS_ZONES=(
  "${LOCATION}.data.privatelink.azurecr.io"
  "privatelink.azurecr.io"
  "privatelink.agentsvc.azure-automation.net"
  "privatelink.blob.core.windows.net"
  "privatelink.cognitiveservices.azure.com"
  "privatelink.documents.azure.com"
  "privatelink.monitor.azure.com"
  "privatelink.ods.opinsights.azure.com"
  "privatelink.oms.opinsights.azure.com"
  "privatelink.openai.azure.com"
  "privatelink.search.windows.net"
  "privatelink.services.ai.azure.com"
  "privatelink.vaultcore.azure.net"
)

if run_az network private-dns zone list \
  --query "[].[name,resourceGroup,id]" \
  --output tsv; then
  DNS_ZONE_ROWS="$AZ_OUTPUT"
  for zone_name in "${EXPECTED_DNS_ZONES[@]}"; do
    zone_row="$(awk -F '\t' -v zone="$zone_name" '$1 == zone {print; exit}' <<<"$DNS_ZONE_ROWS")"
    if [[ -n "$zone_row" ]]; then
      IFS=$'\t' read -r discovered_zone_name zone_resource_group zone_id <<<"$zone_row"
      pass "$zone_name" "Private DNS zone present" \
        "resource group=$zone_resource_group" dns
    else
      fail "$zone_name" "Private DNS zone present" "expected zone is missing" dns
      continue
    fi

    if run_az network private-dns link vnet list \
      --resource-group "$zone_resource_group" \
      --zone-name "$zone_name" \
      --query "[].[name,virtualNetwork.id,virtualNetworkLinkState,registrationEnabled]" \
      --output tsv; then
      if [[ -n "$AZ_OUTPUT" ]]; then
        all_links_complete=true
        while IFS=$'\t' read -r link_name linked_vnet link_state registration_enabled; do
          [[ -n "$link_name" ]] || continue
          if [[ "$link_state" != "Completed" ]]; then
            all_links_complete=false
          fi
        done <<<"$AZ_OUTPUT"
        if [[ "$all_links_complete" == true ]]; then
          pass "$zone_name" "VNet DNS link complete" "$(tr '\n' ';' <<<"$AZ_OUTPUT")" dns
        else
          fail "$zone_name" "VNet DNS link complete" "$(tr '\n' ';' <<<"$AZ_OUTPUT")" dns
        fi
      else
        fail "$zone_name" "VNet DNS link present" "zone has no VNet links" dns
      fi
    else
      fail "$zone_name" "VNet DNS links readable" "$(az_error_detail)" access
    fi

    if run_az network private-dns record-set a list \
      --resource-group "$zone_resource_group" \
      --zone-name "$zone_name" \
      --query "[?name!='@'].[name,aRecords[].ipv4Address]" \
      --output tsv; then
      if [[ -n "$AZ_OUTPUT" ]]; then
        pass "$zone_name" "Private records populated" "$(tr '\n' ';' <<<"$AZ_OUTPUT")" dns
      else
        fail "$zone_name" "Private records populated" "no A records found" dns
      fi
    else
      fail "$zone_name" "DNS records readable" "$(az_error_detail)" access
    fi
  done
else
  DNS_ZONE_ROWS=""
  fail "Private DNS zones" "DNS inventory readable" "$(az_error_detail)" access
fi

declare -a SERVICE_FQDNS=()
SERVICE_FQDNS+=("$FOUNDRY_ACCOUNT_NAME|${FOUNDRY_ACCOUNT_NAME}.services.ai.azure.com")
SERVICE_FQDNS+=("$FOUNDRY_ACCOUNT_NAME|${FOUNDRY_ACCOUNT_NAME}.openai.azure.com")
SERVICE_FQDNS+=("$FOUNDRY_ACCOUNT_NAME|${FOUNDRY_ACCOUNT_NAME}.cognitiveservices.azure.com")

if [[ -n "$RESOURCE_INVENTORY" ]]; then
  while IFS=$'\t' read -r resource_id resource_name resource_type resource_state; do
    [[ -n "$resource_id" ]] || continue
    case "${resource_type,,}" in
      microsoft.storage/storageaccounts)
        check_public_access "$resource_name" "$resource_id"
        check_resource_property "$resource_name" "$resource_id" \
          "properties.allowSharedKeyAccess" "false" "Shared keys disabled" access
        check_resource_property "$resource_name" "$resource_id" \
          "properties.networkAcls.defaultAction" "Deny" "Network default denied" network
        SERVICE_FQDNS+=("$resource_name|${resource_name}.blob.core.windows.net")
        ;;
      microsoft.documentdb/databaseaccounts)
        check_public_access "$resource_name" "$resource_id"
        check_resource_property "$resource_name" "$resource_id" \
          "properties.disableLocalAuth" "true" "Local authentication disabled" access
        SERVICE_FQDNS+=("$resource_name|${resource_name}.documents.azure.com")
        ;;
      microsoft.search/searchservices)
        check_public_access "$resource_name" "$resource_id"
        check_resource_property "$resource_name" "$resource_id" \
          "properties.disableLocalAuth" "true" "Local authentication disabled" access
        SERVICE_FQDNS+=("$resource_name|${resource_name}.search.windows.net")
        ;;
      microsoft.keyvault/vaults)
        check_public_access "$resource_name" "$resource_id"
        check_resource_property "$resource_name" "$resource_id" \
          "properties.networkAcls.defaultAction" "Deny" "Network default denied" network
        SERVICE_FQDNS+=("$resource_name|${resource_name}.vault.azure.net")
        ;;
      microsoft.containerregistry/registries)
        check_public_access "$resource_name" "$resource_id"
        check_resource_property "$resource_name" "$resource_id" \
          "properties.adminUserEnabled" "false" "Registry admin disabled" access
        SERVICE_FQDNS+=("$resource_name|${resource_name}.azurecr.io")
        SERVICE_FQDNS+=("$resource_name|${resource_name}.${LOCATION}.data.azurecr.io")
        ;;
      microsoft.operationalinsights/workspaces)
        check_resource_property "$resource_name" "$resource_id" \
          "properties.publicNetworkAccessForIngestion" "Disabled" "Public ingestion disabled" access
        ;;
      microsoft.insights/components)
        check_resource_property "$resource_name" "$resource_id" \
          "properties.publicNetworkAccessForIngestion" "Disabled" "Public ingestion disabled" access
        ;;
      microsoft.insights/privatelinkscopes)
        if run_az resource show \
          --ids "$resource_id" \
          --query "[[properties.accessModeSettings.ingestionAccessMode,properties.accessModeSettings.queryAccessMode]]" \
          --output tsv; then
          IFS=$'\t' read -r ingestion_mode query_mode <<<"$AZ_OUTPUT"
          [[ "$ingestion_mode" == "PrivateOnly" ]] &&
            pass "$resource_name" "Monitor ingestion private" \
              "ingestion=$ingestion_mode; query=${query_mode:-unknown}" access ||
            fail "$resource_name" "Monitor ingestion private" \
              "ingestion=${ingestion_mode:-unknown}; query=${query_mode:-unknown}" access
        else
          fail "$resource_name" "Monitor access readable" "$(az_error_detail)" access
        fi
        ;;
    esac
  done <<<"$RESOURCE_INVENTORY"
fi

for service_entry in "${SERVICE_FQDNS[@]}"; do
  service_name="${service_entry%%|*}"
  service_fqdn="${service_entry#*|}"
  check_dns_resolution "$service_name" "$service_fqdn"
done

if [[ -n "$FOUNDRY_ACCOUNT_JSON" ]]; then
  IDENTITY_RESOURCE_ID="$(az cognitiveservices account show \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --name "$FOUNDRY_ACCOUNT_NAME" \
    --query "keys(identity.userAssignedIdentities)[0]" \
    --output tsv \
    --only-show-errors 2>/dev/null)"
  if [[ -n "$IDENTITY_RESOURCE_ID" ]] &&
    run_az identity show \
      --ids "$IDENTITY_RESOURCE_ID" \
      --query "[[name,principalId]]" \
      --output tsv; then
    IFS=$'\t' read -r IDENTITY_NAME IDENTITY_PRINCIPAL_ID <<<"$AZ_OUTPUT"
    pass "$IDENTITY_NAME" "Managed identity resolved" "$IDENTITY_PRINCIPAL_ID" access
    check_role_names "$IDENTITY_NAME" "$IDENTITY_PRINCIPAL_ID" "$FOUNDRY_ACCOUNT_ID" \
      $'Cognitive Services OpenAI User\nFoundry User'
  else
    fail "$FOUNDRY_ACCOUNT_NAME" "Managed identity resolved" \
      "user-assigned identity was missing or unreadable" access
  fi
fi

if run_az monitor activity-log list \
  --resource-group "$RESOURCE_GROUP_NAME" \
  --status Failed \
  --offset 7d \
  --max-events 20 \
  --query "[].[eventTimestamp,resourceType.value,resourceGroupName,operationName.value,status.value,subStatus.value]" \
  --output tsv; then
  if [[ -z "$AZ_OUTPUT" ]]; then
    pass "Resource group" "Recent failures absent" "no failed management operations in the last 7 days" resource
  else
    fail "Resource group" "Recent failures absent" "$(tr '\n' ';' <<<"$AZ_OUTPUT")" resource
  fi
else
  fail "Resource group" "Activity log readable" "$(az_error_detail)" access
fi

print_summary
((FAILURES == 0))
