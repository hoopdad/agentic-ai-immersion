resource "azurerm_log_analytics_workspace" "foundry" {
  name                       = local.log_analytics_workspace_name
  location                   = module.resource_group.location
  resource_group_name        = module.resource_group.name
  sku                        = "PerGB2018"
  retention_in_days          = var.application_insights_retention_in_days
  internet_ingestion_enabled = true
  internet_query_enabled     = true
  tags                       = local.tags
}

module "application_insights" {
  source  = "Azure/avm-res-insights-component/azurerm"
  version = "0.4.0"

  name                       = local.application_insights_name
  location                   = module.resource_group.location
  resource_group_name        = module.resource_group.name
  workspace_id               = azurerm_log_analytics_workspace.foundry.id
  application_type           = "web"
  retention_in_days          = var.application_insights_retention_in_days
  daily_data_cap_in_gb       = var.application_insights_daily_data_cap_in_gb
  internet_ingestion_enabled = true
  internet_query_enabled     = true
  enable_telemetry           = false
  tags                       = local.tags

  role_assignments = {
    log_analytics_reader = {
      role_definition_id_or_name       = "Log Analytics Reader"
      principal_id                     = module.foundry_identity.principal_id
      principal_type                   = "ServicePrincipal"
      skip_service_principal_aad_check = true
    }
    privileged_monitoring_data_reader = {
      role_definition_id_or_name       = "Privileged Monitoring Data Reader"
      principal_id                     = module.foundry_identity.principal_id
      principal_type                   = "ServicePrincipal"
      skip_service_principal_aad_check = true
    }
    identity_monitoring_metrics_publisher = {
      role_definition_id_or_name       = "Monitoring Metrics Publisher"
      principal_id                     = module.foundry_identity.principal_id
      principal_type                   = "ServicePrincipal"
      skip_service_principal_aad_check = true
    }
    operator_monitoring_reader = {
      role_definition_id_or_name = "Monitoring Reader"
      principal_id               = var.operator_principal_id
      principal_type             = var.operator_principal_type
    }
    operator_monitoring_metrics_publisher = {
      role_definition_id_or_name = "Monitoring Metrics Publisher"
      principal_id               = var.operator_principal_id
      principal_type             = var.operator_principal_type
    }
  }

  diagnostic_settings = {
    hub = {
      name                  = "${local.application_insights_name}-diag"
      workspace_resource_id = azurerm_log_analytics_workspace.foundry.id
    }
  }
}

resource "azapi_resource" "foundry_account_application_insights_connection" {
  type      = "Microsoft.CognitiveServices/accounts/connections@2026-07-15-preview"
  name      = local.application_insights_name
  parent_id = module.foundry_account.resource_id
  body = {
    properties = {
      authType      = "ApiKey"
      category      = "AppInsights"
      isSharedToAll = true
      metadata = {
        ApiType    = "Azure"
        ResourceId = module.application_insights.resource_id
      }
      target = module.application_insights.resource_id
    }
  }
  sensitive_body = {
    properties = {
      credentials = {
        key = module.application_insights.connection_string
      }
    }
  }
  schema_validation_enabled = false
}

resource "azapi_resource" "foundry_project_application_insights_connection" {
  type      = "Microsoft.CognitiveServices/accounts/projects/connections@2026-07-15-preview"
  name      = local.application_insights_name
  parent_id = azurerm_cognitive_account_project.foundry.id
  body = {
    properties = {
      authType      = "ApiKey"
      category      = "AppInsights"
      isSharedToAll = true
      metadata = {
        ApiType    = "Azure"
        ResourceId = module.application_insights.resource_id
      }
      target = module.application_insights.resource_id
    }
  }
  sensitive_body = {
    properties = {
      credentials = {
        key = module.application_insights.connection_string
      }
    }
  }
  schema_validation_enabled = false
}
