Builder Interface Examples
==========================

.. note::

   These examples are provided for **illustration purposes only** and may not represent realistic experimental parameters or physical hardware configurations. They demonstrate the API usage patterns rather than actual quantum device specifications.

This page demonstrates the core builder interface patterns through complete, runnable examples.

Simple Sequence
---------------

A basic pulse sequence with operations on multiple channels:

.. literalinclude:: ../../../examples/builder_example.py
   :language: python
   :pyobject: example_simple_sequence

Schedule with Positioning
--------------------------

Using schedules for explicit timing control with reference points:

.. literalinclude:: ../../../examples/builder_example.py
   :language: python
   :pyobject: example_schedule_with_positioning

Repetition
----------

Repeating operations a fixed number of times:

.. literalinclude:: ../../../examples/builder_example.py
   :language: python
   :pyobject: example_with_repetition

Iteration
---------

Looping over parameter values:

.. literalinclude:: ../../../examples/builder_example.py
   :language: python
   :pyobject: example_with_iteration

Conditional Execution
---------------------

Using measurements and conditional logic:

.. literalinclude:: ../../../examples/builder_example.py
   :language: python
   :pyobject: example_with_conditional

Measurement Operations
----------------------

Performing measurements with integration:

.. literalinclude:: ../../../examples/builder_example.py
   :language: python
   :pyobject: example_measurement

Complete Program
----------------

A comprehensive example combining multiple concepts:

.. literalinclude:: ../../../examples/builder_example.py
   :language: python
   :pyobject: example_complex_program

Running the Examples
--------------------

Execute the complete example script:

.. code-block:: bash

    python examples/builder_example.py

See Also
--------

* :doc:`basic_usage` - Quick reference for basic operations
* :doc:`/user_guide/builder_guide` - Complete builder interface documentation
* :doc:`/autoapi/eq1_pulse/builder/index` - Builder API reference
