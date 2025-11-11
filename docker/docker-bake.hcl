variable "TAG" {
  default = "latest"
}

variable "REGISTRY" {
  default = "ghcr.io/nersc/interactem"
}

// Functions

function "generate_cache_from" {
  params = [service_name]
  result = [
    // we want to try to grab cache from the base 
    // image cache as well
    {
      type = "registry"
      ref = "${REGISTRY}/interactem:build-cache-arm64"
    },
    {
      type = "registry"
      ref = "${REGISTRY}/interactem:build-cache-amd64"
    },
    {
      type = "registry"
      ref = "${REGISTRY}/${service_name}:build-cache-arm64"
    },
    {
      type = "registry"
      ref = "${REGISTRY}/${service_name}:build-cache-amd64"
    }
  ]
}

function "generate_cache_to" {
  params = [service_name]
  result = [
    {
      type = "registry"
      ref = "${REGISTRY}/${service_name}:build-cache-${CACHE_PLATFORM}"
      mode = "max"
    }
  ]
}

function "generate_tags" {
  params = [service_name]
  result = [
    "${REGISTRY}/${service_name}:${TAG}",
    "${REGISTRY}/${service_name}:latest"
  ]
}

// Base platform definition - let docker decide the platform
target "platform" {
}

target "contexts" {
  contexts = {
    interactem-base = "target:base"
  }
}

variable "CACHE_PLATFORM" {
  default = "amd64"
}

// Base image (parent for service images)
target "base" {
  inherits = ["platform"]
  context = "backend/"
  dockerfile = "../docker/Dockerfile.base"
  tags = generate_tags("interactem")
  cache-from = generate_cache_from("interactem")
  cache-to = generate_cache_to("interactem")
}

// Service definitions
target "operator" {
  inherits = ["platform", "contexts"]
  context = "backend/"
  dockerfile = "../docker/Dockerfile.operator"
  tags = generate_tags("operator")
  cache-from = generate_cache_from("operator")
  cache-to = generate_cache_to("operator")
}

target "callout" {
  inherits = ["platform"]
  context = "backend/"
  dockerfile = "../docker/Dockerfile.callout"
  tags = generate_tags("callout")
  cache-from = generate_cache_from("callout")
  cache-to = generate_cache_to("callout")
}

target "fastapi" {
  inherits = ["platform", "contexts"]
  context = "backend/"
  dockerfile = "../docker/Dockerfile.fastapi"
  tags = generate_tags("fastapi")
  cache-from = generate_cache_from("fastapi")
  cache-to = generate_cache_to("fastapi")
}

target "launcher" {
  inherits = ["platform", "contexts"]
  context = "backend/"
  dockerfile = "../docker/Dockerfile.launcher"
  tags = generate_tags("launcher")
  cache-from = generate_cache_from("launcher")
  cache-to = generate_cache_to("launcher")
}

target "orchestrator" {
  inherits = ["platform", "contexts"]
  context = "backend/"
  dockerfile = "../docker/Dockerfile.orchestrator"
  tags = generate_tags("orchestrator")
  cache-from = generate_cache_from("orchestrator")
  cache-to = generate_cache_to("orchestrator")
}

target "frontend" {
  inherits = ["platform"]
  context = "frontend/"
  dockerfile = "../docker/Dockerfile.frontend"
  tags = generate_tags("frontend")
  cache-from = generate_cache_from("frontend")
  cache-to = generate_cache_to("frontend")
}

target "metrics" {
  inherits = ["platform", "contexts"]
  context = "backend/"
  dockerfile = "../docker/Dockerfile.metrics"
  tags = generate_tags("metrics")
  cache-from = generate_cache_from("metrics")
  cache-to = generate_cache_to("metrics")
}

group "base" {
  targets = ["base"]
}

group "prod" {
  targets = ["operator", "callout", "fastapi", "launcher", "orchestrator", "frontend", "metrics"]
}