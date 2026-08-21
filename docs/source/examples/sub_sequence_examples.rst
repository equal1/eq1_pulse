Sub-Sequence Examples
=====================

.. note::

   These examples are provided for **illustration purposes only** and may not represent realistic experimental parameters or physical hardware configurations. They demonstrate the API usage patterns rather than actual quantum device specifications.

Sub-sequences enable modular composition of pulse programs by encapsulating reusable operation blocks within a sequence context.

Basic Sub-Sequence
------------------

Creating and using a simple sub-sequence:

.. literalinclude:: ../../../examples/sub_sequence_example.py
   :language: python
   :pyobject: example_basic_sub_sequence

Reusable Blocks
---------------

Defining reusable gate sequences:

.. literalinclude:: ../../../examples/sub_sequence_example.py
   :language: python
   :pyobject: example_reusable_blocks

Sub-Sequences in Loops
-----------------------

Using sub-sequences within control flow:

.. literalinclude:: ../../../examples/sub_sequence_example.py
   :language: python
   :pyobject: example_sub_sequence_in_loops

Nested Sub-Sequences
--------------------

Composing sub-sequences hierarchically:

.. literalinclude:: ../../../examples/sub_sequence_example.py
   :language: python
   :pyobject: example_nested_sub_sequences

Active Reset with Sub-Sequences
--------------------------------

Implementing active reset using sub-sequences:

.. literalinclude:: ../../../examples/sub_sequence_example.py
   :language: python
   :pyobject: example_active_reset_with_sub_sequences

Multi-Qubit Operations
----------------------

Coordinating operations across multiple qubits:

.. literalinclude:: ../../../examples/sub_sequence_example.py
   :language: python
   :pyobject: example_multi_qubit_with_sub_sequences

Running the Examples
--------------------

Execute the complete example script:

.. code-block:: bash

    python examples/sub_sequence_example.py

See Also
--------

* :doc:`/experimental/schedule` - Sub-schedule examples with explicit timing (unused, experimental)
* :doc:`/user_guide/builder_guide` - Builder interface documentation
* :doc:`/autoapi/eq1_pulse/builder/index` - Builder API reference
