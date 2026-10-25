variable "app_name" {
  description = "Display name of the AIPIR API app registration."
  type        = string
  default     = "AIPIR Resilience API"
}

variable "identifier_uri" {
  description = "Application ID URI (token audience), e.g. api://aipir-pilot."
  type        = string
  default     = "api://aipir"
}

variable "group_prefix" {
  description = "Prefix for the security groups created per human role."
  type        = string
  default     = "AIPIR"
}

variable "group_owners" {
  description = "Object IDs of users who own (manage membership of) the AIPIR groups."
  type        = list(string)
  default     = []
}

variable "mfa_policy_state" {
  description = <<-EOT
    Conditional Access state: enabledForReportingButNotEnforced (report-only, default, to confirm
    no lock-out first), enabled, or disabled. Conditional Access requires Entra ID P1 or higher.
  EOT
  type        = string
  default     = "enabledForReportingButNotEnforced"
  validation {
    condition     = contains(["enabled", "disabled", "enabledForReportingButNotEnforced"], var.mfa_policy_state)
    error_message = "mfa_policy_state must be enabled, disabled or enabledForReportingButNotEnforced."
  }
}

variable "break_glass_user_ids" {
  description = "Emergency-access accounts excluded from the MFA policy (Microsoft guidance: keep two, monitor them)."
  type        = list(string)
  default     = []
}
