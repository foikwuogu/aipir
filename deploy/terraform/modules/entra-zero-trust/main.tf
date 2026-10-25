# Microsoft Entra ID (Azure AD) identity for AIPIR - the IAM part of Zero-Trust:
#   * one app registration whose app roles are exactly the roles in deploy/zero-trust/rbac_policy.yaml
#   * a security group per human role, assigned to its app role (assignment required: no role, no token)
#   * a workload identity (app-only) for Alertmanager holding only aipir.alert-relay
#   * a Conditional Access policy requiring MFA for every human sign-in to the AIPIR API
# No client secrets are created here; give the relay a certificate or federated credential.

locals {
  human_roles = {
    "aipir.viewer"            = "View AIPIR dashboards, metrics and status"
    "aipir.operator"          = "Request recoveries and acknowledge alerts (MFA)"
    "aipir.recovery-approver" = "Approve recoveries requested by someone else (MFA, two-person rule)"
    "aipir.admin"             = "Manage AIPIR configuration and drift baselines (MFA)"
  }
  workload_roles = {
    "aipir.alert-relay"     = "Alertmanager webhook: submit recovery requests"
    "aipir.metrics-scraper" = "Prometheus / OTel Collector: read metrics"
  }
  all_roles = merge(
    { for k, v in local.human_roles : k => { desc = v, types = ["User"] } },
    { for k, v in local.workload_roles : k => { desc = v, types = ["Application"] } },
  )
}

resource "azuread_application" "api" {
  display_name     = var.app_name
  identifier_uris  = [var.identifier_uri]
  sign_in_audience = "AzureADMyOrg"

  api {
    requested_access_token_version = 2
  }

  dynamic "app_role" {
    for_each = local.all_roles
    content {
      id                   = uuidv5("url", "${var.identifier_uri}/roles/${app_role.key}")
      value                = app_role.key
      display_name         = app_role.key
      description          = app_role.value.desc
      allowed_member_types = app_role.value.types
      enabled              = true
    }
  }
}

resource "azuread_service_principal" "api" {
  client_id                    = azuread_application.api.client_id
  app_role_assignment_required = true # users and apps without an assigned role cannot get a token
}

resource "azuread_group" "role" {
  for_each         = local.human_roles
  display_name     = "${var.group_prefix}-${replace(each.key, "aipir.", "")}"
  description      = each.value
  security_enabled = true
  owners           = var.group_owners
}

resource "azuread_app_role_assignment" "group" {
  for_each            = local.human_roles
  app_role_id         = uuidv5("url", "${var.identifier_uri}/roles/${each.key}")
  principal_object_id = azuread_group.role[each.key].object_id
  resource_object_id  = azuread_service_principal.api.object_id
}

# Workload identity for Alertmanager (app-only token, idtyp=app).
resource "azuread_application" "relay" {
  display_name     = "${var.app_name} - Alert relay"
  sign_in_audience = "AzureADMyOrg"
}

resource "azuread_service_principal" "relay" {
  client_id = azuread_application.relay.client_id
}

resource "azuread_app_role_assignment" "relay" {
  app_role_id         = uuidv5("url", "${var.identifier_uri}/roles/aipir.alert-relay")
  principal_object_id = azuread_service_principal.relay.object_id
  resource_object_id  = azuread_service_principal.api.object_id
}

# MFA for every human sign-in to the AIPIR API.
resource "azuread_conditional_access_policy" "mfa" {
  display_name = "${var.app_name} - require MFA"
  state        = var.mfa_policy_state

  conditions {
    client_app_types = ["all"]
    applications {
      included_applications = [azuread_application.api.client_id]
    }
    users {
      included_groups = [for g in azuread_group.role : g.object_id]
      excluded_users  = var.break_glass_user_ids
    }
  }

  grant_controls {
    operator          = "OR"
    built_in_controls = ["mfa"]
  }
}
