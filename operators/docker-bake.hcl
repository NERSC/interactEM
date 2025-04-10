variable "REGISTRY" {
  default = "ghcr.io/nersc/interactem"
}

variable "TAG" {
  default = "latest"
}

group "base-targets" {
  targets = [
    "base",
    "operator-base"
  ]
}

group "operators" {
  targets = [
    "beam-compensation",
    "data-replay",
    "detstream-aggregator",
    "detstream-assembler",
    "detstream-producer",
    "detstream-state-server",
    "electron-count",
    "electron-count-save",
    "error",
    "image-display",
    "pva-converter",
    "pvapy-ad-sim-server",
    "random-image",
    "sparse-frame-image-converter"
  ]
}

target "base" {
  context = "backend/"
  dockerfile = "../docker/Dockerfile.base"
  platforms = ["linux/amd64", "linux/arm64"]
  tags = ["${REGISTRY}/interactem-base:${TAG}"]
}

target "operator-base" {
  context = "backend/"
  dockerfile = "../docker/Dockerfile.operator"
  platforms = ["linux/amd64", "linux/arm64"]
  tags = ["${REGISTRY}/operator:${TAG}"]
  depends = ["base"]
}

target "common" {
  platforms = ["linux/amd64"]
  args = {}
  depends = ["operator-base"]
}

target "beam-compensation" {
  inherits = ["common"]
  context = "operators/beam-compensation"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/beam-compensation:${TAG}"]
}

target "data-replay" {
  inherits = ["common"]
  context = "operators/data-replay"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/data-replay:${TAG}"]
}

target "detstream-aggregator" {
  inherits = ["common"]
  context = "operators/detstream-aggregator"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/detstream-aggregator:${TAG}"]
}

target "detstream-assembler" {
  inherits = ["common"]
  context = "operators/detstream-assembler"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/detstream-assembler:${TAG}"]
}

target "detstream-producer" {
  inherits = ["common"]
  context = "operators/detstream-producer"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/detstream-producer:${TAG}"]
}

target "detstream-state-server" {
  inherits = ["common"]
  context = "operators/detstream-state-server"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/detstream-state-server:${TAG}"]
}

target "electron-count" {
  inherits = ["common"]
  context = "operators/electron-count"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/electron-count:${TAG}"]
}

target "electron-count-save" {
  inherits = ["common"]
  context = "operators/electron-count-save"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/electron-count-save:${TAG}"]
}

target "error" {
  inherits = ["common"]
  context = "operators/error"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/error:${TAG}"]
}

target "image-display" {
  inherits = ["common"]
  context = "operators/image-display"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/image-display:${TAG}"]
}

target "pva-converter" {
  inherits = ["common"]
  context = "operators/pva-converter"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/pva-converter:${TAG}"]
}

target "pvapy-ad-sim-server" {
  inherits = ["common"]
  context = "operators/pvapy-ad-sim-server"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/pvapy-ad-sim-server:${TAG}"]
}

target "random-image" {
  inherits = ["common"]
  context = "operators/random-image"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/random-image:${TAG}"]
}

target "sparse-frame-image-converter" {
  inherits = ["common"]
  context = "operators/sparse-frame-image-converter"
  dockerfile = "Containerfile" 
  tags = ["${REGISTRY}/sparse-frame-image-converter:${TAG}"]
}