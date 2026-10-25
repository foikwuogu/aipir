variable "namespace" {
  description = "AIPIR namespace."
  type        = string
}

variable "group_bindings" {
  description = <<-EOT
    Identity-provider groups bound to AIPIR cluster roles (Kubernetes RBAC for people).
    On AKS with Entra ID integration, use the group object IDs from the entra-zero-trust module.
  EOT
  type = object({
    viewers   = list(string)
    operators = list(string)
    admins    = list(string)
  })
  default = { viewers = [], operators = [], admins = [] }
}
