locals {
  workload_name                   = "${var.name_prefix}-${var.resource_suffix}"
  compact_workload_name           = replace(local.workload_name, "-", "")
  resource_group_name             = "rg-${local.workload_name}"
  virtual_network_name            = "vnet-${local.workload_name}"
  identity_name                   = "id-${local.workload_name}"
  storage_account_name            = "st${local.compact_workload_name}"
  key_vault_name                  = "kv-${local.workload_name}"
  container_registry_name         = "cr${local.compact_workload_name}"
  foundry_account_name            = "ai-${local.workload_name}"
  foundry_project_name            = var.foundry_project_name
  search_service_name             = "srch-${local.workload_name}"
  cosmos_db_account_name          = "cosmos-${local.workload_name}"
  application_insights_name       = "appi-${local.workload_name}"
  log_analytics_workspace_name    = "log-${local.workload_name}"
  monitor_private_link_scope_name = "ampls-${local.workload_name}"

  private_dns_zones = toset([
    "${var.location}.data.privatelink.azurecr.io",
    "privatelink.azurecr.io",
    "privatelink.agentsvc.azure-automation.net",
    "privatelink.blob.core.windows.net",
    "privatelink.cognitiveservices.azure.com",
    "privatelink.documents.azure.com",
    "privatelink.monitor.azure.com",
    "privatelink.ods.opinsights.azure.com",
    "privatelink.oms.opinsights.azure.com",
    "privatelink.openai.azure.com",
    "privatelink.search.windows.net",
    "privatelink.services.ai.azure.com",
    "privatelink.vaultcore.azure.net",
  ])

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

  ipv4_cidrs = {
    agent_subnet            = var.agent_subnet_address_prefix
    private_endpoint_subnet = var.private_endpoint_subnet_address_prefix
    rfc1918_10              = "10.0.0.0/8"
    rfc1918_172             = "172.16.0.0/12"
    rfc1918_192             = "192.168.0.0/16"
    virtual_network         = var.virtual_network_address_space
  }

  ipv4_ranges = {
    for name, cidr in local.ipv4_cidrs : name => {
      first = sum([
        for index, octet in split(".", cidrhost(cidr, 0)) :
        tonumber(octet) * pow(256, 3 - index)
      ])
      last = sum([
        for index, octet in split(".", cidrhost(cidr, -1)) :
        tonumber(octet) * pow(256, 3 - index)
      ])
    }
  }

  tags = merge({
    environment = var.environment
    managed-by  = "terraform"
    region      = var.location
    workload    = local.workload_name
  }, var.tags)
}

check "subnet_layout" {
  assert {
    condition = anytrue([
      for range_name in ["rfc1918_10", "rfc1918_172", "rfc1918_192"] :
      local.ipv4_ranges.virtual_network.first >= local.ipv4_ranges[range_name].first &&
      local.ipv4_ranges.virtual_network.last <= local.ipv4_ranges[range_name].last
    ])
    error_message = "virtual_network_address_space must be fully contained by an RFC 1918 private IPv4 range."
  }

  assert {
    condition = alltrue([
      for subnet_name in ["agent_subnet", "private_endpoint_subnet"] :
      local.ipv4_ranges[subnet_name].first >= local.ipv4_ranges.virtual_network.first &&
      local.ipv4_ranges[subnet_name].last <= local.ipv4_ranges.virtual_network.last
    ])
    error_message = "Both subnet prefixes must be contained by virtual_network_address_space."
  }

  assert {
    condition = (
      local.ipv4_ranges.agent_subnet.last < local.ipv4_ranges.private_endpoint_subnet.first ||
      local.ipv4_ranges.private_endpoint_subnet.last < local.ipv4_ranges.agent_subnet.first
    )
    error_message = "agent_subnet_address_prefix and private_endpoint_subnet_address_prefix must not overlap."
  }
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
