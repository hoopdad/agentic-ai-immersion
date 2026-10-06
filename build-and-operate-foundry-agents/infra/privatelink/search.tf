resource "azurerm_search_service" "foundry" {
  name                          = local.search_service_name
  resource_group_name           = module.resource_group.name
  location                      = module.resource_group.location
  sku                           = var.search_sku
  replica_count                 = var.search_replica_count
  partition_count               = var.search_partition_count
  local_authentication_enabled  = false
  public_network_access_enabled = false
  semantic_search_sku           = var.search_semantic_search_sku
  tags                          = local.tags

  identity {
    type = "SystemAssigned"
  }
}

resource "azurerm_private_endpoint" "search" {
  name                = "${local.workload_name}-search-pe"
  location            = module.resource_group.location
  resource_group_name = module.resource_group.name
  subnet_id           = module.spoke_vnet.subnets["private_endpoints"].resource_id
  tags                = local.tags

  private_service_connection {
    name                           = "${local.workload_name}-search-psc"
    is_manual_connection           = false
    private_connection_resource_id = azurerm_search_service.foundry.id
    subresource_names              = ["searchService"]
  }

  private_dns_zone_group {
    name                 = "search"
    private_dns_zone_ids = [azurerm_private_dns_zone.foundry["privatelink.search.windows.net"].id]
  }
}

resource "azurerm_role_assignment" "identity_search_service_contributor" {
  scope                            = azurerm_search_service.foundry.id
  role_definition_name             = "Search Service Contributor"
  principal_id                     = module.foundry_identity.principal_id
  principal_type                   = "ServicePrincipal"
  skip_service_principal_aad_check = true
}

resource "azurerm_role_assignment" "identity_search_index_data_contributor" {
  scope                            = azurerm_search_service.foundry.id
  role_definition_name             = "Search Index Data Contributor"
  principal_id                     = module.foundry_identity.principal_id
  principal_type                   = "ServicePrincipal"
  skip_service_principal_aad_check = true
}

resource "azurerm_role_assignment" "operator_search_service_contributor" {
  scope                = azurerm_search_service.foundry.id
  role_definition_name = "Search Service Contributor"
  principal_id         = var.operator_principal_id
  principal_type       = var.operator_principal_type
}

resource "azurerm_role_assignment" "operator_search_index_data_contributor" {
  scope                = azurerm_search_service.foundry.id
  role_definition_name = "Search Index Data Contributor"
  principal_id         = var.operator_principal_id
  principal_type       = var.operator_principal_type
}

resource "azurerm_role_assignment" "search_identity_openai_user" {
  scope                            = module.foundry_account.resource_id
  role_definition_name             = "Cognitive Services OpenAI User"
  principal_id                     = azurerm_search_service.foundry.identity[0].principal_id
  principal_type                   = "ServicePrincipal"
  skip_service_principal_aad_check = true
}

resource "azurerm_role_assignment" "search_identity_cognitive_services_user" {
  scope                            = module.foundry_account.resource_id
  role_definition_name             = "Cognitive Services User"
  principal_id                     = azurerm_search_service.foundry.identity[0].principal_id
  principal_type                   = "ServicePrincipal"
  skip_service_principal_aad_check = true
}

resource "azurerm_monitor_diagnostic_setting" "search" {
  name                       = "${local.workload_name}-search-diag"
  target_resource_id         = azurerm_search_service.foundry.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.foundry.id

  enabled_log {
    category = "OperationLogs"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}
