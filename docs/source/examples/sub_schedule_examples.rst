Sub-Schedule Examples
=====================

.. note::

   These examples are provided for **illustration purposes only** and may not represent realistic experimental parameters or physical hardware configurations. They demonstrate the API usage patterns rather than actual quantum device specifications.

Sub-schedules enable modular composition with explicit timing control by encapsulating operation blocks within a schedule context.

Basic Sub-Schedule
------------------

Creating and positioning a simple sub-schedule:

.. literalinclude:: ../../../examples/sub_schedule_example.py
   :language: python
   :pyobject: example_basic_sub_schedule

Quantum Experiment with Sub-Schedules
--------------------------------------

Structuring a complete experiment using sub-schedules:

.. literalinclude:: ../../../examples/sub_schedule_example.py
   :language: python
   :pyobject: example_quantum_experiment_with_sub_schedules

Parallel Operations
-------------------

Coordinating parallel operations using sub-schedules:

.. literalinclude:: ../../../examples/sub_schedule_example.py
   :language: python
   :pyobject: example_parallel_operations_with_sub_schedules

Reusable Sub-Schedules
-----------------------

Creating and reusing sub-schedule blocks:

.. literalinclude:: ../../../examples/sub_schedule_example.py
   :language: python
   :pyobject: example_reusable_sub_schedules

Running the Examples
--------------------

Execute the complete example script:

.. code-block:: bash

    python examples/sub_schedule_example.py

See Also
--------

* :doc:`sub_sequence_examples` - Sub-sequence examples with implicit timing
* :doc:`/user_guide/builder_guide` - Builder interface documentation
* :doc:`/autoapi/eq1_pulse/builder/index` - Builder API reference
