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
  cache-from = [
    {
      type = "registry",
      ref = "${REGISTRY}/interactem:build-cache-arm64"
    },
    {
      type = "registry",
      ref = "${REGISTRY}/interactem:build-cache-arm64"
    },
    {
      type = "registry",
      ref = "${REGISTRY}/operator:build-cache-arm64"
    },
    {
      type = "registry",
      ref = "${REGISTRY}/operator:build-cache-arm64"
    }
  ]
}

target "base-context" { 
  contexts = {
    interactem-base = "target:base"
  }
}

target "operator-context" {
  contexts = {
    interactem-operator = "target:operator"
  }
}

target "distiller-streaming-context" {
  contexts = {
    distiller-streaming = "target:distiller-streaming"
  }
}

target "output" {
}

target "base" {
  inherits = [ "common" ]
  context = "backend/"
  dockerfile = "../docker/Dockerfile.base"
  tags = ["${REGISTRY}/interactem"]
}

target "operator" {
  inherits = [ "common" , "base-context", "output"]
  context = "backend/"
  dockerfile = "../docker/Dockerfile.operator"
  tags = ["${REGISTRY}/operator"]
}

target "distiller-streaming" {
  inherits = [ "common", "operator-context"]
  context = "operators/distiller-streaming"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/distiller-streaming"]
}

target "beam-compensation" {
  inherits = ["common", "distiller-streaming-context", "output"]
  context = "operators/beam-compensation"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/beam-compensation"]
}

target "data-replay" {
  inherits = ["common", "distiller-streaming-context", "output"]
  context = "operators/data-replay"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/data-replay"]
}

target "detstream-aggregator" {
  inherits = ["common", "operator-context", "output"]
  context = "operators/detstream-aggregator"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/detstream-aggregator"]
}

target "detstream-assembler" {
  inherits = ["common", "operator-context", "output"]
  context = "operators/detstream-assembler"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/detstream-assembler"]
}

target "detstream-producer" {
  inherits = ["common", "operator-context", "output"]
  context = "operators/detstream-producer"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/detstream-producer"]
}

target "detstream-state-server" {
  inherits = ["common", "operator-context", "output"]
  context = "operators/detstream-state-server"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/detstream-state-server"]
}

target "electron-count" {
  inherits = ["common", "operator-context", "output"]
  context = "operators/electron-count"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/electron-count"]
}

target "electron-count-save" {
  inherits = ["common", "operator-context", "output"]
  context = "operators/electron-count-save"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/electron-count-save"]
}

target "error" {
  inherits = ["common", "operator-context", "output"]
  context = "operators/error"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/error"]
}

target "image-display" {
  inherits = ["common", "operator-context", "output"]
  context = "operators/image-display"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/image-display"]
}

target "pva-converter" {
  inherits = ["common", "operator-context", "output"]
  context = "operators/pva-converter"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/pva-converter"]
}

target "pvapy-ad-sim-server" {
  inherits = ["common", "operator-context", "output"]
  context = "operators/pvapy-ad-sim-server"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/pvapy-ad-sim-server"]
}

target "random-image" {
  inherits = ["common", "operator-context", "output"]
  context = "operators/random-image"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/random-image"]
}

target "sparse-frame-image-converter" {
  inherits = ["common", "distiller-streaming-context", "output"]
  context = "operators/sparse-frame-image-converter"
  dockerfile = "Containerfile" 
  tags = ["${REGISTRY}/sparse-frame-image-converter"]
}

target "random-table" {
  inherits = ["common", "operator-context", "output"]
  context = "operators/random-table"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/random-table"]
}

target "table-display" {
  inherits = ["common", "operator-context", "output"]
  context = "operators/table-display"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/table-display"]
}

target "distiller-state-client" {
  inherits = ["common", "distiller-streaming-context", "output"]
  context = "operators/distiller-state-client"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/distiller-state-client"]
}

target "distiller-grabber" {
  inherits = ["common", "distiller-streaming-context", "output"]
  context = "operators/distiller-grabber"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/distiller-grabber"]
}

target "distiller-counted-data-reader" {
  inherits = ["common", "distiller-streaming-context", "output"]
  context = "operators/distiller-counted-data-reader"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/distiller-counted-data-reader"]
}

target "diffraction-pattern-accumulator" {
  inherits = ["common", "distiller-streaming-context", "output"]
  context = "operators/diffraction-pattern-accumulator"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/diffraction-pattern-accumulator"]
}

target "array-image-converter" {
  inherits = ["common", "operator-context", "output"]
  context = "operators/array-image-converter"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/array-image-converter"]
}

target "virtual-bfdf" {
  inherits = ["common", "distiller-streaming-context", "output"]
  context = "operators/virtual-bfdf"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/virtual-bfdf"]
}

target "benchmark-sender" {
  inherits = ["common", "operator-context", "output"]
  context = "operators/benchmark-sender"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/benchmark-sender"]
}

target "benchmark-receiver" {
  inherits = ["common", "operator-context", "output"]
  context = "operators/benchmark-receiver"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/benchmark-receiver"]
}

target "center-of-mass-partial" {
  inherits = ["common", "distiller-streaming-context", "output"]
  context = "operators/center-of-mass-partial"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/center-of-mass-partial"]
}

target "center-of-mass-reduce" {
  inherits = ["common", "distiller-streaming-context", "output"]
  context = "operators/center-of-mass-reduce"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/center-of-mass-reduce"]
}

target "center-of-mass-plot" {
  inherits = ["common", "distiller-streaming-context", "output"]
  context = "operators/center-of-mass-plot"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/center-of-mass-plot"]
}

target "dpc" {
  inherits = ["common", "distiller-streaming-context", "output"]
  context = "operators/dpc"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/dpc"]
}

target "bin-sparse-partial" {
  inherits = ["common", "distiller-streaming-context", "output"]
  context = "operators/bin-sparse-partial"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/bin-sparse-partial"]
}

target "quantem-direct-ptycho" {
  inherits = ["common", "distiller-streaming-context", "output"]
  context = "operators/quantem-direct-ptycho"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/quantem-direct-ptycho"]
}

target "read-tem-data" {
  inherits = ["common", "operator-context", "output"]
  context = "operators/read-tem-data"
  dockerfile = "Containerfile"
  tags = ["${REGISTRY}/read-tem-data"]
}