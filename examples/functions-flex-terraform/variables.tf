variable "environment_name" {
  type        = string
  description = "Name of the environment used to derive a short unique hash for resource names."
  validation {
    condition     = length(var.environment_name) >= 1 && length(var.environment_name) <= 64
    error_message = "environment_name must be between 1 and 64 characters."
  }
}

variable "location" {
  type        = string
  default     = "eastus2"
  description = "Primary Azure region for all resources."
  validation {
    condition = contains([
      "australiaeast", "australiasoutheast", "brazilsouth", "canadacentral",
      "centralindia", "centralus", "eastasia", "eastus", "eastus2", "eastus2euap",
      "francecentral", "germanywestcentral", "italynorth", "japaneast", "koreacentral",
      "northcentralus", "northeurope", "norwayeast", "southafricanorth", "southcentralus",
      "southeastasia", "southindia", "spaincentral", "swedencentral", "uaenorth",
      "uksouth", "ukwest", "westcentralus", "westeurope", "westus", "westus2", "westus3"
    ], var.location)
    error_message = "Unsupported location."
  }
}

variable "vnet_enabled" {
  type        = bool
  description = "If true, deploy VNet integration and private endpoints."
  default     = false
}

variable "principal_id" {
  type        = string
  description = "Principal ID of the deployer (for local-debug RBAC). Optional."
  default     = ""
}

variable "resource_group_name" {
  type    = string
  default = ""
}

variable "api_service_name" {
  type    = string
  default = ""
}

variable "api_user_assigned_identity_name" {
  type    = string
  default = ""
}

variable "application_insights_name" {
  type    = string
  default = ""
}

variable "app_service_plan_name" {
  type    = string
  default = ""
}

variable "log_analytics_name" {
  type    = string
  default = ""
}

variable "storage_account_name" {
  type    = string
  default = ""
}

variable "vnet_name" {
  type    = string
  default = ""
}

variable "existing_app_service_plan_id" {
  type        = string
  default     = ""
  description = "If set, reuse this existing plan instead of creating one."
}

variable "tags" {
  type    = map(string)
  default = {}
}
