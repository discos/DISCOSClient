How to contribute to this project
=================================

This package has been written by following a **test driven development**
approach. Python classes and JSON schemas are thoroughly tested, the latter
against real JSON messages. Features should be proposed on this project's
GitHub Issues page.

Adding a schema
---------------
The classes have been thoroughly tested and several methods has been developed in
order for the clients to offer high flexibility and adapt to various scenarios.
This means that future additions are most likely to be additional schemas.
In order to write a schema for a specific DISCOS component, the first thing to do
is check what information the said component can provide. First and foremost,
you should check what attributes a component already exposes as DevIOs, and
secondly, which inner variables that are currently not exposed as attributes,
can be published in order to provide additional information. All these
attributes should be gathered together, in the form of a
`JSON Schema <https://json-schema.org/>`_, make sure to follow the `draft-07
specification <https://json-schema.org/draft-07>`_ in order to be  compliant
with other written  schemas. Check out
`other schemas <https://github.com/discos/DISCOSClient/tree/master/discos_client/schemas>`_
for a better idea of what a JSON schema looks like. Newly added schemas should
also be reported in :ref:`this documentation <schemas>` as well.

Installing development dependencies
-----------------------------------

To run the test suite and perform static analysis, install the development
dependencies with:

.. code-block:: bash

   pip install .[test]

This installs the required tools for running tests, measuring coverage, and linting.

Running tests with coverage
---------------------------

Use the following commands to execute the test suite and generate coverage data:

.. code-block:: bash

   coverage run -p -m unittest discover -b tests
   coverage combine
   coverage report

To generate an HTML coverage report:

.. code-block:: bash

   coverage html
   firefox htmlcov/index.html  # or use a browser or a text editor of your choice

Static analysis with prospector
-------------------------------

To check code quality using `prospector`, run:

.. code-block:: bash

   prospector
