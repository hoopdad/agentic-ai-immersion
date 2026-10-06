locals {
  workload_name                = "${var.name_prefix}-${var.resource_suffix}"
  compact_workload_name        = replace(local.workload_name, "-", "")
  resource_group_name          = "rg-${local.workload_name}"
  identity_name                = "id-${local.workload_name}"
  storage_account_name         = "st${local.compact_workload_name}"
  key_vault_name               = "kv-${local.workload_name}"
  container_registry_name      = "cr${local.compact_workload_name}"
  foundry_account_name         = "ai-${local.workload_name}"
  foundry_project_name         = var.foundry_project_name
  search_service_name          = "srch-${local.workload_name}"
  cosmos_db_account_name       = "cosmos-${local.workload_name}"
  application_insights_name    = "appi-${local.workload_name}"
  log_analytics_workspace_name = "log-${local.workload_name}"

  reserved_ipv4_ranges = [
    for cidr in [
      "0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8",
      "169.254.0.0/16", "172.16.0.0/12", "192.0.0.0/24", "192.0.2.0/24",
      "192.168.0.0/16", "198.18.0.0/15", "198.51.100.0/24", "203.0.113.0/24",
      "224.0.0.0/4", "240.0.0.0/4",
      ] : {
      first = sum([for index, octet in split(".", cidrhost(cidr, 0)) : tonumber(octet) * pow(256, 3 - index)])
      last  = sum([for index, octet in split(".", cidrhost(cidr, -1)) : tonumber(octet) * pow(256, 3 - index)])
    }
  ]

  model_deployments = {
    for key, deployment in var.model_deployments : key => {
      name                   = deployment.deployment_name
      version_upgrade_option = deployment.version_upgrade_option
      model = {
        format  = deployment.model_format
        name    = deployment.model_name
        version = deployment.model_version
      }
      scale = {
        capacity = deployment.capacity
        type     = deployment.sku_name
      }
    }
  }


  tags = merge({
    environment = var.environment
    managed-by  = "terraform"
    region      = var.location
    workload    = local.workload_name
  }, var.tags)
}

check "workshop_model_keys" {
  assert {
    condition     = contains(keys(var.model_deployments), var.chat_model_deployment_key)
    error_message = "chat_model_deployment_key must identify an entry in model_deployments."
  }

  assert {
    condition     = contains(keys(var.model_deployments), var.embedding_model_deployment_key)
    error_message = "embedding_model_deployment_key must identify an entry in model_deployments."
  }
}

module "resource_group" {
  source  = "Azure/avm-res-resources-resourcegroup/azurerm"
  version = "0.4.0"

  name             = local.resource_group_name
  location         = var.location
  enable_telemetry = false
  tags             = local.tags
}
