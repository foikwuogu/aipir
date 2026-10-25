# AIPIR detector: Deployment + Service + PodDisruptionBudget + default-deny NetworkPolicy.
# Recovery of the monitoring stack is `apply` to this declared state; model rollback is a change
# to var.image (or `kubectl rollout undo`, which the revision history supports).

locals {
  labels = { app = "aipir-detector", "app.kubernetes.io/part-of" = "aipir" }
  env = merge(
    {
      AIPIR_RECOVERY  = var.recovery_mode
      AIPIR_AUTH_MODE = var.auth.mode
      AIPIR_ISSUER    = var.auth.issuer
      AIPIR_AUDIENCE  = var.auth.audience
      AIPIR_ENV       = var.environment
      AIPIR_AUDIT_LOG = "/var/log/aipir/audit.jsonl"
    },
    var.otel_endpoint == "" ? {} : { OTEL_EXPORTER_OTLP_ENDPOINT = var.otel_endpoint },
    var.auth.mode == "rs256" ? { AIPIR_JWKS_FILE = "/etc/aipir/jwks/jwks.json" } : {}
  )
}

resource "kubernetes_deployment_v1" "detector" {
  metadata {
    name      = "aipir-detector"
    namespace = var.namespace
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
        service_account_name            = var.service_account_name
        automount_service_account_token = false
        security_context {
          run_as_non_root = true
          run_as_user     = 10001
          fs_group        = 10001
          seccomp_profile { type = "RuntimeDefault" }
        }
        container {
          name  = "detector"
          image = var.image
          args  = ["--model", var.model_path, "--replay", var.replay_file, "--speed", "60"]
          port {
            name           = "http"
            container_port = 9108
          }
          dynamic "env" {
            for_each = local.env
            content {
              name  = env.key
              value = env.value
            }
          }
          dynamic "env" {
            for_each = var.auth.mode == "hs256" && var.auth.lab_secret_name != null ? [1] : []
            content {
              name = "AIPIR_LAB_SECRET"
              value_from {
                secret_key_ref {
                  name = var.auth.lab_secret_name
                  key  = "secret"
                }
              }
            }
          }
          resources {
            requests = { cpu = "250m", memory = "512Mi" }
            limits   = { cpu = "1", memory = "1Gi" }
          }
          readiness_probe {
            http_get {
              path = "/healthz"
              port = "http"
            }
            period_seconds = 5
          }
          liveness_probe {
            http_get {
              path = "/healthz"
              port = "http"
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
          volume_mount {
            name       = "audit"
            mount_path = "/var/log/aipir"
          }
          dynamic "volume_mount" {
            for_each = var.auth.mode == "rs256" ? [1] : []
            content {
              name       = "jwks"
              mount_path = "/etc/aipir/jwks"
              read_only  = true
            }
          }
        }
        volume {
          name = "telemetry"
          persistent_volume_claim { claim_name = var.telemetry_claim_name }
        }
        volume {
          name = "audit"
          empty_dir {}
        }
        dynamic "volume" {
          for_each = var.auth.mode == "rs256" ? [1] : []
          content {
            name = "jwks"
            config_map { name = var.auth.jwks_configmap }
          }
        }
      }
    }
  }
}

resource "kubernetes_service_v1" "detector" {
  metadata {
    name      = "aipir-detector"
    namespace = var.namespace
    labels    = local.labels
  }
  spec {
    selector = { app = "aipir-detector" }
    port {
      name        = "http"
      port        = 9108
      target_port = "http"
    }
  }
}

resource "kubernetes_pod_disruption_budget_v1" "detector" {
  metadata {
    name      = "aipir-detector"
    namespace = var.namespace
  }
  spec {
    min_available = "1"
    selector { match_labels = { app = "aipir-detector" } }
  }
}

# Zero-Trust network posture: deny everything, then allow only the monitoring namespace in,
# and only DNS + the OTel Collector out. The detector can never reach the control network.
resource "kubernetes_network_policy_v1" "detector" {
  metadata {
    name      = "aipir-detector"
    namespace = var.namespace
  }
  spec {
    pod_selector { match_labels = { app = "aipir-detector" } }
    policy_types = ["Ingress", "Egress"]
    ingress {
      from {
        namespace_selector { match_labels = { "kubernetes.io/metadata.name" = var.monitoring_namespace } }
      }
      ports { port = "9108" }
    }
    egress {
      to {
        namespace_selector { match_labels = { "kubernetes.io/metadata.name" = "kube-system" } }
        pod_selector { match_labels = { "k8s-app" = "kube-dns" } }
      }
      ports {
        port     = "53"
        protocol = "UDP"
      }
    }
    egress {
      to {
        pod_selector { match_labels = { app = "otel-collector" } }
      }
      ports { port = "4318" }
    }
  }
}
