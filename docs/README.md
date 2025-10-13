# interactEM Documentation

This directory contains the documentation for interactEM, built with Sphinx and the Furo theme.

## Setup

Install dependencies:

```bash
cd docs
poetry install
```

## Building the Documentation

Build the HTML documentation:

```bash
make build
```

The built documentation will be in `_build/html/`.

## Development

For live auto-rebuilding during development:

```bash
make autobuild
```

This will start a local server and automatically rebuild the docs when you make changes.

## Structure

- `source/` - Documentation source files (RST and Markdown)
- `source/_static/` - Static assets (CSS, JS, images)
- `source/_templates/` - Custom Sphinx templates
- `source/conf.py` - Sphinx configuration

## Theme

This documentation uses the Furo theme with custom styling inspired by the [iceoryx2-book](https://github.com/ekxide/iceoryx2-book) project.
