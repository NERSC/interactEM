variable "REGISTRY" {
  default = "localhost:5001/ghcr.io/nersc/interactem"
}

target "common" {
  platforms = ["linux/amd64", "linux/arm64"]
  args = {}
}