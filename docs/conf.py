import os
import importlib
import sys
from sphinx.ext.autodoc import ClassDocumenter
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
sys.path.insert(0, os.path.abspath('../discos_client'))

from patches import _simpletype, _complexstructures, _reference

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
    "navigation_depth": 3,
    "prev_next_buttons_location": "bottom",
}

html_css_files = [
    "custom.css",
]

html_static_path = ['_static']


class SkipMembersClassDocumenter(ClassDocumenter):
    objtype = "class"

    option_spec = ClassDocumenter.option_spec.copy()
    option_spec["skip-members"] = lambda arg: [name.strip() for name in arg.split(",")] if arg else []

    def parse_name(self):
        return super().parse_name()


def skip_special_members(app, what, name, obj, skip, options):
    global_skips = app.config.autoclass_skip_members_default or set()
    directive_skips = set(options.get("skip-members", []))

    if name in global_skips or name in directive_skips:
        return True
    return None


def setup(app):
    app.add_config_value("autoclass_skip_members_default", set(), "env")
    app.add_autodocumenter(SkipMembersClassDocumenter, override=True)
    app.connect("autodoc-skip-member", skip_special_members)


sjs_wide_format = importlib.import_module("sphinx-jsonschema.wide_format")
sjs_wide_format.WideFormat._simpletype = _simpletype
sjs_wide_format.WideFormat._complexstructures = _complexstructures
sjs_wide_format.WideFormat._reference = _reference
