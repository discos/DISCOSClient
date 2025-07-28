Messages JSON Schemas
=====================

The following sections contain the message schemas, describing the properties
each schema includes, along with their title, unit of measure, and description.
Some messages are sent by DISCOS components common to all three telescopes,
while others are station-specific. Although certain messages may be delivered
on the same topics, their structure might differ depending on the station.

.. jsonschema:: example.json
   :auto_reference: true
   :lift_definitions: true

More details regarding each schema can be found in the following sections.

.. toctree::
   :maxdepth: 2

   definitions
   scheduler
   antenna
   mount
   receivers
   weather
