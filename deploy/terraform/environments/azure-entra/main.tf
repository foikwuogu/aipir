# Creates the AIPIR identity and access controls in a Microsoft Entra ID tenant.
#   az login --tenant <tenant-id>   (an account allowed to create apps, groups and CA policies)
#   terraform init && terraform plan && terraform apply
terraform {
  required_version = ">= 1.6"
  required_providers {
    azuread = { source = "hashicorp/azuread", version = "~> 3.0" }
  }
}

provider "azuread" {
  tenant_id = var.tenant_id
}

variable "tenant_id" {
  description = "Entra ID tenant ID."
  type        = string
}

variable "group_owners" {
  type    = list(string)
  default = []
}

variable "break_glass_user_ids" {
  type    = list(string)
  default = []
}

module "zero_trust" {
  source               = "../../modules/entra-zero-trust"
  identifier_uri       = "api://aipir-pilot"
  group_owners         = var.group_owners
  break_glass_user_ids = var.break_glass_user_ids
  mfa_policy_state     = "enabledForReportingButNotEnforced"
}

output "aipir_env" { value = module.zero_trust.aipir_env }
output "group_object_ids" { value = module.zero_trust.group_object_ids }
output "relay_client_id" { value = module.zero_trust.relay_client_id }
