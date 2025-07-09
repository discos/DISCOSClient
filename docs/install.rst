Installation
============

To install **DISCOSClient** on **Linux**, **macOS**, or **Windows**, simply run:

.. code-block:: bash

   pip install .

This command installs the package along with its only required dependency:
`pyzmq`.

Verifying the installation
--------------------------

After installation, you can verify that ZeroMQ and its Python bindings are correctly installed:
To check that everything is working correctly, you can run this small test:

.. code-block:: python

   import zmq
   print(zmq.zmq_version(), zmq.__version__)

If you see version numbers printed without errors, you're ready to use DISCOSClient.

.. note::

   If you're using **Alpine Linux** or another system based on **musl libc**,
   precompiled wheels for `pyzmq` may not be available.

   In that case, install the ZeroMQ development libraries before installing the
   package:

   .. code-block:: bash

      apk add zeromq-dev
      pip install .
