module "key_vault" {
  source  = "Azure/avm-res-keyvault-vault/azurerm"
  version = "0.11.0"

  name                          = local.key_vault_name
  location                      = module.resource_group.location
  resource_group_name           = module.resource_group.name
  tenant_id                     = var.tenant_id
  public_network_access_enabled = false
  purge_protection_enabled      = true
  soft_delete_retention_days    = 7
  enable_telemetry              = false
  tags                          = local.tags

  network_acls = {
    bypass         = "None"
    default_action = "Deny"
  }

  role_assignments = {
    foundry_secrets = {
      role_definition_id_or_name       = "Key Vault Secrets User"
      principal_id                     = module.foundry_identity.principal_id
      principal_type                   = "ServicePrincipal"
      skip_service_principal_aad_check = true
    }
  }

  private_endpoints = {
    vault = {
      name                          = "${local.workload_name}-vault-pe"
      subnet_resource_id            = module.spoke_vnet.subnets["private_endpoints"].resource_id
      private_dns_zone_resource_ids = [azurerm_private_dns_zone.foundry["privatelink.vaultcore.azure.net"].id]
    }
  }

  diagnostic_settings = {
    hub = {
      name                  = "${local.workload_name}-vault-diag"
      workspace_resource_id = azurerm_log_analytics_workspace.foundry.id
    }
  }
}
