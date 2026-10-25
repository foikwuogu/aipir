output "api_client_id" { value = azuread_application.api.client_id }
output "audience" { value = var.identifier_uri }
output "relay_client_id" { value = azuread_application.relay.client_id }
output "group_object_ids" {
  description = "Object IDs per human role, for AKS RBAC bindings (aipir-k8s-rbac.group_bindings)."
  value       = { for k, g in azuread_group.role : k => g.object_id }
}
output "aipir_env" {
  description = "Environment values for the AIPIR service (rs256 mode)."
  value = {
    AIPIR_AUTH_MODE = "rs256"
    AIPIR_AUDIENCE  = var.identifier_uri
    AIPIR_JWKS_URL  = "https://login.microsoftonline.com/<tenant-id>/discovery/v2.0/keys"
    AIPIR_ISSUER    = "https://login.microsoftonline.com/<tenant-id>/v2.0"
  }
}
