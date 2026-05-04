import os
import importlib
import sys
from sphinx import addnodes
from sphinx.pycode import ModuleAnalyzer
from sphinx.ext.autodoc import MethodDocumenter, ClassDocumenter

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
sys.path.insert(0, os.path.abspath('../discos_client'))

from patches import _simpletype, _complexstructures, _reference, _transform

# We add these methods which are normally "hidden"
from discos_client.client import DISCOSClient
DISCOSClient.command = DISCOSClient.__command__
from discos_client.namespace import DISCOSNamespace
DISCOSNamespace.bind = DISCOSNamespace.__bind__
DISCOSNamespace.copy = DISCOSNamespace.__copy__
DISCOSNamespace.get_value = DISCOSNamespace.__get_value__
DISCOSNamespace.unbind = DISCOSNamespace.__unbind__
DISCOSNamespace.wait = DISCOSNamespace.__wait__

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'DISCOSClient'
copyright = '2025, Giuseppe Carboni'
author = 'Giuseppe Carboni'
release = '0.2.0'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.doctest',
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
    'sphinx_autodoc_typehints',
    'sphinx-jsonschema',
]

autoclass_content = "both"

autodoc_typehints = "none"

autodoc_default_options = {
    'members': True,
    'member-order': 'bysource',
}

jsonschema_options = {
    'auto_reference': True,
    'auto_target': True,
    'lift_title': True,
    'lift_description': True,
    'lift_definitions': True,
}

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'

html_theme_options = {
    "style_external_links": True,
    "collapse_navigation": False,
    "sticky_navigation": True,
    "titles_only": False,
    "navigation_depth": 3,
    "prev_next_buttons_location": "bottom",
}

html_css_files = [
    "custom.css",
]

html_static_path = ['_static']

latex_engine = 'lualatex'


def setup(app):
    app.connect("viewcode-find-source", on_viewcode_find_source)

def on_viewcode_find_source(app, modname):
    analyzer = ModuleAnalyzer.for_module(modname)
    analyzer.find_tags()
    if modname == "discos_client.client":
        if "DISCOSClient.__command__" in analyzer.tags:
            analyzer.tags["DISCOSClient.command"] = analyzer.tags.get("DISCOSClient.__command__")
            analyzer.tags["SRTClient.command"] = analyzer.tags.get("DISCOSClient.__command__")
            analyzer.tags["MedicinaClient.command"] = analyzer.tags.get("DISCOSClient.__command__")
            analyzer.tags["NotoClient.command"] = analyzer.tags.get("DISCOSClient.__command__")
    if modname == "discos_client.namespace":
        for method in ["bind", "copy", "get_value", "unbind", "wait"]:
            if f"DISCOSNamespace.__{method}__" in analyzer.tags:
                analyzer.tags[f"DISCOSNamespace.{method}"] = analyzer.tags.get(f"DISCOSNamespace.__{method}__")
    return analyzer.code, analyzer.tags


sjs_wide_format = importlib.import_module("sphinx-jsonschema.wide_format")
sjs_wide_format.WideFormat._simpletype = _simpletype
sjs_wide_format.WideFormat._complexstructures = _complexstructures
sjs_wide_format.WideFormat._reference = _reference
sjs_wide_format.WideFormat.transform = _transform
