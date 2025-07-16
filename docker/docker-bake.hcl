variable "TAG" {
  default = "latest"
}

variable "REGISTRY" {
  default = "ghcr.io/nersc/interactem"
}

// Base platform definition
target "platform" {
  platforms = ["linux/amd64", "linux/arm64"]
}

// Base image (parent for service images)
target "base" {
  inherits = ["platform"]
  context = "backend/"
  dockerfile = "../docker/Dockerfile.base"
  tags = [
    "${REGISTRY}/interactem:${TAG}",
    "${REGISTRY}/interactem:latest",
  ]
}

// Service definitions
target "operator" {
  inherits = ["platform"]
  context = "backend/"
  dockerfile = "../docker/Dockerfile.operator"
  tags = [
    "${REGISTRY}/operator:${TAG}",
    "${REGISTRY}/operator:latest",
  ]
}

target "callout" {
  inherits = ["platform"]
  context = "backend/"
  dockerfile = "../docker/Dockerfile.callout"
  tags = [
    "${REGISTRY}/callout:${TAG}",
    "${REGISTRY}/callout:latest",
  ]
}

target "fastapi" {
  inherits = ["platform"]
  context = "backend/"
  dockerfile = "../docker/Dockerfile.fastapi"
  tags = [
    "${REGISTRY}/fastapi:${TAG}",
    "${REGISTRY}/fastapi:latest",
  ]
}

target "launcher" {
  inherits = ["platform"]
  context = "backend/"
  dockerfile = "../docker/Dockerfile.launcher"
  tags = [
    "${REGISTRY}/launcher:${TAG}",
    "${REGISTRY}/launcher:latest",
  ]
}

target "orchestrator" {
  inherits = ["platform"]
  context = "backend/"
  dockerfile = "../docker/Dockerfile.orchestrator"
  tags = [
    "${REGISTRY}/orchestrator:${TAG}",
    "${REGISTRY}/orchestrator:latest",
  ]
}

target "frontend" {
  inherits = ["platform"]
  context = "frontend/"
  dockerfile = "../docker/Dockerfile.frontend"
  tags = [
    "${REGISTRY}/frontend:${TAG}",
    "${REGISTRY}/frontend:latest",
  ]
}

target "metrics" {
  inherits = ["platform"]
  context = "backend/"
  dockerfile = "../docker/Dockerfile.metrics"
  tags = [
    "${REGISTRY}/metrics:${TAG}",
    "${REGISTRY}/metrics:latest",
  ]
}

group "base" {
  targets = ["base"]
}

group "prod" {
  targets = ["operator", "callout", "fastapi", "launcher", "orchestrator", "frontend", "metrics"]
}