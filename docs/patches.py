import os
import sys
from pathlib import Path
from urllib.parse import urlparse
sys.path.insert(0, os.path.abspath('../discos_client'))

def _simpletype(self, schema):
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
        del schema['enum']

    if 'examples' in schema:
        rows.extend(self._examples(schema['examples']))
        del schema['examples']

    if "unit" in schema:
        unit = f"*{schema['unit']}*"
        rows.append(self._line(self._cell("unit"), self._cell(unit)))
        del schema["unit"]

    if "node" in schema:
        node = f"{schema['node']}"
        rows.append(self._line(self._cell("node"), self._cell(node)))
        del schema["node"]

    rows.extend(self._kvpairs(schema, self.KV_SIMPLE))
    return rows

def _complexstructures(self, schema):
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


def _reference(self, schema):
    if self.options['auto_reference'] and self.options['lift_title']:
        # first check if references is to own schema
        # when definitions is separated automated they will be linked to the title
        # otherwise it will only be a string
        reference = (
            self._get_defined_reference(schema, 'definitions') or
            self._get_defined_reference(schema, '$defs')
        )
        if schema['$ref'] == '#' or schema['$ref'] == '#/':
            if self.ref_titles.get(0, False):
                row = (self._line(self._cell('`' + self.ref_titles[0] + '`_')))
            else:
                row = (self._line(self._cell(schema['$ref'])))
        elif reference:
            ref_length, target_name = reference
            # Check if there are definitions available to make a reference
            if (self.ref_titles.get(ref_length, False) and
                    target_name in self.ref_titles[ref_length]):
                ref_title = self.ref_titles[ref_length][target_name]
                row = (self._line(self._cell('`' + ref_title + '`_')))
            else:
                row = (self._line(self._cell(schema['$ref'])))
        elif schema['$ref'].startswith("#/"):
            # Other references to own schema should not be defined as :ref: only as string
            row = (self._line(self._cell(schema['$ref'])))
        elif schema['$ref'].startswith("http"):
            row = (self._line(self._cell(schema['$ref'])))
        elif "#/" in schema['$ref']:
            row = (self._line(self._cell(':ref:`' + self._get_filename(schema['$ref'], True) + '`')))
        else:
            row = (self._line(self._cell(':ref:`' + self._get_filename(schema['$ref']) + '`')))
    elif self.options['auto_reference'] and not self.options['lift_title']:
        # when using reference without titles we need to reference to our own targets
        # if auto_target is False linking won't work
        parsed = urlparse(schema['$ref'])
        if parsed.path:
            filename = Path(parsed.path).name
            hash_char = ""
            if parsed.fragment:
                hash_char = "#"
            row = self._line(self._cell(f":ref:`{filename}{hash_char}{parsed.fragment}`"))
        else:
            row = self._line(self._cell(f":ref:`{self.filename}#{parsed.fragment}`"))
    else:
        row = (self._line(self._cell(':ref:`' + schema['$ref'] + '`')))
    del schema['$ref']
    return [row]
