output "namespace" { value = kubernetes_namespace_v1.aipir.metadata[0].name }
output "metrics_service" {
  value = "${kubernetes_service_v1.detector.metadata[0].name}.${kubernetes_namespace_v1.aipir.metadata[0].name}.svc:9108"
}
