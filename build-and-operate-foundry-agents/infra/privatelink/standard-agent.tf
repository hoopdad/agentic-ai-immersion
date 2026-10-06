data "azapi_resource" "foundry_project" {
  type                   = "Microsoft.CognitiveServices/accounts/projects@2026-03-01"
  resource_id            = azurerm_cognitive_account_project.foundry.id
  response_export_values = ["properties.internalId"]
}

locals {
  project_internal_id = replace(data.azapi_resource.foundry_project.output.properties.internalId, "-", "")
  project_workspace_id = format(
    "%s-%s-%s-%s-%s",
    substr(local.project_internal_id, 0, 8),
    substr(local.project_internal_id, 8, 4),
    substr(local.project_internal_id, 12, 4),
    substr(local.project_internal_id, 16, 4),
    substr(local.project_internal_id, 20, 12),
  )
}

check "project_internal_id" {
  assert {
    condition     = length(local.project_internal_id) == 32
    error_message = "Microsoft Foundry did not return the 32-character project internal ID required for scoped agent-storage access."
  }
}

resource "azapi_resource" "foundry_project_cosmos_db_connection" {
  type                      = "Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview"
  name                      = azurerm_cosmosdb_account.foundry.name
  parent_id                 = azurerm_cognitive_account_project.foundry.id
  schema_validation_enabled = false

  body = {
    properties = {
      authType      = "AAD"
      category      = "CosmosDB"
      isSharedToAll = true
      target        = azurerm_cosmosdb_account.foundry.endpoint
      metadata = {
        ApiType    = "Azure"
        ResourceId = azurerm_cosmosdb_account.foundry.id
        location   = module.resource_group.location
      }
    }
  }
}

resource "azapi_resource" "foundry_project_storage_connection" {
  type                      = "Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview"
  name                      = module.storage.name
  parent_id                 = azurerm_cognitive_account_project.foundry.id
  schema_validation_enabled = false

  body = {
    properties = {
      authType      = "AAD"
      category      = "AzureStorageAccount"
      isSharedToAll = true
      target        = "https://${module.storage.name}.blob.core.windows.net/"
      metadata = {
        ApiType    = "Azure"
        ResourceId = module.storage.resource_id
        location   = module.resource_group.location
      }
    }
  }
}

resource "azapi_resource" "foundry_project_search_connection" {
  type                      = "Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview"
  name                      = azurerm_search_service.foundry.name
  parent_id                 = azurerm_cognitive_account_project.foundry.id
  schema_validation_enabled = false

  body = {
    properties = {
      authType      = "AAD"
      category      = "CognitiveSearch"
      isSharedToAll = true
      target        = "https://${azurerm_search_service.foundry.name}.search.windows.net"
      metadata = {
        ApiType    = "Azure"
        ApiVersion = "2025-11-01-preview"
        ResourceId = azurerm_search_service.foundry.id
        location   = module.resource_group.location
      }
    }
  }
}

resource "time_sleep" "standard_agent_rbac" {
  create_duration = "60s"

  depends_on = [
    module.storage,
    azurerm_role_assignment.identity_cosmos_db_operator,
    azurerm_role_assignment.identity_search_index_data_contributor,
    azurerm_role_assignment.identity_search_service_contributor,
  ]
}

resource "azapi_resource" "foundry_project_capability_host" {
  type                      = "Microsoft.CognitiveServices/accounts/projects/capabilityHosts@2025-04-01-preview"
  name                      = var.capability_host_name
  parent_id                 = azurerm_cognitive_account_project.foundry.id
  schema_validation_enabled = false

  body = {
    properties = {
      capabilityHostKind       = "Agents"
      storageConnections       = [azapi_resource.foundry_project_storage_connection.name]
      threadStorageConnections = [azapi_resource.foundry_project_cosmos_db_connection.name]
      vectorStoreConnections   = [azapi_resource.foundry_project_search_connection.name]
    }
  }

  depends_on = [
    azurerm_private_endpoint.cosmos_db,
    azurerm_private_endpoint.search,
    azapi_resource.foundry_account_dns_zone_group,
    time_sleep.standard_agent_rbac,
  ]
}

resource "azurerm_cosmosdb_sql_role_assignment" "identity_data_contributor" {
  resource_group_name = module.resource_group.name
  account_name        = azurerm_cosmosdb_account.foundry.name
  role_definition_id  = "${azurerm_cosmosdb_account.foundry.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002"
  principal_id        = module.foundry_identity.principal_id
  scope               = azurerm_cosmosdb_account.foundry.id

  depends_on = [azapi_resource.foundry_project_capability_host]
}

resource "azurerm_role_assignment" "identity_agent_storage_owner" {
  scope                            = module.storage.resource_id
  role_definition_name             = "Storage Blob Data Owner"
  principal_id                     = module.foundry_identity.principal_id
  principal_type                   = "ServicePrincipal"
  skip_service_principal_aad_check = true
  condition_version                = "2.0"
  condition                        = <<-EOT
  (
    (
      !(ActionMatches{'Microsoft.Storage/storageAccounts/blobServices/containers/blobs/tags/read'})
      AND !(ActionMatches{'Microsoft.Storage/storageAccounts/blobServices/containers/blobs/filter/action'})
      AND !(ActionMatches{'Microsoft.Storage/storageAccounts/blobServices/containers/blobs/tags/write'})
    )
    OR
    (
      @Resource[Microsoft.Storage/storageAccounts/blobServices/containers:name] StringStartsWithIgnoreCase '${local.project_workspace_id}'
      AND @Resource[Microsoft.Storage/storageAccounts/blobServices/containers:name] StringLikeIgnoreCase '*-azureml-agent'
    )
  )
  EOT

  depends_on = [azapi_resource.foundry_project_capability_host]
}
