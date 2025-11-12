```{include} ../../operators/README.md
:end-before: "### Containerfile"
```

```{literalinclude} ../../operators/center-of-mass-partial/run.py
:pyobject: com_partial
```

<!-- Note we have to include this because myst doesn't have a start-at directive -->
### Containerfile

```{include} ../../operators/README.md
:start-after: "### Containerfile"
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

### Specification

```{include} ../../operators/README.md
:start-after: "### Specification" 
```

```{literalinclude} ../../backend/core/interactem/core/models/spec.py
:pyobject: OperatorSpec
:caption: Specification model
```

```{literalinclude} ../../operators/center-of-mass-partial/operator.json
:language: json
:caption: Example `operator.json`
```
