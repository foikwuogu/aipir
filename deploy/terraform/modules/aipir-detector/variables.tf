variable "namespace" {
  description = "Namespace to deploy into (created by the environment, not by this module)."
  type        = string
}

variable "image" {
  description = "AIPIR detector container image (built from deploy/docker/Dockerfile)."
  type        = string
}

variable "replicas" {
  description = "Detector replicas; >= 2 keeps detection running through a pod failure."
  type        = number
  default     = 2
}

variable "service_account_name" {
  description = "Service account for the detector pods (from the aipir-k8s-rbac module)."
  type        = string
}

variable "model_path" {
  description = "Model bundle inside the image."
  type        = string
  default     = "models/aipir_hai2103.joblib"
}

variable "replay_file" {
  description = "Lab mode: telemetry file to replay from the telemetry volume. Replace the args for a live reader."
  type        = string
  default     = "/data/test2.csv.gz"
}

variable "telemetry_claim_name" {
  description = "PersistentVolumeClaim holding replay telemetry (lab mode)."
  type        = string
  default     = "aipir-telemetry"
}

variable "recovery_mode" {
  description = "dry-run plans recoveries only; execute queues them for two-person approval."
  type        = string
  default     = "dry-run"
  validation {
    condition     = contains(["dry-run", "execute"], var.recovery_mode)
    error_message = "recovery_mode must be dry-run or execute."
  }
}

variable "auth" {
  description = "Zero-Trust token settings. mode = rs256 with an identity provider (Entra ID) in production; hs256 only in a lab."
  type = object({
    mode            = string
    issuer          = string
    audience        = string
    jwks_configmap  = optional(string)
    lab_secret_name = optional(string)
  })
  validation {
    condition     = contains(["rs256", "hs256"], var.auth.mode)
    error_message = "auth.mode must be rs256 (OIDC) or hs256 (lab)."
  }
}

variable "otel_endpoint" {
  description = "OTLP/HTTP endpoint of the OpenTelemetry Collector; empty disables OTel export."
  type        = string
  default     = ""
}

variable "monitoring_namespace" {
  description = "Namespace allowed to scrape metrics and post recovery webhooks."
  type        = string
  default     = "monitoring"
}

variable "environment" {
  description = "deployment.environment resource attribute (lab, pilot, production)."
  type        = string
  default     = "lab"
}
