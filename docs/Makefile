.PHONY: help install build clean serve autobuild sync-readmes

help:
	@echo "Please use \`make <target>' where <target> is one of"
	@echo "  install     to install dependencies via poetry"
	@echo "  build       to build the HTML documentation"
	@echo "  clean       to remove generated documentation files"
	@echo "  serve       to build and serve the documentation"
	@echo "  autobuild   to auto-rebuild on file changes"
	@echo "  sync-readmes to regenerate README files from docs"

install:
	poetry install

sync-readmes:
	poetry run python scripts/sync_readmes.py

build: sync-readmes
	poetry run sphinx-build -n -b html source _build/html

clean:
	rm -rf _build

serve: build
	@echo "Serving documentation at http://localhost:8000"
	@cd _build/html && python -m http.server

autobuild:
	poetry run sphinx-autobuild source _build/html --open-browser --fresh-env
