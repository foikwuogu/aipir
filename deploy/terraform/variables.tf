variable "kubeconfig" {
  description = "Path to the kubeconfig of the target cluster (cloud or plant-edge)."
  type        = string
  default     = "~/.kube/config"
}

variable "kube_context" {
  description = "kubeconfig context to deploy into."
  type        = string
  default     = null
}

variable "image" {
  description = "AIPIR detector container image (built from deploy/Dockerfile)."
  type        = string
  default     = "ghcr.io/OWNER/aipir:0.1.0"
}

variable "replicas" {
  description = "Detector replicas; >= 2 keeps detection running through a pod failure."
  type        = number
  default     = 2
}

variable "recovery_mode" {
  description = "dry-run logs the playbook; execute hands it to the operator's automation."
  type        = string
  default     = "dry-run"
  validation {
    condition     = contains(["dry-run", "execute"], var.recovery_mode)
    error_message = "recovery_mode must be dry-run or execute."
  }
}
