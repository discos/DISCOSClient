import os
import sys
from pathlib import Path
from urllib.parse import urlparse
from docutils import nodes
sys.path.insert(0, os.path.abspath('../discos_client'))

SEP = "__SEP__"
SEP_TOP = "__SEP_TOP__"
SEP_BOTTOM = "__SEP_BOTTOM__"


def _transform(self, schema):
    body, definitions = self._dispatch(schema)
    table = None
    if len(body) > 0:
        cols, head, body = self._cover(schema, body)
        table = self.state.build_table((cols, head, body), self.lineno)
    if table is None:
        return table, definitions

    for tbody in table.traverse(nodes.tbody):
        levels = {}
        for idx, row in enumerate(tbody.children):
            if not isinstance(row, nodes.row):
                continue
            entries = [c for c in row.children if isinstance(c, nodes.entry)]
            if not entries:
                continue
            cell_texts = [e.astext().strip() for e in entries]
            if SEP_TOP in cell_texts:
                marker = SEP_TOP
            elif SEP in cell_texts:
                marker = SEP
            elif SEP_BOTTOM in cell_texts:
                marker = SEP_BOTTOM
            else:
                continue
            sep_index = next(
                (i for i, txt in enumerate(cell_texts) if marker in txt),
                0
            )
            level = max(0, min(sep_index, 4))
            levels[idx] = level
            for e in entries:
                for child in list(e.children):
                    if marker in e.astext():
                        e.remove(child)
        consecutives = consecutive_groups(list(levels.keys()))
        for lst in consecutives:
            level = levels[lst[-1]]
            tbody.children[lst[-1]]['classes'].append(f"row-border-{level}")
            for idx in lst[:-1]:
                l = levels[idx]
                tbody.children[idx]['classes'].append(f"row-hidden-{l}")
    return table, definitions

def consecutive_groups(lst):
    if not lst:
        return []
    groups = []
    current = [lst[0]]
    for x in lst[1:]:
        if x == current[-1] + 1:
            current.append(x)
        else:
            groups.append(current)
            current = [x]
    groups.append(current)
    return groups

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
        if k in schema:
            if k in ['anyOf', 'allOf']:
                if k == 'anyOf':
                    label = self._cell('any of the following')
                else:
                    label = self._cell('all the properties of')
                items = []
                items.append(self._line(self._cell(SEP_TOP)))
                for idx, s in enumerate(schema[k]):
                    content = self._dispatch(s)[0]
                    if not content:
                        continue
                    if idx > 0:
                        items.append(self._line(self._cell(SEP)))
                    items.extend(content)
                if items:
                    items.append(self._line(self._cell(SEP_BOTTOM)))
                    rows.extend(self._prepend(label, items))
            else:
                items = []
                for s in schema[k]:
                    content = self._dispatch(s)[0]
                    if content:
                        items.extend(content)
                if items:
                    rows.extend(self._prepend(self._cell(k), items))
            del schema[k]

    for k in self.SINGLEOBJECTS:
        # combinators belong at this level as alternative to type
        if k in schema:
            rows.extend(self._dispatch(schema[k], self._cell(k))[0])
            del schema[k]

    if self.CONDITIONAL[0] in schema:
        # only if 'if' in schema there would be a need to go through if, then & else
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
    if schema['$ref'].startswith('#'):
        schema['$ref'] = f"{self.filename}{schema['$ref']}"

    if self.options['auto_reference'] and self.options['lift_title']:
        # first check if references is to own schema
        # when definitions is separated automated they will be linked to the title
        # otherwise it will only be a string
        reference = (
            self._get_defined_reference(schema, 'definitions') or
            self._get_defined_reference(schema, '$defs')
        )

        if reference:
            ref_length, target_name = reference
            # Check if there are definitions available to make a reference
            if (self.ref_titles.get(ref_length, False) and
                    target_name in self.ref_titles[ref_length]):
                ref_title = self.ref_titles[ref_length][target_name]
                row = (self._line(self._cell('`' + ref_title + '`_')))
            else:
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
