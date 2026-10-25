output "service_dns" {
  description = "In-cluster address of the detector API and metrics."
  value       = "${kubernetes_service_v1.detector.metadata[0].name}.${var.namespace}.svc:9108"
}

output "deployment_name" {
  value = kubernetes_deployment_v1.detector.metadata[0].name
}
