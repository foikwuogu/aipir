# Lab / pilot environment on any Kubernetes cluster (AKS, EKS, GKE, k3s at the plant edge).
#   terraform init && terraform apply -var image=ghcr.io/<owner>/aipir:<tag>

variable "kubeconfig" {
  type    = string
  default = "~/.kube/config"
}

variable "kube_context" {
  type    = string
  default = null
}

variable "image" {
  type    = string
  default = "ghcr.io/OWNER/aipir:0.2.0"
}

variable "auth" {
  description = "Use rs256 + the Entra ID values from environments/azure-entra for a pilot; hs256 for a closed lab."
  type = object({
    mode            = string
    issuer          = string
    audience        = string
    jwks_configmap  = optional(string)
    lab_secret_name = optional(string)
  })
  default = { mode = "hs256", issuer = "aipir-lab", audience = "api://aipir", lab_secret_name = "aipir-lab-secret" }
}

variable "group_bindings" {
  type = object({
    viewers   = list(string)
    operators = list(string)
    admins    = list(string)
  })
  default = { viewers = [], operators = [], admins = [] }
}

resource "kubernetes_namespace_v1" "aipir" {
  metadata {
    name   = "aipir"
    labels = { "pod-security.kubernetes.io/enforce" = "restricted" }
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

module "rbac" {
  source         = "../../modules/aipir-k8s-rbac"
  namespace      = kubernetes_namespace_v1.aipir.metadata[0].name
  group_bindings = var.group_bindings
}

module "otel" {
  source      = "../../modules/otel-collector"
  namespace   = kubernetes_namespace_v1.aipir.metadata[0].name
  config_yaml = file("${path.module}/../../../observability/otel/otel-collector.yaml")
}

module "detector" {
  source               = "../../modules/aipir-detector"
  namespace            = kubernetes_namespace_v1.aipir.metadata[0].name
  image                = var.image
  service_account_name = module.rbac.detector_service_account
  telemetry_claim_name = kubernetes_persistent_volume_claim_v1.telemetry.metadata[0].name
  auth                 = var.auth
  otel_endpoint        = module.otel.otlp_http_endpoint
}

output "detector" { value = module.detector.service_dns }
output "otlp_endpoint" { value = module.otel.otlp_http_endpoint }
