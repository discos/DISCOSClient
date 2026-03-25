Creating and Configuring a Client
=================================

The :class:`~discos_client.client.DISCOSClient` is the entry point for all
interactions with the telescope. Whether you are connecting to a real telescope
(SRT, Medicina, Noto) or a simulated environment, the client handles the
underlying ZeroMQ connections and maps the incoming telemetry into a structured
Python object tree based on the telescope's metadata definitions.

.. note::
    For a complete list of methods and attributes, please refer to the
    :doc:`/api/api` section.

Connecting to DISCOS
-------------------------------

The library provides three specialized classes pre-configured for the production
environments of INAF's single-dish radio telescopes. Using these classes is the
recommended way to connect, as they automatically handle:

1. **Network Configuration**: IP addresses and Ports are pre-filled.
2. **Metadata Loading**: They automatically load the correct telescope-specific
   schemas (e.g., specific *mount* or *minor_servo* structures) to build the
   object hierarchy and expose descriptions and units.

You can initialize a client by simply importing the class corresponding to your
observatory:

**Sardinia Radio Telescope (SRT)**

.. code-block:: python

   from discos_client import SRTClient
   # Connects to SRT and subscribes to "mount" and "antenna" topics
   SRT = SRTClient("mount", "antenna")

**Medicina Radio Telescope**

.. code-block:: python

   from discos_client import MedicinaClient
   # Subscribes to ALL available topics
   MED = MedicinaClient()

**Noto Radio Telescope**

.. code-block:: python

   from discos_client import NotoClient
   NOTO = NotoClient()

Topic Subscription
~~~~~~~~~~~~~~~~~~

When creating a client, the arguments you pass (e.g., ``"mount"``, ``"antenna"``) determine
which telemetry data you will receive.

* **Specific Topics:** If you provide strings as arguments, the client subscribes *only* to those topics. This is bandwidth-efficient and recommended for specific control scripts.
* **All Topics:** If no arguments are provided, the client defaults to subscribing to **all** available telemetry topics for that telescope.

.. seealso::
    See :ref:`schemas` for a detailed description of the data structures and metadata
    available for each topic.

Connecting to Custom or Simulated Environments
----------------------------------------------

If you are developing offline (e.g., using a Virtual Machine) or connecting to a
simulator, the specialized classes cannot be used as the network addresses will differ.
In this scenario, you must use the generic :class:`~discos_client.client.DISCOSClient`.

When using the generic client, you **must** specify two key parameters:

1. **address**: The IP address of the custom DISCOS Manager.
2. **telescope**: The telescope identifier (e.g., ``"SRT"``). This is crucial because
   it tells the library which JSON schemas to load to correctly populate the object tree.

**Example: Connecting to a simulated DISCOS instance**

.. code-block:: python

   from discos_client import DISCOSClient

   # Connect to a local VM simulating SRT
   # Note: We explicitly request the "active_surface" topic
   client = DISCOSClient("active_surface", address="192.168.56.200", telescope="SRT")

.. warning::
   **Metadata Consistency**
   If you omit the ``telescope`` argument, the client will fall back to a "generic mode".
   It will only load common schemas (like ``antenna``, ``weather``, ``scheduler``).
   Telescope-specific components such as ``active_surface``, ``minor_servo``, and
   ``mount`` **will not appear**, as their definition is station-specific.
