Setup
=====

In order to install **DISCOSClient**, the first thing to do is to clone the
repository with `git`:

.. code-block:: bash

   git clone https://github.com/discos/DISCOSClient.git

...or download it as a ``zip`` archive from
`the repository official web page <https://github.com/discos/DISCOSClient/>`_.

To install it on **Linux**, **macOS** or **Windows**, , move into the
**DISCOSClient** directory and install it by running:

.. code-block:: bash

   cd DISCOSClient
   pip install .

The last executed command will install the package along with its only required
dependency: `pyzmq`.

Verifying the installation
--------------------------

After installation, you can verify that ZeroMQ and its Python bindings are correctly
installed by performing this small test:

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
