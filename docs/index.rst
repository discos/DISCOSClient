DISCOSClient
============

**DISCOSClient** is a Python library that provides a high-level interface to
access real-time telemetry data and send control commands to DISCOS
(Development of the Italian Single-dish COntrol System), the control software
of the three INAF single-dish radiotelescopes, the Sardinia Radio Telescope
(SRT), the Medicina Radio Telescope, and the Noto Radio Telescope.

The library provides an interface for accessing the internal state of telescope
components such as the `antenna`, `mount`, etc., for interacting with them, and
for controlling the telescope by sending it commands.
It is designed to be minimal, thread-safe, and self-describing via JSON schemas.

DISCOSClient is built on top of `ZeroMQ <https://zeromq.org/>`_, a
high-performance asynchronous messaging library for distributed systems.
All message transport is handled through `pyzmq <https://pypi.org/project/pyzmq/>`_,
the official Python bindings for ZeroMQ.

Key Features
------------

- Subscribe to one or multiple topics (e.g., `mount`, `antenna`)
- Send commands to DISCOS
- Automatically decodes incoming JSON messages into nested Python namespaces
- Supports both blocking and non-blocking access to telemetry data
- Cross-platform: works on Linux, macOS, and Windows
- Minimal dependencies: only 2 non-built-in Python libraries are used for
  maximum portability

Goals
-----

The main goals of `DISCOSClient` are:

- To simplify the development of monitoring, visualization and control tools
  for telescope systems
- To allow easy integration with third-party Python applications and dashboards
- To provide a minimal yet powerful abstraction over ZMQ-based message
  subscriptions and command dispatching

Overview
--------

The library exposes a main class `DISCOSClient` in order to access the telescope
telemetry data and send commands to it, along with three pre-configured classes,
one for each telescope:

- `SRTClient` client for the Sardinia Radio Telescope
- `MedicinaClient` client for the Medicina Radio Telescope
- `NotoClient` client for the Noto Radio Telescope

These specialized clients simplify the setup by pre-filling the `telescope`, `address`
and `port` arguments. Internally, each client instance manages a subscription socket
for telemetry and a dedicated interface for command transmission. Incoming JSON messages
are automatically parsed and stored as structured Python objects, which can be queried
or watched.

For further details, installation instructions, and usage examples, see the
sections below.


.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   install

.. toctree::
   :maxdepth: 2
   :caption: User Guide
   :name: user-guide

   user/user
   schemas/schemas

.. toctree::
   :maxdepth: 2
   :caption: API Reference
   :name: api-ref

   api/api

.. toctree::
   :maxdepth: 1
   :caption: Project Info

   developer/developer


Indices and tables
==================

* :ref:`genindex`
