Accessing telemetry data
========================

Clients maintain an internal view of the most recent values for each
subscribed topic. You can access these data directly, at any time,
without blocking, via Python dot notation.

.. code-block:: python

   az = SRT.mount.azimuth.currentPosition

Every node of the inner structure held by the client, is a
:class:`~discos_client.namespace.DISCOSNamespace` object
instance. These namespace nodes are organized as a live, nested tree
that mirrors the structure of each DISCOS telemetry topic: branches represent
JSON objects, leaves represent primitive values (numbers, booleans, strings,
lists). The entire tree updates in place as new messages are received.

Since the whole tree is constantly updated, we provide several ways of
accessing members, to cover different scenarios.

Accessing the value of a leaf :class:`~discos_client.namespace.DISCOSNamespace` object
--------------------------------------------------------------------------------------

The method shown above provides access to a
:class:`~discos_client.namespace.DISCOSNamespace` node of the status tree.




This class acts as a wrapper for the inner value, allowing it to be part of comparisons
and operations just like you were working with a pure string, integer, floating point
number or boolean value. In case you are accessing a leaf node of the tree, you may want
to access the internal value directly instead of using this wrapper functionality.
In order to retrieve the internal value, the
:class:`~discos_client.namespace.DISCOSNamespace` class offers a method called
:meth:`~discos_client.namespace.DISCOSNamespace.get_value`.

.. code-block:: python

   projectCode = SRT.scheduler.projectCode
   # projectCode is a DISCOSNamespace object
   projectCode = SRT.scheduler.projectCode.get_value()
   # projectCode is now a pure str object

Most of the times you won't need to access inner values, but for more complex
operations, sometimes your Python distribution might raise some exceptions when
using a :class:`~discos_client.namespace.DISCOSNamespace` object
as indexer for a list or a dictionary. In case you bump into some weird behavior,
try using :meth:`~discos_client.namespace.DISCOSNamespace.get_value`. You will
also benefit in case you need to work with a fixed value and avoid the continuous
updating of a :class:`~discos_client.namespace.DISCOSNamespace` node.


Immutable snapshots with :meth:`~discos_client.namespace.DISCOSNamespace.copy`
------------------------------------------------------------------------------

Some application might want to access several values together, all of them
contained in a single node or received via the same message. Since the structure
is constantly updated, accessing different values directly as shown above might
lead to a scenario where property 1 is read at time t0 and property 2 is read
at time t1. In order to avoid this, a copy of the parent node can be retrieved
with the :meth:`~discos_client.namespace.DISCOSNamespace.copy` method.

.. code-block:: python

   mount = SRT.mount.copy()
   az, el = mount.azimuth.currentPosition, mount.elevation.currentPosition

Waiting for updates with :meth:`~discos_client.namespace.DISCOSNamespace.wait`
------------------------------------------------------------------------------

Sometimes you only need to check the value of a property for changes, for
example, when a new subscan is being performed, or to check if the antenna was
stowed due to high winds. The :meth:`~discos_client.namespace.DISCOSNamespace.wait`
method comes to your help.

.. code-block:: python

   elevationMode = SRT.mount.elevation.currentMode.wait()

The code above will block until the inner value of the desired node is changed.
Calling :meth:`~discos_client.namespace.DISCOSNamespace.wait` without any argument
will block indefinitely, but an optional argument ``timeout`` can be provided.

.. code-block:: python

   elevationMode = SRT.mount.elevation.currentMode.wait(timeout=5)

In this example, the software waits at most for 5 seconds before returning a
value. If the timeout expires, the current value of the node is returned,
without it being updated.

React to updates with :meth:`~discos_client.namespace.DISCOSNamespace.bind` and :meth:`~discos_client.namespace.DISCOSNamespace.unbind`
---------------------------------------------------------------------------------------------------------------------------------------
The :meth:`~discos_client.namespace.DISCOSNamespace.wait` method shown above
blocks and waits for an update of the desired node before going forward with
code execution. If you need execution to go through, a different approach is
needed. The :meth:`~discos_client.namespace.DISCOSNamespace.bind` method lets
you register a callback function that will be executed when the desired value
changes.

.. code-block:: python

   def printValue(value):
       print(value)

   SRT.scheduler.tracking.bind(printValue)
   ...
   True

The example above will call the simple ``printValue`` function, which will print
the value of scheduler.tracking as soon as it changes. The three dots ... represent
some other code that the application will continue to execute in the main thread.

A callback registered with :meth:`~discos_client.namespace.DISCOSNamespace.bind`
might not be needed anymore at some point in time. The
:meth:`~discos_client.namespace.DISCOSNamespace.unbind` method is used to
detach the callback from the given node.

.. code-block:: python

   def printValue(value):
       print(value)

   SRT.scheduler.tracking.bind(printValue)
   ...
   # callback not needed anymore, unregister it
   SRT.scheduler.tracking.unbind(printValue)

The examples show a very minimal approach to react to an updated value. By
implementing a more complete callback logic you can handle more complex
scenarios.
The :meth:`~discos_client.namespace.DISCOSNamespace.unbind` method can also
be called without any argument. By doing so, the given
:class:`~discos_client.namespace.DISCOSNamespace` node will unregister all
callbacks that were previously registered to it.

Exploiting predicates for :meth:`~discos_client.namespace.DISCOSNamespace.wait` and :meth:`~discos_client.namespace.DISCOSNamespace.bind`
-----------------------------------------------------------------------------------------------------------------------------------------
The :meth:`~discos_client.namespace.DISCOSNamespace.wait` and
:meth:`~discos_client.namespace.DISCOSNamespace.bind` methods also allow a
user to provide a predicate as an argument. This functionality allow more complex
filtering for the new value, and can be useful for several situations. Below is
an example of a code that is executed only whenever the elevation axis of the
antenna gets stowed, using the :meth:`~discos_client.namespace.DISCOSNamespace.wait`
method.

.. code-block:: python

   SRT.mount.elevation.currentMode.wait(predicate=lambda value: value == "STOW")
   ...
   # send an alarm to someone that is waiting for the antenna to be stowed

The same principle can be applied to the
:meth:`~discos_client.namespace.DISCOSNamespace.bind` method. The following
example shows how to bind a callback that would send an alarm via e-mail
whenever the temperature of the cool head of the SRTKBandMFReceiver is greater
or equal to 30K.

.. code-block:: python

   def sendAlarm(value):
       ...
       # generic implementation of a function that sends an alarm via e-mail

   # bind the sendAlarm function
   SRT.receivers.SRTKBandMFReceiver.cryoTemperatureCoolHead.bind(
      sendAlarm,
      predicate=lambda value: value >= 30
   )
   ...
   # execution of other code, the callback will be called by the client
   # updating thread whenever a new value satisfying the predicate is
   # received
   ...
   # unbind the sendAlarm function
   SRT.receivers.SRTKBandMFReceiver.cryoTemperatureCoolHead.unbind(sendAlarm)

In both :meth:`~discos_client.namespace.DISCOSNamespace.bind` examples, both with
and without a predicate, the given callback function is supposed to only receive
one argument, shown as ``value``. The received object will always be the same
:class:`~discos_client.namespace.DISCOSNamespace` node on which
the :meth:`~discos_client.namespace.DISCOSNamespace.bind` method was called,
meaning that inside the callback we can also perform the
:meth:`~discos_client.namespace.DISCOSNamespace.unbind` operation, making
the callback a one-time called function.

.. code-block:: python

   def sendAlarm(value):
       ...
       # generic implementation of a function that sends an alarm via e-mail
       ...
       # now unregister the callback so that the alarm will not be sent again
       value.unbind(sendAlarm)

   # bind the sendAlarm function
   SRT.receivers.SRTKBandMFReceiver.cryoTemperatureCoolHead.bind(
      sendAlarm,
      predicate=lambda value: value >= 30
   )

In the last example, the ``sendAlarm`` callback is called once as soon as the
newly received value for cryoTemperatureCoolHead of the SRTKBandMFReceiver is
greater or equal to 30K. As soon as the alarm logic is executed, the callback
can be unregistered, preventing the application to send another unwanted alarm.
The callback must be registered again later if you would like to receive
another alarm if the temperature rises again.

Tips and best practices
-----------------------

* Use :meth:`~discos_client.namespace.DISCOSNamespace.copy` or
  :meth:`~discos_client.namespace.DISCOSNamespace.get_value` before doing long
  processing so that the value stays the same
* Always unregister callbacks you no longer need with
  :meth:`~discos_client.namespace.DISCOSNamespace.unbind` so that code is not
  executed again and again
* Refer to the :class:`~discos_client.namespace.DISCOSNamespace` class for more details.
