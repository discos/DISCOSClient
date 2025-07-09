User Guide
==========

This guide shows how to use `DISCOSClient` to read real-time telemetry data
from INAF's single-dish radio telescopes. The client provides both synchronous
and asynchronous interfaces, with structured data exposed as nested Python
objects.

Instantiating a Client
----------------------

Use one of the preconfigured factories to create a client:

- ``SRTClient`` for the Sardinia Radio Telescope
- ``MedicinaClient`` for the Medicina Radio Telescope
- ``NotoClient`` for the Noto Radio Telescope

You can optionally provide one or more topic names to subscribe to.
If no topics are specified, the client will automatically subscribe
to all available ones for the selected telescope.

To create a synchronous client for SRT:

.. code-block:: python

   from discos_client import SRTClient

   SRT = SRTClient("mount", "antenna")

To subscribe to all available topics:

.. code-block:: python

   SRT = SRTClient()

Reading Values
--------------

Clients maintain an internal view of the most recent values for each
subscribed topic. You can access these data at any time without blocking,
either via dot notation or with the ``get()`` method.

Using dot notation:

.. code-block:: python

   az = SRT.mount.azimuth.currentPosition
   
Using the ``get()`` method:

.. code-block:: python

   az = SRT.get("mount.azimuth.currentPosition")
   
To block and wait for a new message, add ``wait=True``:

.. code-block:: python

   az = SRT.get("mount.azimuth.currentPosition", wait=True)

.. note::

   Calling ``get("...", wait=True)`` returns when a new message is received
   for the requested property, regardless of whether the actual value has changed.


Synchronous Clients
...................

Once created, the client starts receiving updates in a background thread.
You can read values as shown in the previous section, or access the entire
content of a topic like this:

.. code-block:: python

   antenna = SRT.get("antenna")
   print(antenna.observedAzimuth, antenna.observedElevation)

Asynchronous Clients
....................

Asynchronous clients are designed to be used within Python's `asyncio`
framework. They are ideal for applications that need to remain responsive
while waiting for updates. You can still use the access via dot-notation as
you've seen in the previous paragraphs, but the overall usage requires
`asyncio` constructs such as ``await`` and an event loop.

To create an asynchronous client, pass ``asynchronous=True``:

.. code-block:: python

   import asyncio
   from discos_client import MedicinaClient

   async def main():
       MED = MedicinaClient("antenna", asynchronous=True)

       # Read current full topic
       antenna = await MED.get("antenna")
       print(antenna.rawAzimuth)

       # Wait for next full topic update
       antenna = await MED.get("antenna", wait=True)
       print(antenna.rawElevation)

       # Wait for a specific field update
       az = await MED.get("antenna.observedAzimuth", wait=True)
       print(az)

   asyncio.run(main())


Choosing Between Sync and Async Clients
---------------------------------------

This section helps clarify when to use the synchronous or asynchronous
client, based on your application's requirements. It outlines the
strengths and limitations of each mode to support an informed choice.

When to use Synchronous Clients
...............................

The synchronous implementation is the most traditional and straightforward
to use. It is recommended in non-complex contexts where asynchronous
programming is not needed, such as:

- your code is **sequential or blocking**
- you're writing **simple scripts**, test procedures, or command-line tools
- you're **not using** the `asyncio` framework
- you prefer a **simpler interface** without `await` or event loop management

When to use Asynchronous Clients
................................

Asynchronous clients are designed for use with Python’s `asyncio` framework.
They are ideal when your application needs to stay responsive or handle
multiple concurrent tasks.

Recommended when:

- you're developing a **graphical interface**, e.g. using PySide or Qt
- you're running a **web server** or interactive dashboard
- you're building a **data pipeline** or real-time monitor
- your environment is already using `asyncio`

Comparison Summary
..................

.. list-table::
   :widths: 30 30
   :header-rows: 1

   * - Use case
     - Recommended client
   * - Simple scripts or tests
     - synchronous
   * - Terminal monitoring tools
     - synchronous
   * - GUI or interactive tools
     - asynchronous
   * - Web servers or dashboards
     - asynchronous
   * - Applications already using asyncio
     - asynchronous
   * - Avoiding async complexity
     - synchronous
