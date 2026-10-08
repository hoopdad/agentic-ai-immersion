locals {
  foundry_project_endpoint = "https://${local.foundry_account_name}.services.ai.azure.com/api/projects/${local.foundry_project_name}"
  azure_openai_endpoint    = "https://${local.foundry_account_name}.openai.azure.com/"
  search_endpoint          = "https://${local.search_service_name}.search.windows.net"
  blob_storage_url         = "https://${local.storage_account_name}.blob.core.windows.net"

  workshop_environment = {
    APPLICATIONINSIGHTS_CONNECTION_STRING = module.application_insights.connection_string
    AZURE_AI_MODEL_DEPLOYMENT_NAME        = var.model_deployments[var.chat_model_deployment_key].deployment_name
    AZURE_AI_SEARCH_ENDPOINT              = local.search_endpoint
    AZURE_OPENAI_CHAT_DEPLOYMENT_NAME     = var.model_deployments[var.chat_model_deployment_key].deployment_name
    AZURE_OPENAI_ENDPOINT                 = local.azure_openai_endpoint
    AZURE_PROJECT_NAME                    = local.foundry_project_name
    AZURE_RESOURCE_GROUP                  = module.resource_group.name
    AZURE_SUBSCRIPTION_ID                 = var.subscription_id
    EMBEDDING_MODEL_DEPLOYMENT_NAME       = var.model_deployments[var.embedding_model_deployment_key].deployment_name
    FOUNDRY_MODEL                         = var.model_deployments[var.chat_model_deployment_key].deployment_name
    FOUNDRY_PROJECT_ENDPOINT              = local.foundry_project_endpoint
    MARKETPLACE_BLOB_STORAGE_CONTAINER    = var.marketplace_blob_container_name
    MARKETPLACE_BLOB_STORAGE_URL          = local.blob_storage_url
    MARKETPLACE_RESOURCE_SUFFIX           = var.resource_suffix
    PROJECT_RESOURCE_ID                   = azurerm_cognitive_account_project.foundry.id
    TENANT_ID                             = var.tenant_id
  }
}

output "resource_group_name" {
  description = "Resource group containing the workshop deployment."
  value       = module.resource_group.name
}

output "location" {
  description = "Azure region containing the workshop deployment."
  value       = module.resource_group.location
}

output "foundry_account_id" {
  description = "Resource ID of the Microsoft Foundry resource."
  value       = module.foundry_account.resource_id
}

output "foundry_account_endpoint" {
  description = "Microsoft Foundry resource public data-plane endpoint; Microsoft Entra authentication is required."
  value       = module.foundry_account.endpoint
}

output "foundry_project_id" {
  description = "Resource ID of the Microsoft Foundry project."
  value       = azurerm_cognitive_account_project.foundry.id
}

output "foundry_project_endpoint" {
  description = "Microsoft Foundry project public endpoint for FOUNDRY_PROJECT_ENDPOINT; Microsoft Entra authentication is required."
  value       = local.foundry_project_endpoint
}

output "foundry_project_endpoints" {
  description = "Endpoints returned by the Microsoft Foundry project resource."
  value       = azurerm_cognitive_account_project.foundry.endpoints
}

output "azure_openai_endpoint" {
  description = "Azure OpenAI-compatible resource endpoint for AZURE_OPENAI_ENDPOINT."
  value       = local.azure_openai_endpoint
}

output "model_deployment_names" {
  description = "Configured Microsoft Foundry model deployment names by input key."
  value       = { for key, deployment in var.model_deployments : key => deployment.deployment_name }
}

output "chat_model_deployment_name" {
  description = "Chat model deployment selected for the workshop."
  value       = var.model_deployments[var.chat_model_deployment_key].deployment_name
}

output "embedding_model_deployment_name" {
  description = "Embedding model deployment selected for Lab 2."
  value       = var.model_deployments[var.embedding_model_deployment_key].deployment_name
}

output "search_service_id" {
  description = "Resource ID of Azure AI Search."
  value       = azurerm_search_service.foundry.id
}

output "search_endpoint" {
  description = "Azure AI Search public endpoint for AZURE_AI_SEARCH_ENDPOINT; Microsoft Entra authentication is required."
  value       = local.search_endpoint
}

output "cosmos_db_account_id" {
  description = "Resource ID of the Azure Cosmos DB for NoSQL account used by Standard Agent setup."
  value       = azurerm_cosmosdb_account.foundry.id
}

output "storage_account_id" {
  description = "Resource ID of the Azure Storage account."
  value       = module.storage.resource_id
}

output "blob_storage_url" {
  description = "Blob service URL for optional Lab 2 shared conversation history."
  value       = local.blob_storage_url
}

output "marketplace_blob_container_name" {
  description = "Blob container for optional Lab 2 shared conversation history."
  value       = var.marketplace_blob_container_name
}

output "key_vault_id" {
  description = "Resource ID of Azure Key Vault."
  value       = module.key_vault.resource_id
}

output "container_registry_id" {
  description = "Resource ID of Azure Container Registry."
  value       = module.container_registry.resource_id
}

output "container_registry_login_server" {
  description = "Login server of Azure Container Registry."
  value       = module.container_registry.login_server
}

output "user_assigned_identity_id" {
  description = "Resource ID of the user-assigned managed identity used by the Microsoft Foundry resource and project."
  value       = module.foundry_identity.resource_id
}

output "application_insights_id" {
  description = "Resource ID of Application Insights."
  value       = module.application_insights.resource_id
}

output "application_insights_connection_string" {
  description = "Application Insights connection string for hosted-agent tracing."
  value       = module.application_insights.connection_string
  sensitive   = true
}

output "log_analytics_workspace_id" {
  description = "Resource ID of the Log Analytics workspace."
  value       = azurerm_log_analytics_workspace.foundry.id
}

output "workshop_environment" {
  description = "Environment-variable map for the workshop root .env file."
  value       = local.workshop_environment
  sensitive   = true
}

output "workshop_env" {
  description = "Newline-delimited workshop environment values. Treat this output as sensitive."
  value       = join("\n", [for key in sort(keys(local.workshop_environment)) : "${key}=${local.workshop_environment[key]}"])
  sensitive   = true
}
