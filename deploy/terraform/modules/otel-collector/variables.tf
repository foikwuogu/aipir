variable "namespace" {
  type = string
}

variable "image" {
  description = "OpenTelemetry Collector (contrib) image."
  type        = string
  default     = "otel/opentelemetry-collector-contrib:0.111.0"
}

variable "config_yaml" {
  description = "Collector configuration (deploy/observability/otel/otel-collector.yaml)."
  type        = string
}
