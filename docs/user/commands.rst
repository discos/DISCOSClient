Sending commands to DISCOS
==========================

The :class:`~discos_client.client.DISCOSClient` provides a simple interface to
send remote commands to the telescope control software.

Command interface
-----------------

If the client is correctly authenticated, it exposes a
:meth:`~discos_client.client.DISCOSClient.command` method. This method allows
you to send a command name along with any required arguments.

To send a simple command:

.. code-block:: python

   >>> answer = SRT.command("setupKKG")
   >>> print(answer)
   {'executed': True, 'command': 'setupKKG'}

To send a command with arguments:

.. code-block:: python

   >>> answer = SRT.command("goTo", 180, 45)
   >>> print(answer)
   {'executed': True, 'command': 'goTo'}


Client authentication
---------------------

In order for a client to be able to send commands to DISCOS, it has to
authenticate itself to the server. The authentication mechanism uses
`CurveZMQ <http://curvezmq.org/>`_, an authentication and encryption protocol
for ZeroMQ based on secure elliptic-curve cryptography.
The DISCOSClient package comes with an utility script capable of generating a
pair of CurveZMQ keys and store them in the default DISCOSClient configuration
directory.

How to generate the keys
........................

The generation process:
1. Creates a configuration directory in the standard user path.
2. Generates a public key (``identity.key``) and a secret key (``identity.key_secret``).
3. Sets appropriate file permissions (644 for public, 600 for secret) on POSIX systems.

Usage
.....

You can run the generator from your terminal:

.. code-block:: bash

   discos-keygen [options]

* ``--overwrite``: Replace existing keys.
* ``--show-only``: Prints the current public key and its path without generating new ones.

.. warning::
   **Never share your secret key!** Only the ``identity.key`` file should be shared.
   The ``identity.key_secret`` file **must** remain private.

Authorization Process
~~~~~~~~~~~~~~~~~~~~~

To be authorized to send commands to any of the telescopes:

#. Generate your keys with ``discos-keygen``.
#. Locate your ``identity.key`` file.
#. Send a copy of the ``identity.key`` file to the **DISCOS team**,
   asking for authorization for the desired telescopes. Your request
   will be reviewed and you will hear back from the team.
