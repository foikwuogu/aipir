output "detector_service_account" { value = kubernetes_service_account_v1.detector.metadata[0].name }
output "drift_service_account" { value = kubernetes_service_account_v1.drift.metadata[0].name }
output "recovery_service_account" { value = kubernetes_service_account_v1.recovery.metadata[0].name }
