Testing and Linting
===================

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
   open htmlcov/index.html  # or use your file manager

Static analysis with prospector
-------------------------------

To check code quality using `prospector`, run:

.. code-block:: bash

   prospector
