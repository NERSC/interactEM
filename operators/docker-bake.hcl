variable "REGISTRY" {
  default = "ghcr.io/nersc/interactem"
}

variable "TAG" {
  default = "latest"
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
    "sparse-frame-image-converter",
    "random-table",
    "table-display",
    "distiller-state-client",
    "distiller-grabber",
    "distiller-counted-data-reader",
    "diffraction-pattern-accumulator",
    "array-image-converter",
    "virtual-bfdf",
    "benchmark-sender",
    "benchmark-receiver"
  ]
}

target "base" {
  context = "backend/"
  dockerfile = "../docker/Dockerfile.base"
  platforms = ["linux/amd64", "linux/arm64"]
  tags = ["${REGISTRY}/interactem:${TAG}"]
}

target "operator" {
  context = "backend/"
  dockerfile = "../docker/Dockerfile.operator"
  platforms = ["linux/amd64", "linux/arm64"]
  tags = ["${REGISTRY}/operator:${TAG}"]
}

target "distiller-streaming" {
  context = "operators/distiller-streaming"
  dockerfile = "Containerfile"
  platforms = ["linux/amd64", "linux/arm64"]
  tags = ["${REGISTRY}/distiller-streaming:${TAG}"]
}

target "common" {
  platforms = ["linux/amd64"]
  args = {}
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

target "random-table" {
  inherits = ["common"]
  context = "operators/random-table"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/random-table:${TAG}"]
}

target "table-display" {
  inherits = ["common"]
  context = "operators/table-display"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/table-display:${TAG}"]
}

target "distiller-state-client" {
  inherits = ["common"]
  context = "operators/distiller-state-client"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/distiller-state-client:${TAG}"]
}

target "distiller-grabber" {
  inherits = ["common"]
  context = "operators/distiller-grabber"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/distiller-grabber:${TAG}"]
}

target "distiller-counted-data-reader" {
  inherits = ["common"]
  context = "operators/distiller-counted-data-reader"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/distiller-counted-data-reader:${TAG}"]
}

target "diffraction-pattern-accumulator" {
  inherits = ["common"]
  context = "operators/diffraction-pattern-accumulator"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/diffraction-pattern-accumulator:${TAG}"]
}

target "array-image-converter" {
  inherits = ["common"]
  context = "operators/array-image-converter"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/array-image-converter:${TAG}"]
}

target "virtual-bfdf" {
  inherits = ["common"]
  context = "operators/virtual-bfdf"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/virtual-bfdf:${TAG}"]
}

target "benchmark-sender" {
  inherits = ["common"]
  context = "operators/benchmark-sender"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/benchmark-sender:${TAG}"]
}

target "benchmark-receiver" {
  inherits = ["common"]
  context = "operators/benchmark-receiver"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/benchmark-receiver:${TAG}"]
}