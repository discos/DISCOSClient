Internal Classes
================

These are the core classes used to implement the behavior of the DISCOS client system.
In general, users should interact only with :class:`DISCOSClient`, which serves as a factory.
The other classes are provided for advanced usage or internal reference.

DISCOSClient
------------

.. autoclass:: discos_client.client.DISCOSClient
   :members:
   :special-members: __new__

BaseClient
----------

.. autoclass:: discos_client.client.BaseClient
   :members:
   :special-members:
   :skip-members: __weakref__

SyncClient
----------

.. autoclass:: discos_client.client.SyncClient
   :members:
   :show-inheritance:

AsyncClient
-----------

.. autoclass:: discos_client.client.AsyncClient
   :members:
   :show-inheritance:

DISCOSNamespace
---------------

.. autoclass:: discos_client.namespace.DISCOSNamespace
   :members:
   :special-members:
   :skip-members: __eq__, __ge__, __gt__, __le__, __lt__, __ne__, __weakref__
