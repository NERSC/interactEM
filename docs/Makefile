.PHONY: help install build clean serve autobuild

help:
	@echo "Please use \`make <target>' where <target> is one of"
	@echo "  install     to install dependencies via poetry"
	@echo "  build       to build the HTML documentation"
	@echo "  clean       to remove generated documentation files"
	@echo "  serve       to build and serve the documentation"
	@echo "  autobuild   to auto-rebuild on file changes"

install:
	poetry install

build:
	poetry run sphinx-build -b html source _build/html

clean:
	rm -rf _build

serve: build
	@echo "Serving documentation at http://localhost:8000"
	@cd _build/html && python -m http.server

autobuild:
	poetry run sphinx-autobuild source _build/html --open-browser \
		--watch ../README.md \
		--watch ../backend/agent/README.md \
		--watch ../operators/README.md \
		--fresh-env
