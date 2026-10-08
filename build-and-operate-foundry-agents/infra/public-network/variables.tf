variable "subscription_id" {
  description = "Azure subscription ID where the workshop resources will be deployed."
  type        = string

  validation {
    condition     = can(regex("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", var.subscription_id))
    error_message = "subscription_id must be a valid GUID."
  }
}

variable "tenant_id" {
  description = "Microsoft Entra tenant ID for the Azure subscription."
  type        = string

  validation {
    condition     = can(regex("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", var.tenant_id))
    error_message = "tenant_id must be a valid GUID."
  }
}

variable "location" {
  description = "Azure region for every regional resource."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9]+$", var.location))
    error_message = "location must be an Azure region name such as eastus2."
  }
}

variable "name_prefix" {
  description = "Lowercase prefix used in generated resource names."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,10}[a-z0-9]$", var.name_prefix))
    error_message = "name_prefix must be 3-12 lowercase letters, numbers, or hyphens; start with a letter and end with a letter or number."
  }
}

variable "resource_suffix" {
  description = "Short lowercase suffix that makes globally scoped resource names unique."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9]{3,6}$", var.resource_suffix))
    error_message = "resource_suffix must be 3-6 lowercase letters or numbers."
  }
}

variable "environment" {
  description = "Environment tag applied to every resource."
  type        = string
  default     = "workshop"

  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]{1,32}$", var.environment))
    error_message = "environment must be 1-32 letters, numbers, periods, underscores, or hyphens."
  }
}

variable "tags" {
  description = "Additional tags merged with the standard deployment tags."
  type        = map(string)
  default     = {}
}

variable "operator_principal_id" {
  description = "Microsoft Entra object ID of the user, group, or service principal that operates the workshop."
  type        = string

  validation {
    condition     = can(regex("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", var.operator_principal_id))
    error_message = "operator_principal_id must be a valid Microsoft Entra object ID."
  }
}

variable "operator_principal_type" {
  description = "Microsoft Entra principal type for operator_principal_id."
  type        = string
  default     = "User"

  validation {
    condition     = contains(["User", "Group", "ServicePrincipal"], var.operator_principal_type)
    error_message = "operator_principal_type must be User, Group, or ServicePrincipal."
  }
}

variable "foundry_project_name" {
  description = "Name of the project created under the Microsoft Foundry resource."
  type        = string
  default     = "marketplace"

  validation {
    condition     = can(regex("^[A-Za-z0-9][A-Za-z0-9_.-]{1,63}$", var.foundry_project_name))
    error_message = "foundry_project_name must be 2-64 letters, numbers, underscores, periods, or hyphens and start with a letter or number."
  }
}

variable "foundry_project_display_name" {
  description = "Display name shown for the Microsoft Foundry project."
  type        = string
  default     = "Build and Operate Foundry Agents"
}

variable "foundry_project_description" {
  description = "Description shown for the Microsoft Foundry project."
  type        = string
  default     = "Public-network Microsoft Foundry project for the Build and Operate Foundry Agents workshop."
}

variable "validation_resource_group_name" {
  description = "Optional existing resource group name used only by post-deploy-validation.sh when it differs from this root's naming convention."
  type        = string
  default     = null
  nullable    = true
}

variable "validation_foundry_account_name" {
  description = "Optional existing Foundry account name used only by post-deploy-validation.sh when it differs from this root's naming convention."
  type        = string
  default     = null
  nullable    = true
}

variable "allowed_public_ipv4_cidrs" {
  description = "Nonempty public IPv4 source allowlist for Key Vault and Container Registry operator/CI access. Use canonical CIDRs; /32 denotes one address. Foundry and its data services intentionally allow all public sources."
  type        = set(string)
  nullable    = false

  validation {
    condition     = length(var.allowed_public_ipv4_cidrs) > 0
    error_message = "allowed_public_ipv4_cidrs must contain at least one public IPv4 CIDR for Key Vault and Container Registry."
  }

  validation {
    condition = alltrue([
      for cidr in var.allowed_public_ipv4_cidrs : try(
        can(cidrnetmask(cidr)) &&
        tonumber(split("/", cidr)[1]) > 0 &&
        cidrhost(cidr, 0) == split("/", cidr)[0] &&
        alltrue([
          for reserved in local.reserved_ipv4_ranges :
          sum([for index, octet in split(".", cidrhost(cidr, -1)) : tonumber(octet) * pow(256, 3 - index)]) < reserved.first ||
          sum([for index, octet in split(".", cidrhost(cidr, 0)) : tonumber(octet) * pow(256, 3 - index)]) > reserved.last
        ]),
        false
      )
    ])
    error_message = "Use canonical, globally routable IPv4 CIDRs only; wildcard, private, loopback, link-local, shared, documentation, multicast and reserved ranges are not allowed."
  }
}

variable "storage_account_sku" {
  description = "Replication SKU for the Azure Storage account."
  type        = string
  default     = "Standard_LRS"

  validation {
    condition     = contains(["Standard_LRS", "Standard_ZRS", "Standard_GRS", "Standard_GZRS"], var.storage_account_sku)
    error_message = "storage_account_sku must be Standard_LRS, Standard_ZRS, Standard_GRS, or Standard_GZRS."
  }
}

variable "marketplace_blob_container_name" {
  description = "Blob container used for optional Lab 2 shared conversation history."
  type        = string
  default     = "marketplace-history"

  validation {
    condition     = can(regex("^[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])$", var.marketplace_blob_container_name))
    error_message = "marketplace_blob_container_name must be a valid 3-63 character Azure Blob container name."
  }
}

variable "search_sku" {
  description = "Azure AI Search pricing tier. Standard Agent setup requires Basic or higher."
  type        = string
  default     = "basic"

  validation {
    condition     = contains(["basic", "standard", "standard2", "standard3"], var.search_sku)
    error_message = "search_sku must be basic, standard, standard2, or standard3."
  }
}

variable "search_semantic_search_sku" {
  description = "Azure AI Search semantic ranker billing plan."
  type        = string
  default     = "free"

  validation {
    condition     = contains(["free", "standard"], var.search_semantic_search_sku)
    error_message = "search_semantic_search_sku must be free or standard."
  }
}

variable "search_replica_count" {
  description = "Number of Azure AI Search replicas."
  type        = number
  default     = 1

  validation {
    condition     = contains([1, 2, 3, 4, 6, 12], var.search_replica_count)
    error_message = "search_replica_count must be 1, 2, 3, 4, 6, or 12."
  }
}

variable "search_partition_count" {
  description = "Number of Azure AI Search partitions."
  type        = number
  default     = 1

  validation {
    condition     = contains([1, 2, 3, 4, 6, 12], var.search_partition_count)
    error_message = "search_partition_count must be 1, 2, 3, 4, 6, or 12."
  }
}

variable "cosmos_free_tier_enabled" {
  description = "Whether to request the Azure Cosmos DB free tier. A subscription can have only one free-tier account."
  type        = bool
  default     = false
}

variable "cosmos_zone_redundant" {
  description = "Whether the Azure Cosmos DB regional replica uses availability zones."
  type        = bool
  default     = false
}

variable "application_insights_retention_in_days" {
  description = "Application Insights retention period."
  type        = number
  default     = 30

  validation {
    condition     = contains([30, 60, 90, 120, 180, 270, 365, 550, 730], var.application_insights_retention_in_days)
    error_message = "application_insights_retention_in_days must be a supported Application Insights retention value."
  }
}

variable "application_insights_daily_data_cap_in_gb" {
  description = "Daily Application Insights ingestion cap in GB."
  type        = number
  default     = 1

  validation {
    condition     = var.application_insights_daily_data_cap_in_gb > 0
    error_message = "application_insights_daily_data_cap_in_gb must be greater than zero."
  }
}

variable "model_deployments" {
  description = "Model deployments created on the Microsoft Foundry resource. Confirm regional availability and quota before applying."
  type = map(object({
    deployment_name        = string
    model_name             = string
    model_version          = string
    model_format           = optional(string, "OpenAI")
    sku_name               = string
    capacity               = number
    version_upgrade_option = optional(string, "NoAutoUpgrade")
  }))

  validation {
    condition     = length(var.model_deployments) > 0
    error_message = "model_deployments must contain at least one deployment."
  }

  validation {
    condition = alltrue([
      for deployment in values(var.model_deployments) :
      can(regex("^[A-Za-z0-9][A-Za-z0-9_.-]{1,63}$", deployment.deployment_name)) &&
      deployment.capacity > 0 &&
      contains(
        ["NoAutoUpgrade", "OnceNewDefaultVersionAvailable", "OnceCurrentVersionExpired"],
        deployment.version_upgrade_option
      )
    ])
    error_message = "Each model deployment needs a valid name, positive capacity, and supported version_upgrade_option."
  }
}

variable "chat_model_deployment_key" {
  description = "Key in model_deployments used as the workshop chat model."
  type        = string
  default     = "gpt_5_4_mini"
}

variable "embedding_model_deployment_key" {
  description = "Key in model_deployments used by Lab 2 for 3072-dimension embeddings."
  type        = string
  default     = "text_embedding_3_large"
}

variable "capability_host_name" {
  description = "Name of the project capability host for Standard Agent setup."
  type        = string
  default     = "caphostproj"

  validation {
    condition     = can(regex("^[A-Za-z0-9][A-Za-z0-9_.-]{1,63}$", var.capability_host_name))
    error_message = "capability_host_name must be 2-64 letters, numbers, underscores, periods, or hyphens."
  }
}
