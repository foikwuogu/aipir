# OpenTelemetry Collector: receives OTLP from the detector, exports metrics to Prometheus and
# traces/logs to the backend configured in the collector file.

resource "kubernetes_config_map_v1" "config" {
  metadata {
    name      = "otel-collector"
    namespace = var.namespace
  }
  data = { "config.yaml" = var.config_yaml }
}

resource "kubernetes_deployment_v1" "collector" {
  metadata {
    name      = "otel-collector"
    namespace = var.namespace
    labels    = { app = "otel-collector", "app.kubernetes.io/part-of" = "aipir" }
  }
  spec {
    replicas = 1
    selector { match_labels = { app = "otel-collector" } }
    template {
      metadata {
        labels = { app = "otel-collector" }
        annotations = {
          "checksum/config" = sha256(var.config_yaml)
        }
      }
      spec {
        automount_service_account_token = false
        security_context {
          run_as_non_root = true
          run_as_user     = 10001
          seccomp_profile { type = "RuntimeDefault" }
        }
        container {
          name  = "collector"
          image = var.image
          args  = ["--config=/etc/otelcol/config.yaml"]
          port {
            name           = "otlp-http"
            container_port = 4318
          }
          port {
            name           = "otlp-grpc"
            container_port = 4317
          }
          port {
            name           = "prom-export"
            container_port = 8889
          }
          resources {
            requests = { cpu = "100m", memory = "128Mi" }
            limits   = { cpu = "500m", memory = "512Mi" }
          }
          security_context {
            allow_privilege_escalation = false
            read_only_root_filesystem  = true
            capabilities { drop = ["ALL"] }
          }
          volume_mount {
            name       = "config"
            mount_path = "/etc/otelcol"
            read_only  = true
          }
        }
        volume {
          name = "config"
          config_map { name = kubernetes_config_map_v1.config.metadata[0].name }
        }
      }
    }
  }
}

resource "kubernetes_service_v1" "collector" {
  metadata {
    name      = "otel-collector"
    namespace = var.namespace
  }
  spec {
    selector = { app = "otel-collector" }
    port {
      name        = "otlp-http"
      port        = 4318
      target_port = "otlp-http"
    }
    port {
      name        = "otlp-grpc"
      port        = 4317
      target_port = "otlp-grpc"
    }
    port {
      name        = "prom-export"
      port        = 8889
      target_port = "prom-export"
    }
  }
}
