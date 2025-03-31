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
  depends_on = ["base"]
}

target "callout" {
  inherits = ["platform"]
  context = "backend/"
  dockerfile = "../docker/Dockerfile.callout"
  tags = [
    "${REGISTRY}/callout:${TAG}",
    "${REGISTRY}/callout:latest",
  ]
  depends_on = ["base"]
}

target "fastapi" {
  inherits = ["platform"]
  context = "backend/"
  dockerfile = "../docker/Dockerfile.fastapi"
  tags = [
    "${REGISTRY}/fastapi:${TAG}",
    "${REGISTRY}/fastapi:latest",
  ]
  depends_on = ["base"]
}

target "launcher" {
  inherits = ["platform"]
  context = "backend/"
  dockerfile = "../docker/Dockerfile.launcher"
  tags = [
    "${REGISTRY}/launcher:${TAG}",
    "${REGISTRY}/launcher:latest",
  ]
  depends_on = ["base"]
}

target "orchestrator" {
  inherits = ["platform"]
  context = "backend/"
  dockerfile = "../docker/Dockerfile.orchestrator"
  tags = [
    "${REGISTRY}/orchestrator:${TAG}",
    "${REGISTRY}/orchestrator:latest",
  ]
  depends_on = ["base"]
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

// Default target group
group "default" {
  targets = ["base", "operator", "callout", "fastapi", "launcher", "orchestrator", "frontend"]
}

// Production target group
group "prod" {
  targets = ["base", "operator", "callout", "fastapi", "launcher", "orchestrator", "frontend"]
}