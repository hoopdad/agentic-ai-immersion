module "container_registry" {
  source  = "Azure/avm-res-containerregistry-registry/azurerm"
  version = "0.8.0"

  name                          = local.container_registry_name
  location                      = module.resource_group.location
  resource_group_name           = module.resource_group.name
  sku                           = "Premium"
  admin_enabled                 = false
  anonymous_pull_enabled        = false
  export_policy_enabled         = true
  public_network_access_enabled = true
  network_rule_bypass_option    = "None"
  enable_telemetry              = false
  tags                          = local.tags

  role_assignments = {
    foundry_pull = {
      role_definition_id_or_name       = "AcrPull"
      principal_id                     = module.foundry_identity.principal_id
      principal_type                   = "ServicePrincipal"
      skip_service_principal_aad_check = true
    }
  }

  network_rule_set = {
    default_action = "Deny"
    ip_rule = [
      for cidr in sort(tolist(var.allowed_public_ipv4_cidrs)) : {
        action   = "Allow"
        ip_range = cidr
      }
    ]
  }

  diagnostic_settings = {
    hub = {
      name                  = "${local.workload_name}-acr-diag"
      workspace_resource_id = azurerm_log_analytics_workspace.foundry.id
    }
  }
}
