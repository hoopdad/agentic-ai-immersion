module "private_endpoints_nsg" {
  source  = "Azure/avm-res-network-networksecuritygroup/azurerm"
  version = "0.5.1"

  name                = "nsg-${local.workload_name}-private-endpoints"
  resource_group_name = module.resource_group.name
  location            = module.resource_group.location
  enable_telemetry    = false
  tags                = local.tags
}

module "agent_nsg" {
  source  = "Azure/avm-res-network-networksecuritygroup/azurerm"
  version = "0.5.1"

  name                = "nsg-${local.workload_name}-agents"
  resource_group_name = module.resource_group.name
  location            = module.resource_group.location
  enable_telemetry    = false
  tags                = local.tags
}

module "spoke_vnet" {
  source  = "Azure/avm-res-network-virtualnetwork/azurerm"
  version = "0.22.2"

  name             = local.virtual_network_name
  location         = module.resource_group.location
  parent_id        = module.resource_group.resource_id
  address_space    = [var.virtual_network_address_space]
  enable_telemetry = false
  tags             = local.tags

  subnets = {
    private_endpoints = {
      name                                          = "snet-${local.workload_name}-private-endpoints"
      address_prefixes                              = [var.private_endpoint_subnet_address_prefix]
      default_outbound_access_enabled               = false
      private_endpoint_network_policies             = "Disabled"
      private_link_service_network_policies_enabled = true
      network_security_group = {
        id = module.private_endpoints_nsg.resource_id
      }
    }
    agents = {
      name                            = "snet-${local.workload_name}-agents"
      address_prefixes                = [var.agent_subnet_address_prefix]
      default_outbound_access_enabled = true
      network_security_group = {
        id = module.agent_nsg.resource_id
      }
      delegations = [{
        name = "Microsoft.App-environments"
        service_delegation = {
          name = "Microsoft.App/environments"
        }
      }]
    }
  }
}

resource "azurerm_private_dns_zone" "foundry" {
  for_each = local.private_dns_zones

  name                = each.value
  resource_group_name = module.resource_group.name
  tags                = local.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "spoke" {
  for_each = azurerm_private_dns_zone.foundry

  name                  = "${local.workload_name}-link"
  resource_group_name   = module.resource_group.name
  private_dns_zone_name = each.value.name
  virtual_network_id    = module.spoke_vnet.resource_id
  registration_enabled  = false
  tags                  = local.tags
}
