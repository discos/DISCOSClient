DISCOSClient
============

.. image:: https://github.com/discos/DISCOSClient/actions/workflows/ci_tests.yml/badge.svg
   :target: https://github.com/discos/DISCOSClient/actions/workflows/ci_tests.yml
   :alt: CI Tests

.. image:: https://codecov.io/gh/discos/DISCOSClient/graph/badge.svg?token=6ZYAL74I06
   :target: https://codecov.io/gh/discos/DISCOSClient
   :alt: Code Coverage

**DISCOSClient** is a Python client for accessing telemetry data streams from DISCOS
(Development of the Italian Single-dish COntrol System), the control system used by INAF's radio telescopes.

The client allows subscriptions to specific components (e.g., mount, antenna) and provides
thread-safe, read-only access to their internal state via a structured and immutable interface.

Features
--------

- ZeroMQ SUB client for structured telemetry updates
- Read-only nested namespaces for safe access
- Lightweight and dependency-minimal
- JSON schemas used as metadata for message structure

Setup
-----

Clone the repository and install the package:

.. code-block:: bash

   git clone https://github.com/discos/DISCOSClient.git
   cd DISCOSClient
   pip install .

Usage Example
-------------

.. code-block:: python

   from discos_client import DISCOSClient

   SRT = DISCOSClient("mount", address="127.0.0.1", port=16000)

   az = SRT.mount.azimuth.currentPosition
   el = SRT.mount.elevation.currentPosition
   print(f"Azimuth: {az}\nElevation: {el}")

Project Structure
-----------------

- ``discos_client/``            – Main client implementation
- ``discos_client/schemas/``    – JSON schemas used as structural metadata
- ``tests/``                    – Unit tests

Documentation
-------------

For more details, read the full documentation, available at:

📘 https://discosclient.readthedocs.io/en/latest/

License
-------

This project is licensed under the GPL-3.0-only license.
See the ``LICENSE`` file for details.

Contact
-------

Giuseppe Carboni – `giuseppe.carboni@inaf.it <mailto:giuseppe.carboni@inaf.it>`_
