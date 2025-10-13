# Authoring operators

```{include} ../../operators/README.md
:start-after: "# Authoring operators"
:end-before: "### Containerfile"
```

```{literalinclude} ../../operators/center-of-mass-partial/run.py
:pyobject: com_partial
```

```{include} ../../operators/README.md
:start-after: "### `run.py` file"
:end-before: "### Specification"
```

```{literalinclude} ../../operators/distiller-streaming/Containerfile
:language: Dockerfile
:caption: ghcr.io/nersc/interactem/distiller-streaming
```

```{literalinclude} ../../operators/center-of-mass-partial/Containerfile
:language: Dockerfile
:caption: ghcr.io/nersc/interactem/center-of-mass-partial
```

```{include} ../../operators/README.md
:start-after: "### Containerfile"
:end-before: "## Building locally"
```

```{literalinclude} ../../backend/core/interactem/core/models/spec.py
:pyobject: OperatorSpec
:caption: Specification model
```

```{literalinclude} ../../operators/center-of-mass-partial/operator.json
:language: json
:caption: Example `operator.json`
```

## Building locally

```{include} ../../operators/README.md
:start-after: "## Building locally"
```
