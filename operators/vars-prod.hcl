variable "REGISTRY" {
  default = "ghcr.io/nersc/interactem"
}

target "common" {
  platforms = ["linux/amd64", "linux/arm64"]
}
