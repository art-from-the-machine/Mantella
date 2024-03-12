# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'Mantella'
copyright = '2024, Art from the Machine'
author = 'Art from the Machine'
release = ''

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = ["myst_parser",
               "sphinx_design",
               "sphinx.ext.autodoc",
               "sphinxcontrib.youtube"]
myst_enable_extensions = ["colon_fence",
                          "deflist",
                          "tasklist",
                          "smartquotes"]
myst_heading_anchors = 3
templates_path = ['_templates']
exclude_patterns = []



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'furo'
html_title = "Mantella"
html_logo = "./_static/img/mantella_logo_docs.png"
html_favicon = "./_static/img/mantella_favicon.ico"
html_static_path = ['_static']
html_theme_options = {
    "sidebar_hide_name": True,
}