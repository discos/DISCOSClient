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
   :special-members: __init__, __del__, __initialize__, __to_namespace__, __update_namespace__, __public_dict__, __format__, __str__, __repr__

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
   :special-members: __init__, __value_operation__, __repr__, __str__,
                     __int__, __float__, __neg__, __bool__, __getitem__,
                     __len__, __iter__, __setattr__, __delattr__,
                     __ilshift__, __format__, __deepcopy__,
                     __get_value__, __has_value__, __is__,
                     __public_dict__, __value_repr__
