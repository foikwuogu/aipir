# Infrastructure-as-Code for AIPIR: the whole detection stack is declared here, so
# recovery from a compromised or failed monitoring node is `terraform apply` to a
# known-good state (and a model rollback is a one-line change to var.image).

locals {
  labels = { app = "aipir-detector", "app.kubernetes.io/part-of" = "aipir" }
}

resource "kubernetes_namespace_v1" "aipir" {
  metadata {
    name   = "aipir"
    labels = { "pod-security.kubernetes.io/enforce" = "restricted" }
  }
}

resource "kubernetes_deployment_v1" "detector" {
  metadata {
    name      = "aipir-detector"
    namespace = kubernetes_namespace_v1.aipir.metadata[0].name
    labels    = local.labels
  }
  spec {
    replicas               = var.replicas
    revision_history_limit = 5
    selector { match_labels = { app = "aipir-detector" } }
    strategy {
      type = "RollingUpdate"
      rolling_update {
        max_unavailable = "0"
        max_surge       = "1"
      }
    }
    template {
      metadata {
        labels      = local.labels
        annotations = { "prometheus.io/scrape" = "true", "prometheus.io/port" = "9108" }
      }
      spec {
        automount_service_account_token = false
        security_context {
          run_as_non_root = true
          run_as_user     = 10001
          seccomp_profile { type = "RuntimeDefault" }
        }
        container {
          name  = "detector"
          image = var.image
          args  = ["--model", "models/aipir_hai2103.joblib", "--replay", "/data/test2.csv.gz", "--speed", "60"]
          port {
            name           = "metrics"
            container_port = 9108
          }
          env {
            name  = "AIPIR_RECOVERY"
            value = var.recovery_mode
          }
          resources {
            requests = { cpu = "250m", memory = "512Mi" }
            limits   = { cpu = "1", memory = "1Gi" }
          }
          readiness_probe {
            http_get {
              path = "/healthz"
              port = "metrics"
            }
            period_seconds = 5
          }
          liveness_probe {
            http_get {
              path = "/healthz"
              port = "metrics"
            }
            period_seconds    = 10
            failure_threshold = 3
          }
          security_context {
            allow_privilege_escalation = false
            read_only_root_filesystem  = true
            capabilities { drop = ["ALL"] }
          }
          volume_mount {
            name       = "telemetry"
            mount_path = "/data"
            read_only  = true
          }
        }
        volume {
          name = "telemetry"
          persistent_volume_claim { claim_name = kubernetes_persistent_volume_claim_v1.telemetry.metadata[0].name }
        }
      }
    }
  }
}

resource "kubernetes_persistent_volume_claim_v1" "telemetry" {
  metadata {
    name      = "aipir-telemetry"
    namespace = kubernetes_namespace_v1.aipir.metadata[0].name
  }
  spec {
    access_modes = ["ReadOnlyMany"]
    resources { requests = { storage = "1Gi" } }
  }
  wait_until_bound = false
}

resource "kubernetes_service_v1" "detector" {
  metadata {
    name      = "aipir-detector"
    namespace = kubernetes_namespace_v1.aipir.metadata[0].name
    labels    = local.labels
  }
  spec {
    selector = { app = "aipir-detector" }
    port {
      name        = "metrics"
      port        = 9108
      target_port = "metrics"
    }
  }
}

resource "kubernetes_pod_disruption_budget_v1" "detector" {
  metadata {
    name      = "aipir-detector"
    namespace = kubernetes_namespace_v1.aipir.metadata[0].name
  }
  spec {
    min_available = "1"
    selector { match_labels = { app = "aipir-detector" } }
  }
}

resource "kubernetes_network_policy_v1" "isolation" {
  metadata {
    name      = "aipir-detector-isolation"
    namespace = kubernetes_namespace_v1.aipir.metadata[0].name
  }
  spec {
    pod_selector { match_labels = { app = "aipir-detector" } }
    policy_types = ["Ingress", "Egress"]
    ingress {
      from {
        namespace_selector { match_labels = { "kubernetes.io/metadata.name" = "monitoring" } }
      }
      ports { port = "9108" }
    }
  }
}
