# Least-privilege Kubernetes RBAC for AIPIR. Workloads get their own service accounts; people get
# namespaced roles through identity-provider groups. Nothing is cluster-wide.

locals {
  labels = { "app.kubernetes.io/part-of" = "aipir" }
}

# --- workload identities -----------------------------------------------------------------
resource "kubernetes_service_account_v1" "detector" {
  metadata {
    name      = "aipir-detector"
    namespace = var.namespace
    labels    = local.labels
  }
  automount_service_account_token = false # the detector never calls the Kubernetes API
}

resource "kubernetes_service_account_v1" "drift" {
  metadata {
    name      = "aipir-drift"
    namespace = var.namespace
    labels    = local.labels
  }
}

resource "kubernetes_service_account_v1" "recovery" {
  metadata {
    name      = "aipir-recovery"
    namespace = var.namespace
    labels    = local.labels
  }
}

# Drift checker: read-only on the kinds AIPIR declares, in its own namespace.
resource "kubernetes_role_v1" "drift_reader" {
  metadata {
    name      = "aipir-drift-reader"
    namespace = var.namespace
  }
  rule {
    api_groups = ["", "apps", "policy", "networking.k8s.io", "rbac.authorization.k8s.io", "batch"]
    resources = ["deployments", "services", "configmaps", "serviceaccounts", "poddisruptionbudgets",
    "networkpolicies", "roles", "rolebindings", "cronjobs"]
    verbs = ["get", "list"]
  }
}

resource "kubernetes_role_binding_v1" "drift_reader" {
  metadata {
    name      = "aipir-drift-reader"
    namespace = var.namespace
  }
  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "Role"
    name      = kubernetes_role_v1.drift_reader.metadata[0].name
  }
  subject {
    kind      = "ServiceAccount"
    name      = kubernetes_service_account_v1.drift.metadata[0].name
    namespace = var.namespace
  }
}

# Recovery runner (Ansible recover_monitoring.yml): may roll back the detector deployment only.
resource "kubernetes_role_v1" "recovery" {
  metadata {
    name      = "aipir-recovery"
    namespace = var.namespace
  }
  rule {
    api_groups     = ["apps"]
    resources      = ["deployments"]
    resource_names = ["aipir-detector"]
    verbs          = ["get", "patch"]
  }
  rule {
    api_groups = ["apps"]
    resources  = ["replicasets"]
    verbs      = ["get", "list"]
  }
}

resource "kubernetes_role_binding_v1" "recovery" {
  metadata {
    name      = "aipir-recovery"
    namespace = var.namespace
  }
  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "Role"
    name      = kubernetes_role_v1.recovery.metadata[0].name
  }
  subject {
    kind      = "ServiceAccount"
    name      = kubernetes_service_account_v1.recovery.metadata[0].name
    namespace = var.namespace
  }
}

# --- people (through identity-provider groups) ------------------------------------------
resource "kubernetes_role_v1" "people" {
  for_each = {
    viewer   = { verbs = ["get", "list", "watch"], resources = ["pods", "services", "deployments", "configmaps", "events"] }
    operator = { verbs = ["get", "list", "watch"], resources = ["pods", "pods/log", "services", "deployments", "configmaps", "events"] }
    admin    = { verbs = ["get", "list", "watch", "create", "update", "patch"], resources = ["deployments", "services", "configmaps", "cronjobs", "networkpolicies", "poddisruptionbudgets"] }
  }
  metadata {
    name      = "aipir-${each.key}"
    namespace = var.namespace
  }
  rule {
    api_groups = ["", "apps", "batch", "policy", "networking.k8s.io"]
    resources  = each.value.resources
    verbs      = each.value.verbs
  }
}

locals {
  bindings = merge(
    { for g in var.group_bindings.viewers : "viewer-${g}" => { role = "viewer", group = g } },
    { for g in var.group_bindings.operators : "operator-${g}" => { role = "operator", group = g } },
    { for g in var.group_bindings.admins : "admin-${g}" => { role = "admin", group = g } },
  )
}

resource "kubernetes_role_binding_v1" "people" {
  for_each = local.bindings
  metadata {
    name      = "aipir-${each.key}"
    namespace = var.namespace
  }
  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "Role"
    name      = kubernetes_role_v1.people[each.value.role].metadata[0].name
  }
  subject {
    api_group = "rbac.authorization.k8s.io"
    kind      = "Group"
    name      = each.value.group
  }
}
