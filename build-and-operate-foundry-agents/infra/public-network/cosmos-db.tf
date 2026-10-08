resource "azurerm_cosmosdb_account" "foundry" {
  name                = local.cosmos_db_account_name
  location            = module.resource_group.location
  resource_group_name = module.resource_group.name
  offer_type          = "Standard"
  kind                = "GlobalDocumentDB"

  automatic_failover_enabled            = false
  free_tier_enabled                     = var.cosmos_free_tier_enabled
  local_authentication_enabled          = false
  multiple_write_locations_enabled      = false
  public_network_access_enabled         = true
  ip_range_filter                       = []
  network_acl_bypass_for_azure_services = false
  tags                                  = local.tags

  consistency_policy {
    consistency_level = "Session"
  }

  geo_location {
    location          = module.resource_group.location
    failover_priority = 0
    zone_redundant    = var.cosmos_zone_redundant
  }
}

resource "azurerm_role_assignment" "identity_cosmos_db_operator" {
  scope                            = azurerm_cosmosdb_account.foundry.id
  role_definition_name             = "Cosmos DB Operator"
  principal_id                     = module.foundry_identity.principal_id
  principal_type                   = "ServicePrincipal"
  skip_service_principal_aad_check = true
}
