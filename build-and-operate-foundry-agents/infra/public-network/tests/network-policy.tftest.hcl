mock_provider "azurerm" {
  mock_resource "azurerm_cosmosdb_account" {
    defaults = {
      id       = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-network-test/providers/Microsoft.DocumentDB/databaseAccounts/cosmos-network-test"
      endpoint = "https://cosmos-network-test.documents.azure.com:443/"
    }
  }
  mock_resource "azurerm_search_service" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-network-test/providers/Microsoft.Search/searchServices/srch-network-test"
      identity = {
        principal_id = "00000000-0000-0000-0000-000000000006"
        tenant_id    = "00000000-0000-0000-0000-000000000002"
      }
    }
  }
  mock_resource "azurerm_cognitive_account_project" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-network-test/providers/Microsoft.CognitiveServices/accounts/ai-network-test/projects/marketplace"
    }
  }
  mock_resource "azurerm_log_analytics_workspace" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-network-test/providers/Microsoft.OperationalInsights/workspaces/log-network-test"
    }
  }
}
mock_provider "azapi" {}
mock_provider "time" {}

override_module {
  target = module.resource_group
  outputs = {
    name        = "rg-network-test"
    location    = "eastus2"
    resource_id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-network-test"
  }
}

override_module {
  target = module.foundry_identity
  outputs = {
    resource_id  = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-network-test/providers/Microsoft.ManagedIdentity/userAssignedIdentities/id-network-test"
    client_id    = "00000000-0000-0000-0000-000000000002"
    principal_id = "00000000-0000-0000-0000-000000000003"
  }
}

override_module {
  target = module.storage
  outputs = {
    name        = "stnetworktest"
    resource_id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-network-test/providers/Microsoft.Storage/storageAccounts/stnetworktest"
  }
}

override_module {
  target = module.foundry_account
  outputs = {
    resource_id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-network-test/providers/Microsoft.CognitiveServices/accounts/ai-network-test"
    endpoint    = "https://ai-network-test.cognitiveservices.azure.com/"
  }
}

override_module {
  target = module.key_vault
  outputs = {
    resource_id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-network-test/providers/Microsoft.KeyVault/vaults/kv-network-test"
  }
}

override_module {
  target = module.container_registry
  outputs = {
    resource_id  = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-network-test/providers/Microsoft.ContainerRegistry/registries/crnetworktest"
    login_server = "crnetworktest.azurecr.io"
  }
}

override_module {
  target = module.application_insights
  outputs = {
    resource_id       = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-network-test/providers/Microsoft.Insights/components/appi-network-test"
    connection_string = "InstrumentationKey=00000000-0000-0000-0000-000000000004"
  }
}

override_data {
  target = data.azapi_resource.foundry_project
  values = {
    output = {
      properties = {
        internalId = "00000000-0000-0000-0000-000000000005"
      }
    }
  }
}

variables {
  subscription_id           = "00000000-0000-0000-0000-000000000001"
  tenant_id                 = "00000000-0000-0000-0000-000000000002"
  operator_principal_id     = "00000000-0000-0000-0000-000000000003"
  location                  = "eastus2"
  name_prefix               = "network"
  resource_suffix           = "test"
  allowed_public_ipv4_cidrs = ["8.8.8.8/32", "9.9.9.8/31", "11.0.0.0/24"]
  model_deployments = {
    gpt_5_4_mini = {
      deployment_name = "test-chat"
      model_name      = "test-chat"
      model_version   = "1"
      sku_name        = "GlobalStandard"
      capacity        = 1
    }
    text_embedding_3_large = {
      deployment_name = "test-embedding"
      model_name      = "test-embedding"
      model_version   = "1"
      sku_name        = "GlobalStandard"
      capacity        = 1
    }
  }
}

run "public_network_policy" {
  command = apply

  assert {
    condition     = azurerm_cosmosdb_account.foundry.public_network_access_enabled && azurerm_search_service.foundry.public_network_access_enabled
    error_message = "Cosmos DB and Search must use public endpoints."
  }

  assert {
    condition     = length(azurerm_cosmosdb_account.foundry.ip_range_filter) == 0 && length(azurerm_search_service.foundry.allowed_ips) == 0
    error_message = "Cosmos DB and Search must accept managed-runtime public egress without a source-IP firewall."
  }

  assert {
    condition     = !azurerm_cosmosdb_account.foundry.local_authentication_enabled && !azurerm_search_service.foundry.local_authentication_enabled
    error_message = "Public networking must not enable key authentication."
  }

  assert {
    condition     = azurerm_log_analytics_workspace.foundry.internet_ingestion_enabled && azurerm_log_analytics_workspace.foundry.internet_query_enabled
    error_message = "Monitor must remain reachable without private networking."
  }
}

run "reject_empty_allowlist" {
  command = plan
  variables {
    allowed_public_ipv4_cidrs = []
  }
  expect_failures = [var.allowed_public_ipv4_cidrs]
}

run "reject_wildcard" {
  command = plan
  variables {
    allowed_public_ipv4_cidrs = ["0.0.0.0/0"]
  }
  expect_failures = [var.allowed_public_ipv4_cidrs]
}

run "reject_private_network" {
  command = plan
  variables {
    allowed_public_ipv4_cidrs = ["10.0.0.0/8"]
  }
  expect_failures = [var.allowed_public_ipv4_cidrs]
}

run "reject_overlapping_private_range" {
  command = plan
  variables {
    allowed_public_ipv4_cidrs = ["8.0.0.0/6"]
  }
  expect_failures = [var.allowed_public_ipv4_cidrs]
}

run "reject_ipv6" {
  command = plan
  variables {
    allowed_public_ipv4_cidrs = ["2001:4860:4860::8888/128"]
  }
  expect_failures = [var.allowed_public_ipv4_cidrs]
}

run "reject_malformed_cidr" {
  command = plan
  variables {
    allowed_public_ipv4_cidrs = ["not-an-ip"]
  }
  expect_failures = [var.allowed_public_ipv4_cidrs]
}

run "reject_noncanonical_cidr" {
  command = plan
  variables {
    allowed_public_ipv4_cidrs = ["11.0.0.7/24"]
  }
  expect_failures = [var.allowed_public_ipv4_cidrs]
}

run "reject_loopback" {
  command = plan
  variables {
    allowed_public_ipv4_cidrs = ["127.0.0.1/32"]
  }
  expect_failures = [var.allowed_public_ipv4_cidrs]
}

run "reject_documentation_range" {
  command = plan
  variables {
    allowed_public_ipv4_cidrs = ["203.0.113.0/24"]
  }
  expect_failures = [var.allowed_public_ipv4_cidrs]
}
