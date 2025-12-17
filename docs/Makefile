.PHONY: help install build clean serve autobuild sync-readmes

UV := uv

help:
	@echo "Please use \`make <target>' where <target> is one of"
	@echo "  build       to build the HTML documentation"
	@echo "  clean       to remove generated documentation files"
	@echo "  serve       to build and serve the documentation"
	@echo "  autobuild   to auto-rebuild on file changes"
	@echo "  sync-readmes to regenerate README files from docs"

sync-readmes:
	$(UV) run scripts/sync_readmes.py

build: sync-readmes
	$(UV) run sphinx-build -n -b html source _build/html

sync-check:
	$(UV) run scripts/sync_readmes.py --check

clean:
	rm -rf _build

serve: build
	@echo "Serving documentation at http://localhost:8000"
	@cd _build/html && $(UV) run python -m http.server

autobuild:
	$(UV) run sphinx-autobuild source _build/html --open-browser --fresh-env
