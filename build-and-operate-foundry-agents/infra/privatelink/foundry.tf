module "foundry_account" {
  source  = "Azure/avm-res-cognitiveservices-account/azurerm"
  version = "0.11.1"

  name                               = local.foundry_account_name
  location                           = module.resource_group.location
  parent_id                          = module.resource_group.resource_id
  kind                               = "AIServices"
  sku_name                           = "S0"
  allow_project_management           = true
  custom_subdomain_name              = local.foundry_account_name
  deployment_serialization_enabled   = true
  local_auth_enabled                 = false
  outbound_network_access_restricted = true
  public_network_access_enabled      = false
  enable_telemetry                   = false
  tags                               = local.tags

  managed_identities = {
    system_assigned            = false
    user_assigned_resource_ids = [module.foundry_identity.resource_id]
  }

  network_acls = {
    bypass         = "AzureServices"
    default_action = "Deny"
  }

  storage = [{
    storage_account_id = module.storage.resource_id
    identity_client_id = module.foundry_identity.client_id
  }]

  cognitive_deployments = local.model_deployments

  network_injections = {
    subnet_id                         = module.spoke_vnet.subnets["agents"].resource_id
    scenario                          = "agent"
    microsoft_managed_network_enabled = false
  }

  private_endpoints_manage_dns_zone_group = false
  private_endpoints = {
    account = {
      name               = "${local.workload_name}-account-pe"
      subnet_resource_id = module.spoke_vnet.subnets["private_endpoints"].resource_id
      private_dns_zone_resource_ids = [
        azurerm_private_dns_zone.foundry["privatelink.cognitiveservices.azure.com"].id,
        azurerm_private_dns_zone.foundry["privatelink.openai.azure.com"].id,
        azurerm_private_dns_zone.foundry["privatelink.services.ai.azure.com"].id,
      ]
    }
  }

  diagnostic_settings = {
    hub = {
      name                  = "${local.workload_name}-account-diag"
      log_categories        = ["Audit", "AzureOpenAIRequestUsage", "ManagedNetworkEvent", "RequestResponse"]
      log_groups            = []
      metric_categories     = ["AllMetrics"]
      workspace_resource_id = azurerm_log_analytics_workspace.foundry.id
    }
  }

  depends_on = [
    azapi_resource_action.purge_foundry_account,
    module.storage,
  ]
}

resource "azapi_resource_action" "purge_foundry_account" {
  type        = "Microsoft.CognitiveServices/locations/resourceGroups/deletedAccounts@2021-04-30"
  resource_id = "/subscriptions/${var.subscription_id}/providers/Microsoft.CognitiveServices/locations/${var.location}/resourceGroups/${module.resource_group.name}/deletedAccounts/${local.foundry_account_name}"
  method      = "DELETE"
  when        = "destroy"

  depends_on = [time_sleep.foundry_purge_cooldown]
}

resource "time_sleep" "foundry_purge_cooldown" {
  destroy_duration = "900s"

  depends_on = [module.spoke_vnet]
}

resource "azapi_resource" "foundry_account_dns_zone_group" {
  type      = "Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01"
  name      = "default"
  parent_id = module.foundry_account.private_endpoints["account"].id
  body = {
    properties = {
      privateDnsZoneConfigs = [
        {
          name = "cognitive-services"
          properties = {
            privateDnsZoneId = azurerm_private_dns_zone.foundry["privatelink.cognitiveservices.azure.com"].id
          }
        },
        {
          name = "openai"
          properties = {
            privateDnsZoneId = azurerm_private_dns_zone.foundry["privatelink.openai.azure.com"].id
          }
        },
        {
          name = "foundry-services"
          properties = {
            privateDnsZoneId = azurerm_private_dns_zone.foundry["privatelink.services.ai.azure.com"].id
          }
        },
      ]
    }
  }
}

resource "azurerm_cognitive_account_project" "foundry" {
  name                 = local.foundry_project_name
  cognitive_account_id = module.foundry_account.resource_id
  location             = module.resource_group.location
  display_name         = var.foundry_project_display_name
  description          = var.foundry_project_description
  tags                 = local.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [module.foundry_identity.resource_id]
  }
}

resource "azurerm_role_assignment" "identity_openai_user" {
  scope                            = module.foundry_account.resource_id
  role_definition_name             = "Cognitive Services OpenAI User"
  principal_id                     = module.foundry_identity.principal_id
  principal_type                   = "ServicePrincipal"
  skip_service_principal_aad_check = true
}

resource "azurerm_role_assignment" "identity_foundry_user" {
  scope                            = module.foundry_account.resource_id
  role_definition_name             = "Foundry User"
  principal_id                     = module.foundry_identity.principal_id
  principal_type                   = "ServicePrincipal"
  skip_service_principal_aad_check = true
}

resource "azurerm_role_assignment" "operator_openai_user" {
  scope                = module.foundry_account.resource_id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = var.operator_principal_id
  principal_type       = var.operator_principal_type
}

resource "azurerm_role_assignment" "operator_foundry_owner" {
  scope                = module.foundry_account.resource_id
  role_definition_name = "Foundry Owner"
  principal_id         = var.operator_principal_id
  principal_type       = var.operator_principal_type
}

resource "azurerm_role_assignment" "operator_foundry_project_manager" {
  scope                = azurerm_cognitive_account_project.foundry.id
  role_definition_name = "Foundry Project Manager"
  principal_id         = var.operator_principal_id
  principal_type       = var.operator_principal_type
}
