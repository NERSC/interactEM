# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'interactEM'
copyright = '2025, interactEM developers'
author = 'interactEM developers'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinxcontrib.mermaid",
    "myst_parser",
    "sphinx_design",
    "sphinx_multiversion",
    "sphinx_copybutton",
]

myst_enable_extensions = [
    "deflist",
    "attrs_block",
    "attrs_inline",
]
myst_heading_anchors = 3

# Enable nitpicky mode to catch broken cross-references and invalid links
nitpicky = True

# Suppress specific warnings that are expected
suppress_warnings = [
    'myst.xref_missing',
    'image.not_readable',
    'myst.header',
]

smv_branch_whitelist = r'^main$'
smv_tag_whitelist = r'^v\d+\.\d+\.\d+$'
smv_remote_whitelist = r'^origin$'
smv_released_pattern = r'^tags/v\d+\.\d+\.\d+$'

templates_path = ["_templates"]
exclude_patterns = []

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "furo"
html_title = "interactEM Documentation"
html_theme_options = {
    "top_of_page_buttons": [],
    "light_css_variables": {
        "color-brand-primary": "#6c7b7f",
        "color-brand-content": "#6c7b7f",
        "color-background-primary": "#ffffff",
        "color-background-secondary": "#f9fafb",
        "color-background-hover": "#f3f4f6",
        "color-background-border": "#e5e7eb",
        "color-foreground-primary": "#1f2937",
        "color-foreground-secondary": "#6b7280",
        "color-foreground-muted": "#9ca3af",
        "color-foreground-border": "#e5e7eb",
        "color-code-background": "#f3f4f6",
        "color-code-foreground": "#1f2937",
        "color-link": "#6c7b7f",
        "color-link-underline": "#6c7b7f",
        "color-link-underline--hover": "#4b5563",
        "color-sidebar-background": "#f9fafb",
        "color-sidebar-background-border": "#e5e7eb",
        "color-sidebar-item-background--hover": "#f3f4f6",
        "color-sidebar-link-text": "#4b5563",
        "color-sidebar-link-text--top-level": "#1f2937",
        "color-sidebar-caption-text": "#6b7280",
    },

    "dark_css_variables": {
        "color-brand-primary": "#9ca3af",
        "color-brand-content": "#9ca3af",
        "color-background-primary": "#1C1D1F",
        "color-background-secondary": "#252628",
        "color-background-hover": "#2a2c2f",
        "color-background-border": "#38393b",
        "color-foreground-primary": "#d2dbde",
        "color-foreground-secondary": "#859399",
        "color-foreground-muted": "#859399",
        "color-foreground-border": "#38393b",
        "color-code-background": "#2a2c2f",
        "color-code-foreground": "#d2dbde",
        "color-link": "#9ca3af",
        "color-link-underline": "#9ca3af",
        "color-link-underline--hover": "#d1d5db",
        "color-sidebar-background": "#252628",
        "color-sidebar-background-border": "#38393b",
        "color-sidebar-item-background--hover": "#2a2c2f",
        "color-sidebar-link-text": "#d2dbde",
        "color-sidebar-link-text--top-level": "#ffffff",
        "color-sidebar-caption-text": "#859399",
    },
}
html_static_path = ["_static"]
html_permalinks_icon = "#"
html_css_files = [
    "css/custom.css",
]
html_sidebars = {
    "**": [
        "sidebar/github-link.html",
        "sidebar/scroll-start.html",
        "sidebar/brand.html",
        "sidebar/search.html",
        "sidebar/navigation.html",
        "sidebar/ethical-ads.html",
        "sidebar/scroll-end.html",
    ]
}


# -- MarkdownSymlinks Configuration -----------------------------------------


def setup(app):
    """Configure the markdown symlinks domain."""
    import os

    from markdown_code_symlinks import MarkdownSymlinksDomain

    github_repo_url = "https://github.com/NERSC/interactEM/"
    github_repo_branch = "blob/main/"

    docs_root_dir = os.path.realpath(os.path.dirname(__file__))
    code_root_dir = os.path.realpath(os.path.join(docs_root_dir, "..", ".."))

    MarkdownSymlinksDomain.init_domain(
        github_repo_url, github_repo_branch, docs_root_dir, code_root_dir
    )
    MarkdownSymlinksDomain.find_links()
    app.add_domain(MarkdownSymlinksDomain)
