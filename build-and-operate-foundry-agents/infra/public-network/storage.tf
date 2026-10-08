module "storage" {
  source  = "Azure/avm-res-storage-storageaccount/azurerm"
  version = "0.10.0"

  name                            = local.storage_account_name
  location                        = module.resource_group.location
  parent_id                       = module.resource_group.resource_id
  account_sku_name                = var.storage_account_sku
  allow_nested_items_to_be_public = false
  default_to_oauth_authentication = true
  public_network_access_enabled   = true
  shared_access_key_enabled       = false
  enable_telemetry                = false
  tags                            = local.tags

  containers = {
    foundry = {
      name = "foundry"
    }
    agent_files = {
      name = "agent-files"
    }
    marketplace_history = {
      name = var.marketplace_blob_container_name
    }
  }

  role_assignments = {
    foundry_blob_data = {
      role_definition_id_or_name       = "Storage Blob Data Contributor"
      principal_id                     = module.foundry_identity.principal_id
      principal_type                   = "ServicePrincipal"
      skip_service_principal_aad_check = true
    }
    operator_blob_data = {
      role_definition_id_or_name = "Storage Blob Data Contributor"
      principal_id               = var.operator_principal_id
      principal_type             = var.operator_principal_type
    }
  }

  network_rules = {
    bypass         = ["None"]
    default_action = "Allow"
  }

  diagnostic_settings_storage_account = {
    hub = {
      name                  = "${local.workload_name}-storage-diag"
      metrics               = [{ category = "Transaction" }]
      workspace_resource_id = azurerm_log_analytics_workspace.foundry.id
    }
  }
}
