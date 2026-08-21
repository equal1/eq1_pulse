Schedules (Experimental)
========================

.. warning::

    ``Schedule`` and the ``eq1_pulse.builder.experimental`` API it is built with are **unused
    and scheduled for removal.** New code should express timing with :mod:`eq1_pulse.builder`
    sequences instead (:doc:`/user_guide/builder_guide`).

This page collects everything about the experimental, explicitly-timed schedule API: what a
schedule is, how sub-schedules compose, the ``@nested_schedule`` decorator, and how it compares to
the supported ``@nested_sequence`` decorator.

What Is a Schedule
------------------

A **schedule** provides explicit timing control with reference points. Each operation can specify
when it starts relative to another operation.

.. code-block:: python

    from eq1_pulse.builder import experimental, square_pulse

    with experimental.build_schedule() as sched:
        # First operation
        op1 = experimental.play("qubit", square_pulse(duration="100ns", amplitude="50mV"))

        # Second operation starts 200ns after first operation ends
        op2 = experimental.play(
            "qubit",
            square_pulse(duration="100ns", amplitude="30mV"),
            ref_op=op1,
            ref_pt="end",
            rel_time="200ns"
        )

        # Readout starts when second pulse starts
        experimental.play(
            "readout",
            square_pulse(duration="500ns", amplitude="20mV"),
            ref_op=op2,
            ref_pt="start",
            ref_pt_new="start"
        )

Reference points can be:

* ``"start"`` - operation start time
* ``"center"`` - operation midpoint
* ``"end"`` - operation end time

Playing Pulses in a Schedule
-----------------------------

``experimental.play()`` accepts the same pulse-construction arguments as the sequence-side
``play()``, plus the schedule timing parameters:

.. code-block:: python

    from eq1_pulse.builder import experimental

    with experimental.build_schedule() as sched:
        experimental.play(
            "drive",
            square_pulse(duration="10us", amplitude="100mV"),
            ref_op=ref_operation,
            ref_pt="end",
            rel_time="5us"
        )

Sub-Schedules
-------------

.. note::

   These examples are provided for **illustration purposes only** and may not represent realistic experimental parameters or physical hardware configurations. They demonstrate the API usage patterns rather than actual quantum device specifications.

Sub-schedules enable modular composition with explicit timing control by encapsulating operation blocks within a schedule context.

Basic Sub-Schedule
~~~~~~~~~~~~~~~~~~~

Creating and positioning a simple sub-schedule:

.. literalinclude:: ../../../examples/experimental/sub_schedule_example.py
   :language: python
   :pyobject: example_basic_sub_schedule

Quantum Experiment with Sub-Schedules
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Structuring a complete experiment using sub-schedules:

.. literalinclude:: ../../../examples/experimental/sub_schedule_example.py
   :language: python
   :pyobject: example_quantum_experiment_with_sub_schedules

Parallel Operations
~~~~~~~~~~~~~~~~~~~~

Coordinating parallel operations using sub-schedules:

.. literalinclude:: ../../../examples/experimental/sub_schedule_example.py
   :language: python
   :pyobject: example_parallel_operations_with_sub_schedules

Reusable Sub-Schedules
~~~~~~~~~~~~~~~~~~~~~~~

Creating and reusing sub-schedule blocks:

.. literalinclude:: ../../../examples/experimental/sub_schedule_example.py
   :language: python
   :pyobject: example_reusable_sub_schedules

Running the sub-schedule examples:

.. code-block:: bash

    python examples/experimental/sub_schedule_example.py

The ``@nested_schedule`` Decorator
------------------------------------

Use ``@nested_schedule`` to create reusable schedule blocks that need explicit timing control.
Functions decorated with ``@nested_schedule`` return a :class:`ScheduleBlock` object that must be
passed to :func:`add_block` along with schedule timing parameters.

**Basic Usage:**

.. code-block:: python

    from eq1_pulse.builder import experimental, full_integration, square_pulse

    @experimental.nested_schedule
    def initialize_qubit(qubit: str):
        """Initialize a qubit to ground state."""
        experimental.play(qubit, square_pulse(duration="100ns", amplitude="200mV"))
        experimental.wait(qubit, duration="50ns")

    @experimental.nested_schedule
    def rabi_drive(qubit: str, amplitude: str):
        """Apply a Rabi drive pulse."""
        experimental.play(qubit, square_pulse(duration="50ns", amplitude=amplitude))

    @experimental.nested_schedule
    def measure_qubit(drive_ch: str, readout_ch: str, result_var: str):
        """Measure a qubit."""
        experimental.play(drive_ch, square_pulse(duration="1us", amplitude="50mV"))
        experimental.record(readout_ch, var=result_var, duration="1us", integration=full_integration())

    # Use the building blocks in a schedule
    with experimental.build_schedule() as sched:
        # Call the function to create a block, then add it with timing
        init_token = experimental.add_block(initialize_qubit("qubit0"), op_name="init")

        # Position subsequent blocks relative to previous operations
        rabi_token = experimental.add_block(
            rabi_drive("qubit0", "150mV"),
            op_name="rabi",
            ref_op=init_token,
            ref_pt="end",
            rel_time="10ns"
        )

        experimental.add_block(
            measure_qubit("drive0", "readout0", "result"),
            op_name="measure",
            ref_op=rabi_token,
            ref_pt="end",
            rel_time="50ns"
        )

**Key Points:**

- The decorated function returns a :class:`ScheduleBlock` (not :obj:`None`)
- You must pass this block to :func:`add_block` to insert it into the schedule
- :func:`add_block` takes schedule timing parameters (``name``, ``ref_op``, ``ref_pt``, ``rel_time``)
- :func:`add_block` returns an :class:`OperationToken` for referencing this block
- Can only be used in schedule contexts (will error if called in sequence contexts)
- If you don't call :func:`add_block` on a returned block, you'll get a runtime error when the schedule context closes

**Visual Explanation:**

The diagram below shows how ``@nested_schedule`` decorated functions create schedule blocks that are positioned with ``add_block()``:

.. plot::
   :align: center
   :caption: @nested_schedule decorator with add_block usage.

   from experimental.nested_schedule_diagram import create_nested_schedule_diagram
   create_nested_schedule_diagram()

The diagram illustrates:

1. **Top section**: Decorator definitions for reusable schedule blocks
2. **Middle section**: Usage with ``add_block()`` providing timing parameters
3. **Bottom section**: Resulting timeline showing precise positioning with reference points and relative timing

**Error Handling:**

The builder tracks all :class:`ScheduleBlock` objects and ensures they are consumed:

.. code-block:: python

    with experimental.build_schedule() as sched:
        # This creates a block but doesn't add it - ERROR!
        block = initialize_qubit("qubit0")
        # RuntimeError when context closes: unconsumed ScheduleBlock

    # Correct usage:
    with experimental.build_schedule() as sched:
        experimental.add_block(initialize_qubit("qubit0"), op_name="init")  # ✓

Parallel Operations with Schedules
-------------------------------------

Schedule building blocks shine when you need parallel execution:

.. code-block:: python

    @experimental.nested_schedule
    def two_qubit_gate(control: str, target: str, angle: str):
        """Two-qubit controlled rotation gate."""
        experimental.play(control, square_pulse(duration="40ns", amplitude="100mV"))
        experimental.play(target, square_pulse(duration="40ns", amplitude="100mV"))
        experimental.shift_phase(target, angle)

    with experimental.build_schedule() as sched:
        # Initialize both qubits in parallel (same start time)
        init0 = experimental.add_block(initialize_qubit("qubit0"), op_name="init0")
        experimental.add_block(
            initialize_qubit("qubit1"),
            op_name="init1",
            ref_op=init0,
            ref_pt="start"  # Start at same time as init0
        )

        # Apply gates with precise timing
        gate0 = experimental.add_block(
            rabi_drive("qubit0", "140mV"),
            op_name="gate0",
            ref_op=init0,
            ref_pt="end",
            rel_time="20ns"
        )

        gate1 = experimental.add_block(
            two_qubit_gate("qubit0", "qubit1", "45deg"),
            op_name="cnot",
            ref_op=gate0,
            ref_pt="start"  # Start at same time as gate0
        )

        # Measure both in parallel
        meas0 = experimental.add_block(
            measure_qubit("drive0", "readout0", "r0"),
            ref_op=gate1,
            ref_pt="end",
            rel_time="100ns"
        )

        experimental.add_block(
            measure_qubit("drive1", "readout1", "r1"),
            ref_op=meas0,
            ref_pt="start"  # Start at same time as meas0
        )

This creates a schedule where:

- Both qubits are initialized simultaneously
- The two-qubit gate starts when the single-qubit gate starts
- Both measurements execute in parallel

``@nested_sequence`` vs. ``@nested_schedule``
------------------------------------------------

**Side-by-Side Comparison:**

.. plot::
   :align: center
   :caption: Comparison of @nested_sequence vs @nested_schedule decorators.

   from decorator_comparison_diagram import create_decorator_comparison_diagram
   create_decorator_comparison_diagram()

**Feature Comparison Table:**

+---------------------------+----------------------------+----------------------------+
| Feature                   | ``@nested_sequence``       | ``@nested_schedule``       |
+===========================+============================+============================+
| Context                   | Sequences only             | Schedules only             |
+---------------------------+----------------------------+----------------------------+
| Return value              | :obj:`None`                | :class:`ScheduleBlock`     |
+---------------------------+----------------------------+----------------------------+
| Usage                     | Call directly              | Pass to :func:`add_block`  |
+---------------------------+----------------------------+----------------------------+
| Timing control            | Implicit (sequential)      | Explicit (ref points)      |
+---------------------------+----------------------------+----------------------------+
| Parallel operations       | No                         | Yes                        |
+---------------------------+----------------------------+----------------------------+

.. important::

   **Sequences and schedules cannot be mixed!**

   - ``@nested_sequence`` decorated functions can **only** be called within ``build_sequence()`` contexts
   - ``@nested_schedule`` decorated functions can **only** be called within ``experimental.build_schedule()`` contexts
   - You cannot nest a schedule inside a sequence, or vice versa
   - If you need both sequential operations and explicit timing, choose one approach for your entire program (sequences are the supported choice -- see :doc:`/user_guide/builder_guide`)

Complete Example
-----------------

A multi-qubit experiment combining a ``@nested_sequence`` gate library with
``@nested_schedule`` calibration blocks, as they could be used side by side before the
schedule API is removed:

.. code-block:: python

    from eq1_pulse.builder import build_sequence, experimental, full_integration, nested_sequence, play, square_pulse

    # ========== Gate library (sequences) ==========

    @nested_sequence
    def x90_gate(qubit: str):
        """π/2 rotation around X axis."""
        play(qubit, square_pulse(duration="10ns", amplitude="100mV"))

    # ========== Calibration blocks (schedules) ==========

    @experimental.nested_schedule
    def qubit_reset(qubit: str):
        """Active reset protocol."""
        experimental.play(qubit, square_pulse(duration="100ns", amplitude="200mV"))
        experimental.wait(qubit, duration="1us")

    @experimental.nested_schedule
    def dispersive_readout(drive: str, readout: str, result: str):
        """Standard dispersive readout."""
        experimental.play(drive, square_pulse(duration="2us", amplitude="40mV"))
        experimental.record(readout, var=result, duration="2us", integration=full_integration())

    # ========== Use in sequence context ==========

    with build_sequence() as seq:
        x90_gate("q0")

    # ========== Use in schedule context ==========

    with experimental.build_schedule() as sched:
        experimental.var_decl("r0", "complex", unit="mV")

        reset0 = experimental.add_block(qubit_reset("q0"), op_name="reset0")
        experimental.add_block(
            dispersive_readout("drive0", "readout0", "r0"),
            op_name="readout0",
            ref_op=reset0,
            ref_pt="end",
            rel_time="50ns"
        )

See Also
--------

* :doc:`/user_guide/builder_guide` - The supported, sequence-only builder interface
* :doc:`/examples/sub_sequence_examples` - Sub-sequence examples with implicit timing
* :doc:`/autoapi/eq1_pulse/builder/index` - Builder API reference
