DISCOSClient
============

**DISCOSClient** is a Python library that provides a high-level interface to
access real-time telemetry data published by the DISCOS (Development of the
Italian Single-dish COntrol System) infrastructure. This system is used by
INAF telescopes such as the Sardinia Radio Telescope (SRT), the Medicina Radio
Telescope, and the Noto Radio Telescope.

The library provides both synchronous and asynchronous interfaces for accessing
the internal state of telescope components such as the `antenna`, `mount`, etc.
It is designed to be minimal, thread-safe, and self-describing via JSON schemas.

DISCOSClient is built on top of `ZeroMQ <https://zeromq.org/>`_, a
high-performance asynchronous messaging library for distributed systems.
All message transport is handled through `pyzmq <https://pypi.org/project/pyzmq/>`_,
the official Python bindings for ZeroMQ.

This documentation guides you through installation, usage, and advanced functionality.

Key Features
------------

- Subscribe to one or multiple topics (e.g., `mount`, `antenna`)
- Available in both **synchronous** and **asynchronous** variants
  (`SyncClient`, `AsyncClient`)
- Automatically decodes incoming JSON messages into nested Python namespaces
- Supports both blocking and non-blocking access to telemetry data
- Cross-platform: works on Linux, macOS, and Windows

Goals
-----

The main goals of `DISCOSClient` are:

- To simplify the development of monitoring and visualization tools
  for telescope systems
- To allow easy integration with third-party Python applications and dashboards
- To provide a minimal yet powerful abstraction over ZMQ-based message
  subscriptions

Overview
--------

The library exposes a main factory class `DISCOSClient`, along with three
preconfigured partial factories for convenience:

- `SRTClient` for the Sardinia Radio Telescope
- `MedicinaClient` for the Medicina Radio Telescope
- `NotoClient` for the Noto Radio Telescope

These partial clients simplify the setup by pre-filling the `telescope`
and `address` arguments, making it easier to instantiate clients for the
corresponding observatory:

Internally, each client instance manages a subscription socket and a background
thread (for `SyncClient`) or coroutine (for `AsyncClient`) that continuously
listens for messages published by the telescope systems.

Incoming JSON messages are automatically parsed and stored as structured Python
objects, which can be queried, watched, or awaited depending on the client's
mode.

For further details, installation instructions, and usage examples, see the
sections below.


.. toctree::
   :maxdepth: 2
   :caption: Contents:

   install
   user
   developer/developer
   schemas/schemas


Indices and tables
==================

* :ref:`genindex`
