Minor Servos
============

The SRT Minor Servo schema differs from the Medicina and Noto relative schemas.
Below you can find its definition. The Medicina and Noto definition will be
added in the future.

.. jsonschema:: ../../discos_client/schemas/srt/minor_servo.json#/$defs/boss/properties/boss
   :hide_key: /**/$id

.. jsonschema:: ../../discos_client/schemas/srt/minor_servo.json#/$defs/minor_servo/patternProperties/^(?!boss$).*
   :hide_key: /**/$id

.. jsonschema:: ../../discos_client/schemas/srt/minor_servo.json#/$defs/error_code
   :hide_key: /**/$id

.. jsonschema:: ../../discos_client/schemas/srt/minor_servo.json#/$defs/translation_axis_info
   :hide_key: /**/$id

.. jsonschema:: ../../discos_client/schemas/srt/minor_servo.json#/$defs/rotation_axis_info
   :hide_key: /**/$id
