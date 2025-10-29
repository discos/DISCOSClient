Internal Classes
================

These are the core classes used to implement the behavior of the DISCOS client
system. In general, users interacts primarily with a specific telescope client:
:class:`SRTClient`, :class:`MedicinaClient` or :class:`NotoClient`, but they can
also use the more general :class:`~discos_client.client.DISCOSClient`
providing IP address and port of the DISCOS Manager machine (for example when
connecting to a simulated instance of DISCOS). All values read inside the client are
:class:`~discos_client.namespace.DISCOSNamespace` objects.

DISCOSClient
------------

.. autoclass:: discos_client.client.DISCOSClient
   :members:

DISCOSNamespace
---------------

.. autoclass:: discos_client.namespace.DISCOSNamespace
   :members:
