module "foundry_identity" {
  source  = "Azure/avm-res-managedidentity-userassignedidentity/azurerm"
  version = "0.5.2"

  name                = local.identity_name
  location            = module.resource_group.location
  resource_group_name = module.resource_group.name
  enable_telemetry    = false
  tags                = local.tags
}
