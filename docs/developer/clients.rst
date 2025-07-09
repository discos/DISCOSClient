Out of the box Clients
======================

The `DISCOSClient` can be instantiated for different telescopes using
predefined functions named after the supported observatories.

These helper functions automatically configure the network settings
and telescope name for you. You only need to specify the topics you want
to subscribe to, and whether you prefer synchronous or asynchronous behavior.

.. |topics| replace:: One or more topic names to subscribe to.
.. |async| replace:: Whether to create an asynchronous client. Defaults to ``False``.
.. |rettype| replace:: :class:`~discos_client.client.SyncClient` | :class:`~discos_client.client.AsyncClient`
.. |return| replace:: An instance of :class:`~discos_client.client.SyncClient` or :class:`~discos_client.client.AsyncClient`

SRTClient
---------

.. function:: SRTClient(*topics: str, asynchronous: bool = False)

   Creates a client configured for the **Sardinia Radio Telescope (SRT)**.

   :param topics: |topics|
   :type topics: str
   :param asynchronous: |async|
   :type asynchronous: bool
   :return: |return|
   :return type: |rettype|

MedicinaClient
--------------

.. function:: MedicinaClient(*topics: str, asynchronous: bool = False)

   Creates a client configured for the **Medicina Radio Telescope**.

   :param topics: |topics|
   :type topics: str
   :param asynchronous: |async|
   :type asynchronous: bool
   :return: |return|
   :return type: |rettype|

NotoClient
----------

.. function:: NotoClient(*topics: str, asynchronous: bool = False)

   Creates a client configured for the **Noto Radio Telescope**.

   :param topics: |topics|
   :type topics: str
   :param asynchronous: |async|
   :type asynchronous: bool
   :return: |return|
   :return type: |rettype|
