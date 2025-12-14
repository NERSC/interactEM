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
    "benchmark-receiver",
    "center-of-mass-partial",
    "center-of-mass-reduce",
    "center-of-mass-plot",
    "dpc",
    "bin-sparse-partial",
    "quantem-direct-ptycho",
    "read-tem-data"
  ]
}

target "common" {
  args = {}
}

target "operator-contexts" {
  contexts = {
    operator = "target:operator"
  }
}

target "operator-full-contexts" {
  contexts = {
    operator            = "target:operator"
    distiller-streaming = "target:distiller-streaming"
  }
}

target "base" {
  inherits = [ "common" ]
  context = "backend/"
  dockerfile = "../docker/Dockerfile.base"
  tags = ["${REGISTRY}/interactem:${TAG}"]
}

target "operator" {
  inherits = [ "common" ]
  context = "backend/"
  contexts = {
    interactem-base = "target:base"
  }
  dockerfile = "../docker/Dockerfile.operator"
  tags = ["${REGISTRY}/operator:${TAG}"]
}

target "distiller-streaming" {
  inherits = [ "common", "operator-contexts" ]
  context = "operators/distiller-streaming"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/distiller-streaming:${TAG}"]
}

target "beam-compensation" {
  inherits = ["common", "operator-full-contexts"]
  context = "operators/beam-compensation"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/beam-compensation:${TAG}"]
}

target "data-replay" {
  inherits = ["common", "operator-full-contexts"]
  context = "operators/data-replay"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/data-replay:${TAG}"]
}

target "detstream-aggregator" {
  inherits = ["common", "operator-full-contexts"]
  context = "operators/detstream-aggregator"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/detstream-aggregator:${TAG}"]
}

target "detstream-assembler" {
  inherits = ["common", "operator-full-contexts"]
  context = "operators/detstream-assembler"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/detstream-assembler:${TAG}"]
}

target "detstream-producer" {
  inherits = ["common", "operator-full-contexts"]
  context = "operators/detstream-producer"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/detstream-producer:${TAG}"]
}

target "detstream-state-server" {
  inherits = ["common", "operator-full-contexts"]
  context = "operators/detstream-state-server"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/detstream-state-server:${TAG}"]
}

target "electron-count" {
  inherits = ["common", "operator-full-contexts"]
  context = "operators/electron-count"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/electron-count:${TAG}"]
}

target "electron-count-save" {
  inherits = ["common", "operator-full-contexts"]
  context = "operators/electron-count-save"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/electron-count-save:${TAG}"]
}

target "error" {
  inherits = ["common", "operator-full-contexts"]
  context = "operators/error"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/error:${TAG}"]
}

target "image-display" {
  inherits = ["common", "operator-full-contexts"]
  context = "operators/image-display"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/image-display:${TAG}"]
}

target "pva-converter" {
  inherits = ["common", "operator-full-contexts"]
  context = "operators/pva-converter"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/pva-converter:${TAG}"]
}

target "pvapy-ad-sim-server" {
  inherits = ["common", "operator-full-contexts"]
  context = "operators/pvapy-ad-sim-server"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/pvapy-ad-sim-server:${TAG}"]
}

target "random-image" {
  inherits = ["common", "operator-full-contexts"]
  context = "operators/random-image"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/random-image:${TAG}"]
}

target "sparse-frame-image-converter" {
  inherits = ["common", "operator-full-contexts"]
  context = "operators/sparse-frame-image-converter"
  dockerfile = "Containerfile" 
  tags = ["${REGISTRY}/sparse-frame-image-converter:${TAG}"]
}

target "random-table" {
  inherits = ["common", "operator-full-contexts"]
  context = "operators/random-table"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/random-table:${TAG}"]
}

target "table-display" {
  inherits = ["common", "operator-full-contexts"]
  context = "operators/table-display"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/table-display:${TAG}"]
}

target "distiller-state-client" {
  inherits = ["common", "operator-full-contexts"]
  context = "operators/distiller-state-client"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/distiller-state-client:${TAG}"]
}

target "distiller-grabber" {
  inherits = ["common", "operator-full-contexts"]
  context = "operators/distiller-grabber"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/distiller-grabber:${TAG}"]
}

target "distiller-counted-data-reader" {
  inherits = ["common", "operator-full-contexts"]
  context = "operators/distiller-counted-data-reader"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/distiller-counted-data-reader:${TAG}"]
}

target "diffraction-pattern-accumulator" {
  inherits = ["common", "operator-full-contexts"]
  context = "operators/diffraction-pattern-accumulator"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/diffraction-pattern-accumulator:${TAG}"]
}

target "array-image-converter" {
  inherits = ["common", "operator-full-contexts"]
  context = "operators/array-image-converter"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/array-image-converter:${TAG}"]
}

target "virtual-bfdf" {
  inherits = ["common", "operator-full-contexts"]
  context = "operators/virtual-bfdf"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/virtual-bfdf:${TAG}"]
}

target "benchmark-sender" {
  inherits = ["common", "operator-full-contexts"]
  context = "operators/benchmark-sender"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/benchmark-sender:${TAG}"]
}

target "benchmark-receiver" {
  inherits = ["common", "operator-full-contexts"]
  context = "operators/benchmark-receiver"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/benchmark-receiver:${TAG}"]
}

target "center-of-mass-partial" {
  inherits = ["common", "operator-full-contexts"]
  context = "operators/center-of-mass-partial"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/center-of-mass-partial:${TAG}"]
}

target "center-of-mass-reduce" {
  inherits = ["common", "operator-full-contexts"]
  context = "operators/center-of-mass-reduce"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/center-of-mass-reduce:${TAG}"]
}

target "center-of-mass-plot" {
  inherits = ["common", "operator-full-contexts"]
  context = "operators/center-of-mass-plot"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/center-of-mass-plot:${TAG}"]
}

target "dpc" {
  inherits = ["common", "operator-full-contexts"]
  context = "operators/dpc"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/dpc:${TAG}"]
}

target "bin-sparse-partial" {
  inherits = ["common", "operator-full-contexts"]
  context = "operators/bin-sparse-partial"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/bin-sparse-partial:${TAG}"]
}

target "quantem-direct-ptycho" {
  inherits = ["common", "operator-full-contexts"]
  context = "operators/quantem-direct-ptycho"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/quantem-direct-ptycho:${TAG}"]
}

target "read-tem-data" {
  inherits = ["common", "operator-full-contexts"]
  context = "operators/read-tem-data"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/read-tem-data:${TAG}"]
}
