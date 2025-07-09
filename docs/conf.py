# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import importlib
import sys
sys.path.insert(0, os.path.abspath('../discos_client'))

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'DISCOSClient'
copyright = '2025, Giuseppe Carboni'
author = 'Giuseppe Carboni'
release = '0.1.0'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
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
    'lift_title': False,
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


def _patched_sphinx_jsonschema_simpletype(self, schema):
    """Render the *extra* ``units`` schema property for every object."""
    rows = []

    if 'title' in schema and (not self.options['lift_title'] or self.nesting > 1):
        rows.append(self._line(self._cell('*' + schema['title'] + '*')))
        del schema['title']

    self._check_description(schema, rows)

    if 'type' in schema:
        rows.append(
            self._line(self._cell('type'),
                       self._decodetype(schema['type'])))
        del schema['type']

    if 'enum' in schema:
        rows.append(
            self._line(
                self._cell('enum'),
                self._cell('\n'.join(
                    [str(e) for e in schema['enum']]))))
        #rows.append(
        #    self._line(
        #        self._cell('enum'),
        #        self._cell(', '.join(
        #            [str(e) for e in schema['enum']]))))
        del schema['enum']

    if 'examples' in schema:
        rows.extend(self._examples(schema['examples']))
        del schema['examples']

    if "unit" in schema:
        unit = f"*{schema['unit']}*"
        rows.append(self._line(self._cell("unit"), self._cell(unit)))
        del schema["unit"]

    rows.extend(self._kvpairs(schema, self.KV_SIMPLE))
    return rows

def _patched_sphinx_jsonschema_complexstructures(self, schema):
    rows = []

    for k in self.COMBINATORS:
        # combinators belong at this level as alternative to type
        if k in schema:
            items = []
            for s in schema[k]:
                content = self._dispatch(s)[0]
                if content:
                    items.extend(content)
            if items:
                key = k
                if k == 'allOf':
                    key = 'properties'
                rows.extend(self._prepend(self._cell(key), items))
            del schema[k]

    for k in self.SINGLEOBJECTS:
        # combinators belong at this level as alternative to type
        if k in schema:
            rows.extend(self._dispatch(schema[k], self._cell(k))[0])
            del schema[k]

    if self.CONDITIONAL[0] in schema:
        # only if 'if' in schema there would be a needs to go through if, then & else
        items = []
        for k in self.CONDITIONAL:
            if k in schema:
                content = self._dispatch(schema[k])[0]
                if content:
                    items.append(self._prepend(self._cell(k), content))
                del schema[k]
        if len(items) >= 2:
            for item in items:
                rows.extend(item)

    return rows


sjs_wide_format = importlib.import_module("sphinx-jsonschema.wide_format")
_original_sphinx_jsonschema_simpletype = sjs_wide_format.WideFormat._simpletype
_original_sphinx_jsonschema_complexstructures = sjs_wide_format.WideFormat._complexstructures
sjs_wide_format.WideFormat._simpletype = _patched_sphinx_jsonschema_simpletype
sjs_wide_format.WideFormat._complexstructures = _patched_sphinx_jsonschema_complexstructures
