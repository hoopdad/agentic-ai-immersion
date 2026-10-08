module "container_registry" {
  source  = "Azure/avm-res-containerregistry-registry/azurerm"
  version = "0.8.0"

  name                          = local.container_registry_name
  location                      = module.resource_group.location
  resource_group_name           = module.resource_group.name
  sku                           = "Premium"
  admin_enabled                 = false
  anonymous_pull_enabled        = false
  export_policy_enabled         = false
  public_network_access_enabled = false
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

  private_endpoints = {
    registry = {
      name               = "${local.workload_name}-acr-pe"
      subnet_resource_id = module.spoke_vnet.subnets["private_endpoints"].resource_id
      private_dns_zone_resource_ids = [
        azurerm_private_dns_zone.foundry["privatelink.azurecr.io"].id,
        azurerm_private_dns_zone.foundry["${var.location}.data.privatelink.azurecr.io"].id,
      ]
    }
  }

  diagnostic_settings = {
    hub = {
      name                  = "${local.workload_name}-acr-diag"
      workspace_resource_id = azurerm_log_analytics_workspace.foundry.id
    }
  }
}

resource "azurerm_private_dns_a_record" "container_registry_data" {
  name                = local.container_registry_name
  zone_name           = azurerm_private_dns_zone.foundry["${var.location}.data.privatelink.azurecr.io"].name
  resource_group_name = module.resource_group.name
  ttl                 = 10
  records = flatten([
    for zone in module.container_registry.private_endpoints["registry"].private_dns_zone_configs : [
      for record in zone.record_sets :
      record.ip_addresses
      if record.fqdn == "${local.container_registry_name}.${var.location}.data.privatelink.azurecr.io"
    ]
  ])
  tags = local.tags
}
