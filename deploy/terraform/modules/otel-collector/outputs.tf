output "otlp_http_endpoint" {
  value = "http://${kubernetes_service_v1.collector.metadata[0].name}.${var.namespace}.svc:4318"
}
