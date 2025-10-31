Builder Interface Guide
=======================

The builder interface provides a high-level, Pythonic API for constructing pulse sequences and schedules. It uses Python context managers and provides functions that closely mirror the underlying model structure while offering a more intuitive programming experience.

Getting Started
---------------

Import the builder functions:

.. code-block:: python

    from eq1_pulse.builder import *

Building Sequences vs. Schedules
---------------------------------

Sequences
~~~~~~~~~

A **sequence** is an ordered list of operations where timing is implicit. Operations on the same channel execute sequentially.

.. code-block:: python

    with build_sequence() as seq:
        play("qubit", square_pulse(duration="100ns", amplitude="50mV"))
        wait("qubit", duration="50ns")
        play("qubit", square_pulse(duration="100ns", amplitude="50mV"))

In this sequence:

1. First pulse plays for 100ns
2. Then waits 50ns
3. Then second pulse plays for 100ns

Total time on the ``"qubit"`` channel: 250ns

Schedules
~~~~~~~~~

A **schedule** provides explicit timing control with reference points. Each operation can specify when it starts relative to another operation.

.. code-block:: python

    with build_schedule() as sched:
        # First operation
        op1 = play("qubit", square_pulse(duration="100ns", amplitude="50mV"))

        # Second operation starts 200ns after first operation ends
        op2 = play(
            "qubit",
            square_pulse(duration="100ns", amplitude="30mV"),
            ref_op=op1,
            ref_pt="end",
            rel_time="200ns"
        )

        # Readout starts when second pulse starts
        play(
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

Core Operations
---------------

Playing Pulses
~~~~~~~~~~~~~~

The ``play()`` function sends a pulse to a channel:

.. code-block:: python

    play(channel, pulse, name=None, **kwargs)

**In sequences:**

.. code-block:: python

    with build_sequence() as seq:
        play("drive", square_pulse(duration="10us", amplitude="100mV"))

**In schedules:**

.. code-block:: python

    with build_schedule() as sched:
        play(
            "drive",
            square_pulse(duration="10us", amplitude="100mV"),
            ref_op=ref_operation,
            ref_pt="end",
            rel_time="5us"
        )

Waiting
~~~~~~~

The ``wait()`` function creates a delay on a channel:

.. code-block:: python

    wait(channel, duration, **kwargs)

Example:

.. code-block:: python

    wait("qubit", duration="100ns")

Setting Frequency
~~~~~~~~~~~~~~~~~

The ``set_frequency()`` function changes the oscillator frequency for a channel:

.. code-block:: python

    set_frequency(channel, frequency, **kwargs)

Example:

.. code-block:: python

    set_frequency("qubit", frequency="5.2GHz")

    # Or with a variable
    set_frequency("qubit", var("freq"))

Setting Phase
~~~~~~~~~~~~~

The ``set_phase()`` function updates the phase of a channel:

.. code-block:: python

    set_phase(channel, phase, **kwargs)

Example:

.. code-block:: python

    set_phase("drive", phase="90deg")

Shifting Phase
~~~~~~~~~~~~~~

The ``shift_phase()`` function adds an offset to the current phase:

.. code-block:: python

    shift_phase(channel, phase, **kwargs)

Example:

.. code-block:: python

    shift_phase("drive", phase="45deg")

Barriers
~~~~~~~~

The ``barrier()`` function synchronizes multiple channels:

.. code-block:: python

    barrier(*channels)

Example:

.. code-block:: python

    # Ensure both channels reach this point before continuing
    barrier("drive", "readout")

    # After barrier, these start at the same time
    play("drive", pulse1)
    play("readout", pulse2)

Pulse Shapes
------------

Square Pulse
~~~~~~~~~~~~

A constant-amplitude rectangular pulse:

.. code-block:: python

    square_pulse(duration, amplitude, phase=None, rise_time=None, fall_time=None)

The ``rise_time`` and ``fall_time`` parameters define linear ramps at the beginning and end of the pulse,
enabling trapezoidal or ramp-shaped pulses. These times are included in the total pulse duration.

Example:

.. code-block:: python

    # Basic square pulse
    pulse = square_pulse(duration="100ns", amplitude="50mV")
    pulse = square_pulse(duration="100ns", amplitude="50mV", phase="90deg")

    # Ramp pulse with rise and fall times
    ramp = square_pulse(
        duration="100ns",
        amplitude="50mV",
        rise_time="10ns",
        fall_time="10ns"
    )

Sine Pulse
~~~~~~~~~~

A sinusoidal waveform:

.. code-block:: python

    sine_pulse(duration, amplitude, frequency, phase=None, to_frequency=None)

The ``to_frequency`` parameter enables frequency-swept (chirp) pulses. When specified, the frequency
linearly sweeps from ``frequency`` to ``to_frequency`` over the pulse duration.

Example:

.. code-block:: python

    # Basic sine pulse at fixed frequency
    pulse = sine_pulse(
        duration="1us",
        amplitude="30mV",
        frequency="5GHz",
        phase="0deg"
    )

    # Chirp pulse with frequency sweep
    chirp = sine_pulse(
        duration="1us",
        amplitude="30mV",
        frequency="5GHz",
        to_frequency="6GHz"
    )

External Pulse
~~~~~~~~~~~~~~

Reference a pulse shape defined in an external library or function:

.. code-block:: python

    external_pulse(function, duration, amplitude, params=None)

The ``function`` parameter should be a fully qualified name (e.g., ``"my_lib.gaussian"``).
The external function is expected to generate the pulse waveform.

Example:

.. code-block:: python

    # Reference a Gaussian pulse from external library
    pulse = external_pulse(
        "pulse_lib.gaussian",
        duration="200ns",
        amplitude="50mV",
        params={"sigma": "40ns"}
    )

    # Reference a DRAG pulse
    drag = external_pulse(
        "pulse_lib.drag",
        duration="200ns",
        amplitude="50mV",
        params={
            "sigma": "40ns",
            "beta": 0.5
        }
    )

Arbitrary Sampled Pulse
~~~~~~~~~~~~~~~~~~~~~~~~

Define a custom pulse using explicit sample points:

.. code-block:: python

    arbitrary_pulse(samples, duration, amplitude, interpolation=None, time_points=None)

Samples should be normalized (peak value of 1.0) and will be scaled by the amplitude.

Example:

.. code-block:: python

    # Triangle pulse
    triangle = arbitrary_pulse(
        samples=[0.0, 0.5, 1.0, 0.5, 0.0],
        duration="100ns",
        amplitude="50mV"
    )

    # Complex IQ pulse
    iq_samples = [0.0+0.0j, 0.5+0.3j, 1.0+0.0j, 0.5-0.3j, 0.0+0.0j]
    iq_pulse = arbitrary_pulse(
        samples=iq_samples,
        duration="80ns",
        amplitude="75mV",
        interpolation="linear"
    )

    # Pulse with explicit time points
    custom = arbitrary_pulse(
        samples=[0.0, 1.0, 1.0, 0.0],
        duration="200ns",
        amplitude="60mV",
        time_points=[0.0, 0.2, 0.8, 1.0]  # Normalized time points
    )

Measurements
------------

Basic Measurement
~~~~~~~~~~~~~~~~~

The ``measure()`` function performs a measurement operation:

.. code-block:: python

    measure(
        channel,
        result_var,
        duration,
        amplitude,
        integration="full",
        frequency=None,
        phase=None,
        **kwargs
    )

Example:

.. code-block:: python

    var_decl("result", "complex", unit="mV")

    measure(
        "readout",
        result_var="result",
        duration="1us",
        amplitude="30mV",
        integration="demod",
        frequency="6GHz"
    )

Integration modes:

* ``"full"`` - integrate entire acquisition window
* ``"demod"`` - demodulate and integrate

Measure and Discriminate
~~~~~~~~~~~~~~~~~~~~~~~~~

Combines measurement with state discrimination:

.. code-block:: python

    measure_and_discriminate(
        channel,
        raw_var,
        result_var,
        threshold,
        duration,
        amplitude,
        integration="full",
        **kwargs
    )

Example:

.. code-block:: python

    var_decl("raw", "complex", unit="mV")
    var_decl("state", "bool")

    measure_and_discriminate(
        "readout",
        raw_var="raw",
        result_var="state",
        threshold="0.5mV",
        duration="1us",
        amplitude="30mV"
    )

The ``state`` variable will be :obj:`True` if the measurement exceeds the threshold.

Variables
---------

Declaring Variables
~~~~~~~~~~~~~~~~~~~

Use ``var_decl()`` to declare a variable before using it:

.. code-block:: python

    var_decl(name, type, unit=None)

Types can be:

* ``"bool"`` - boolean value
* ``"int"`` - integer
* ``"float"`` - floating point number
* ``"complex"`` - complex number

Example:

.. code-block:: python

    var_decl("result", "complex", unit="mV")
    var_decl("state", "bool")
    var_decl("amplitude", "float", unit="mV")

Using Variables
~~~~~~~~~~~~~~~

Reference variables with ``var()``:

.. code-block:: python

    var(name)

Example:

.. code-block:: python

    # Use in conditional
    with if_("state"):
        play("qubit", pulse)

    # Use in pulse parameters
    play("qubit", square_pulse(duration="100ns", amplitude=var("amp")))

Control Flow
------------

Repetition (repeat)
~~~~~~~~~~~~~~~~~~~

Execute a block a fixed number of times:

.. code-block:: python

    with repeat(count):
        # operations

Example:

.. code-block:: python

    with build_sequence() as seq:
        with repeat(100):
            play("qubit", square_pulse(duration="50ns", amplitude="50mV"))
            wait("qubit", duration="50ns")

Iteration (``for_``)
~~~~~~~~~~~~~~~~~~~~

Loop over a sequence of values:

.. code-block:: python

    with for_(variable_name, values):
        # operations

Values can be:

* Python ``range()`` objects
* Lists of numbers
* ``LinSpace`` objects for linear sweeps

Example:

.. code-block:: python

    from eq1_pulse.models.basic_types import LinSpace

    with build_sequence() as seq:
        var_decl("freq", "float", unit="MHz")

        # Frequency sweep
        sweep = LinSpace(start=4000.0, stop=6000.0, num=100)
        with for_("freq", sweep):
            set_frequency("qubit", var("freq"))
            play("qubit", pulse)
            measure("readout", result_var="result", duration="1us", amplitude="30mV")

Conditionals (``if_``)
~~~~~~~~~~~~~~~~~~~~~~

Execute operations based on a condition:

.. code-block:: python

    with if_(condition):
        # operations if True

    with if_(condition):
        # operations if True
    with else_():
        # operations if False

Example:

.. code-block:: python

    var_decl("state", "bool")

    measure_and_discriminate(
        "readout",
        raw_var="raw",
        result_var="state",
        threshold="0.5mV",
        duration="1us",
        amplitude="30mV"
    )

    with if_("state"):
        # Qubit was in |1>, apply correction
        play("qubit", square_pulse(duration="100ns", amplitude="50mV"))
    with else_():
        # Qubit was in |0>, do nothing
        pass

Storing Results
---------------

The ``store()`` function saves measurement results:

.. code-block:: python

    store(stream_name, variable, mode="append")

Modes:

* ``"append"`` - add value to stream
* ``"average"`` - accumulate average
* ``"buffer"`` - store in buffer

Example:

.. code-block:: python

    var_decl("result", "complex", unit="mV")

    with for_("amp", range(0, 100, 5)):
        play("qubit", square_pulse(duration="100ns", amplitude=var("amp")))
        measure("readout", result_var="result", duration="1us", amplitude="30mV")
        store("rabi_data", "result", mode="average")

Advanced Patterns
-----------------

Nested Subsequences
~~~~~~~~~~~~~~~~~~~

Create reusable subsequences:

.. code-block:: python

    with build_sequence() as x_gate:
        play("qubit", square_pulse(duration="100ns", amplitude="50mV"))

    with build_sequence() as main_seq:
        # Use subsequence multiple times
        subsequence(x_gate)
        wait("qubit", duration="100ns")
        subsequence(x_gate)

Multi-Channel Synchronization
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Coordinate operations across channels:

.. code-block:: python

    with build_sequence() as seq:
        # Prepare both qubits
        play("qubit1", prep_pulse)
        play("qubit2", prep_pulse)

        # Ensure both are ready before entangling
        barrier("qubit1", "qubit2")

        # Two-qubit gate (simultaneous pulses)
        play("qubit1", entangling_pulse_q1)
        play("qubit2", entangling_pulse_q2)

        # Synchronize before measurement
        barrier("qubit1", "qubit2")

        # Simultaneous readout
        measure("qubit1", result_var="result1", duration="1us", amplitude="30mV")
        measure("qubit2", result_var="result2", duration="1us", amplitude="30mV")

Complete Example
----------------

Here's a complete Rabi oscillation experiment:

.. code-block:: python

    from eq1_pulse.builder import *
    from eq1_pulse.models.basic_types import LinSpace

    # Build amplitude Rabi sequence
    with build_sequence() as rabi_seq:
        # Declare variables
        var_decl("amp", "float", unit="mV")
        var_decl("raw", "complex", unit="mV")
        var_decl("state", "bool")

        # Sweep amplitude from 0 to 100 mV
        amplitude_sweep = LinSpace(start=0.0, stop=100.0, num=50)

        with for_("amp", amplitude_sweep):
            # Apply variable-amplitude pulse
            play("qubit", square_pulse(duration="100ns", amplitude=var("amp")))

            # Measure and discriminate
            measure_and_discriminate(
                "readout",
                raw_var="raw",
                result_var="state",
                threshold="0.5mV",
                duration="1us",
                amplitude="30mV"
            )

            # Store result
            store("rabi_amplitude", "state", mode="average")

            # Wait for qubit to relax
            wait("qubit", duration="10us")

    # Export to JSON
    print(rabi_seq.model_dump_json(indent=2))

This creates a complete experiment that sweeps the drive amplitude and measures the excited state population at each amplitude value.

JSON Output
~~~~~~~~~~~

.. code-block:: json

    [
      {
        "op_type": "var_decl",
        "name": "amp",
        "dtype": "float",
        "unit": "mV"
      },
      {
        "op_type": "var_decl",
        "name": "raw",
        "dtype": "complex",
        "unit": "mV"
      },
      {
        "op_type": "var_decl",
        "name": "state",
        "dtype": "bool"
      },
      {
        "op_type": "for",
        "var": "amp",
        "items": {
          "start": 0.0,
          "stop": 100.0,
          "num": 50
        },
        "body": [
          {
            "op_type": "play",
            "channel": "qubit",
            "pulse": {
              "pulse_type": "square",
              "duration": {
                "ns": 100
              },
              "amplitude": "amp"
            }
          },
          {
            "op_type": "play",
            "channel": "readout",
            "pulse": {
              "pulse_type": "square",
              "duration": {
                "us": 1
              },
              "amplitude": {
                "mV": 30
              }
            }
          },
          {
            "op_type": "record",
            "channel": "readout",
            "var": "raw",
            "duration": {
              "us": 1
            },
            "integration": {
              "integration_type": "full"
            }
          },
          {
            "op_type": "discriminate",
            "target": "state",
            "source": "raw",
            "threshold": {
              "mV": 0.5
            }
          },
          {
            "op_type": "store",
            "key": "rabi_amplitude",
            "source": "state",
            "mode": "average"
          },
          {
            "op_type": "wait",
            "channels": [
              "qubit"
            ],
            "duration": {
              "us": 10
            }
          }
        ]
      }
    ]

The JSON structure shows:

1. **Variable declarations** (lines 2-14): Three variables for amplitude sweep, raw measurement, and discriminated state
2. **For loop** (lines 15-93): Sweeps amplitude from 0 to 100 mV in 50 steps
3. **Loop body** contains:

   - **Play operation** (lines 19-29): Variable-amplitude square pulse on qubit channel
   - **Measurement** (lines 30-50): Readout pulse and recording with integration
   - **Discrimination** (lines 51-57): Threshold comparison to classify qubit state
   - **Data storage** (lines 58-63): Store averaged results
   - **Wait operation** (lines 64-70): Allow qubit to relax between measurements

This JSON can be exported to control hardware or used for simulation and analysis.

Pulse Sequence Visualization
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The diagram below shows how the JSON structure translates into a concrete pulse sequence timeline:

.. only:: html

   .. image:: /_static/pulse_sequence_diagram.svg
      :width: 100%
      :alt: Pulse sequence timing diagram
      :align: center

.. only:: latex

   .. image:: /_static/pulse_sequence_diagram.pdf
      :width: 100%
      :alt: Pulse sequence timing diagram
      :align: center

The visualization shows three iterations of the 50-iteration loop, displaying the temporal structure:

- **Drive pulses** (purple): Applied on the qubit channel with increasing amplitude (25 mV, 50 mV, 75 mV shown). Pulse duration is 100 ns.
- **Readout pulses** (orange): Applied on the readout channel immediately after each drive pulse. Fixed at 30 mV amplitude and 1 μs duration.
- **Wait periods** (gray dashed): 10 μs relaxation time on both channels to allow the qubit to return to ground state before the next iteration.

Each iteration follows the same temporal pattern: drive → readout → wait. The amplitude sweep from 0 to 100 mV across all 50 iterations enables calibration of the π pulse amplitude for this qubit.

Creating Reusable Building Blocks
----------------------------------

For complex pulse programs, you'll often want to create reusable, modular building blocks that encapsulate common operations. The builder provides two decorators for this purpose: ``@nested_sequence`` and ``@nested_schedule``.

The ``@nested_sequence`` Decorator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use ``@nested_sequence`` to create reusable operation blocks in sequence contexts. Functions decorated with ``@nested_sequence`` automatically create a :func:`sub_sequence` when called.

**Basic Usage:**

.. code-block:: python

    from eq1_pulse.builder import *

    @nested_sequence
    def hadamard_gate(qubit: str):
        """Apply a Hadamard gate."""
        play(qubit, square_pulse(duration="20ns", amplitude="100mV"))
        shift_phase(qubit, "90deg")
        play(qubit, square_pulse(duration="20ns", amplitude="100mV"))
        shift_phase(qubit, "-90deg")

    @nested_sequence
    def x_gate(qubit: str):
        """Apply an X gate."""
        play(qubit, square_pulse(duration="20ns", amplitude="150mV"))

    @nested_sequence
    def readout_sequence(drive_ch: str, readout_ch: str, result_var: str):
        """Perform readout measurement."""
        play(drive_ch, square_pulse(duration="1us", amplitude="50mV"))
        record(readout_ch, var=result_var, duration="1us")

    # Use the building blocks in a sequence
    with build_sequence() as seq:
        var_decl("readout", "complex", unit="mV")

        hadamard_gate("qubit0")
        x_gate("qubit0")
        hadamard_gate("qubit0")

        readout_sequence("drive0", "readout0", "readout")

**Key Points:**

- The decorated function is called normally with its parameters
- It automatically creates a ``sub_sequence`` in the current context
- The function returns :obj:`None` (operations are added to the context)
- Can only be used in sequence contexts (raises error in schedule contexts)
- Decorated functions can call other ``@nested_sequence`` decorated functions

**Visual Explanation:**

The diagram below illustrates how ``@nested_sequence`` eliminates manual context management:

.. only:: html

   .. image:: /_static/nested_sequence_diagram.svg
      :width: 100%
      :alt: @nested_sequence decorator usage
      :align: center

.. only:: latex

   .. image:: /_static/nested_sequence_diagram.pdf
      :width: 100%
      :alt: @nested_sequence decorator usage
      :align: center

Without the decorator, you must manually create ``sub_sequence()`` contexts. With ``@nested_sequence``, simply calling the function automatically creates the sub-sequence, making code cleaner and more reusable.

**Composing Building Blocks:**

You can compose building blocks together:

.. code-block:: python

    @nested_sequence
    def bell_state_prep(qubit1: str, qubit2: str):
        """Prepare a Bell state between two qubits."""
        hadamard_gate(qubit1)  # Call another decorated function
        # Simplified CNOT implementation
        play(qubit1, square_pulse(duration="30ns", amplitude="120mV"))
        play(qubit2, square_pulse(duration="30ns", amplitude="120mV"))

    with build_sequence() as seq:
        bell_state_prep("qubit0", "qubit1")
        # Multiple readouts
        var_decl("result0", "complex", unit="mV")
        var_decl("result1", "complex", unit="mV")
        readout_sequence("drive0", "readout0", "result0")
        readout_sequence("drive1", "readout1", "result1")

The ``@nested_schedule`` Decorator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use ``@nested_schedule`` to create reusable schedule blocks that need explicit timing control. Functions decorated with ``@nested_schedule`` return a :class:`ScheduleBlock` object that must be passed to :func:`add_block` along with schedule timing parameters.

**Basic Usage:**

.. code-block:: python

    from eq1_pulse.builder import *

    @nested_schedule
    def initialize_qubit(qubit: str):
        """Initialize a qubit to ground state."""
        play(qubit, square_pulse(duration="100ns", amplitude="200mV"))
        wait(qubit, duration="50ns")

    @nested_schedule
    def rabi_drive(qubit: str, amplitude: str):
        """Apply a Rabi drive pulse."""
        play(qubit, square_pulse(duration="50ns", amplitude=amplitude))

    @nested_schedule
    def measure_qubit(drive_ch: str, readout_ch: str, result_var: str):
        """Measure a qubit."""
        play(drive_ch, square_pulse(duration="1us", amplitude="50mV"))
        record(readout_ch, var=result_var, duration="1us")

    # Use the building blocks in a schedule
    with build_schedule() as sched:
        # Call the function to create a block, then add it with timing
        init_token = add_block(initialize_qubit("qubit0"), name="init")

        # Position subsequent blocks relative to previous operations
        rabi_token = add_block(
            rabi_drive("qubit0", "150mV"),
            name="rabi",
            ref_op=init_token,
            ref_pt="end",
            rel_time="10ns"
        )

        add_block(
            measure_qubit("drive0", "readout0", "result"),
            name="measure",
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

.. only:: html

   .. image:: /_static/nested_schedule_diagram.svg
      :width: 100%
      :alt: @nested_schedule decorator with add_block usage
      :align: center

.. only:: latex

   .. image:: /_static/nested_schedule_diagram.pdf
      :width: 100%
      :alt: @nested_schedule decorator with add_block usage
      :align: center

The diagram illustrates:

1. **Top section**: Decorator definitions for reusable schedule blocks
2. **Middle section**: Usage with ``add_block()`` providing timing parameters
3. **Bottom section**: Resulting timeline showing precise positioning with reference points and relative timing

**Error Handling:**

The builder tracks all :class:`ScheduleBlock` objects and ensures they are consumed:

.. code-block:: python

    with build_schedule() as sched:
        # This creates a block but doesn't add it - ERROR!
        block = initialize_qubit("qubit0")
        # RuntimeError when context closes: unconsumed ScheduleBlock

    # Correct usage:
    with build_schedule() as sched:
        add_block(initialize_qubit("qubit0"), name="init")  # ✓

Parallel Operations with Schedules
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Schedule building blocks shine when you need parallel execution:

.. code-block:: python

    @nested_schedule
    def two_qubit_gate(control: str, target: str, angle: str):
        """Two-qubit controlled rotation gate."""
        play(control, square_pulse(duration="40ns", amplitude="100mV"))
        play(target, square_pulse(duration="40ns", amplitude="100mV"))
        shift_phase(target, angle)

    with build_schedule() as sched:
        # Initialize both qubits in parallel (same start time)
        init0 = add_block(initialize_qubit("qubit0"), name="init0")
        add_block(
            initialize_qubit("qubit1"),
            name="init1",
            ref_op=init0,
            ref_pt="start"  # Start at same time as init0
        )

        # Apply gates with precise timing
        gate0 = add_block(
            rabi_drive("qubit0", "140mV"),
            name="gate0",
            ref_op=init0,
            ref_pt="end",
            rel_time="20ns"
        )

        gate1 = add_block(
            two_qubit_gate("qubit0", "qubit1", "45deg"),
            name="cnot",
            ref_op=gate0,
            ref_pt="start"  # Start at same time as gate0
        )

        # Measure both in parallel
        meas0 = add_block(
            measure_qubit("drive0", "readout0", "r0"),
            ref_op=gate1,
            ref_pt="end",
            rel_time="100ns"
        )

        add_block(
            measure_qubit("drive1", "readout1", "r1"),
            ref_op=meas0,
            ref_pt="start"  # Start at same time as meas0
        )

This creates a schedule where:

- Both qubits are initialized simultaneously
- The two-qubit gate starts when the single-qubit gate starts
- Both measurements execute in parallel

When to Use Which Decorator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Use** ``@nested_sequence`` **when:**

- Building sequences with implicit timing (sequential operations on same channel)
- Creating gate libraries or common operation patterns
- You don't need explicit timing control
- Working with control flow (repetitions, iterations, conditionals)

**Use** ``@nested_schedule`` **when:**

- You need explicit timing relationships between operations
- Implementing parallel operations on multiple channels
- Building calibration routines with precise timing
- Creating measurement sequences with specific positioning

**Side-by-Side Comparison:**

.. only:: html

   .. image:: /_static/decorator_comparison_diagram.svg
      :width: 100%
      :alt: Comparison of @nested_sequence vs @nested_schedule
      :align: center

.. only:: latex

   .. image:: /_static/decorator_comparison_diagram.pdf
      :width: 100%
      :alt: Comparison of @nested_sequence vs @nested_schedule
      :align: center

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
   - ``@nested_schedule`` decorated functions can **only** be called within ``build_schedule()`` contexts
   - You cannot nest a schedule inside a sequence, or vice versa
   - If you need both sequential operations and explicit timing, choose one approach for your entire program

Best Practices
~~~~~~~~~~~~~~

1. **Descriptive names**: Use clear function names that describe the operation:

   .. code-block:: python

       @nested_sequence
       def pi_pulse(qubit: str):  # Good
           """Apply a π pulse."""
           ...

       @nested_sequence
       def do_stuff(ch: str):  # Avoid
           ...

2. **Add docstrings**: Document what your building blocks do:

   .. code-block:: python

       @nested_schedule
       def ramsey_sequence(qubit: str, delay: str):
           """Ramsey sequence with variable delay.

           Applies π/2 - delay - π/2 sequence for T2* measurement.

           :param qubit: Target qubit channel
           :param delay: Free evolution time between π/2 pulses
           """
           ...

3. **Use type hints**: Help users understand parameter types:

   .. code-block:: python

       @nested_sequence
       def readout_sequence(
           drive_ch: str,
           readout_ch: str,
           result_var: str
       ) -> None:
           ...

4. **Parameterize building blocks**: Make them flexible and reusable:

   .. code-block:: python

       @nested_schedule
       def variable_amplitude_pulse(
           channel: str,
           duration: str,
           amplitude: str,
           shape: str = "square"
       ):
           """Pulse with configurable parameters."""
           if shape == "square":
               play(channel, square_pulse(duration=duration, amplitude=amplitude))
           elif shape == "sine":
               play(channel, sine_pulse(
                   duration=duration,
                   amplitude=amplitude,
                   frequency="5GHz"
               ))

5. **Always use** :func:`add_block` **with** ``@nested_schedule``:

   .. code-block:: python

       # Wrong - creates unconsumed block
       with build_schedule():
           block = measure_qubit("drive", "readout", "result")  # Error!

       # Correct
       with build_schedule():
           add_block(
               measure_qubit("drive", "readout", "result"),
               name="measure"
           )

6. **Don't mix sequence and schedule decorators**:

   .. code-block:: python

       @nested_sequence
       def gate_sequence(qubit: str):
           play(qubit, square_pulse(duration="20ns", amplitude="100mV"))

       @nested_schedule
       def calibration_block(qubit: str):
           play(qubit, square_pulse(duration="100ns", amplitude="200mV"))

       # WRONG - sequence decorator in schedule context
       with build_schedule():
           gate_sequence("q0")  # RuntimeError!

       # WRONG - schedule decorator in sequence context
       with build_sequence():
           add_block(calibration_block("q0"), name="cal")  # RuntimeError!

       # CORRECT - match decorator to context
       with build_sequence():
           gate_sequence("q0")  # ✓

       with build_schedule():
           add_block(calibration_block("q0"), name="cal")  # ✓

Complete Example
~~~~~~~~~~~~~~~~

Here's a complete example combining both decorators for a multi-qubit experiment:

.. code-block:: python

    from eq1_pulse.builder import *

    # ========== Gate library (sequences) ==========

    @nested_sequence
    def x90_gate(qubit: str):
        """π/2 rotation around X axis."""
        play(qubit, square_pulse(duration="10ns", amplitude="100mV"))

    @nested_sequence
    def x_gate(qubit: str):
        """π rotation around X axis."""
        play(qubit, square_pulse(duration="20ns", amplitude="100mV"))

    @nested_sequence
    def y_gate(qubit: str):
        """π rotation around Y axis."""
        shift_phase(qubit, "90deg")
        play(qubit, square_pulse(duration="20ns", amplitude="100mV"))
        shift_phase(qubit, "-90deg")

    # ========== Calibration blocks (schedules) ==========

    @nested_schedule
    def qubit_reset(qubit: str):
        """Active reset protocol."""
        play(qubit, square_pulse(duration="100ns", amplitude="200mV"))
        wait(qubit, duration="1us")

    @nested_schedule
    def dispersive_readout(drive: str, readout: str, result: str):
        """Standard dispersive readout."""
        play(drive, square_pulse(duration="2us", amplitude="40mV"))
        record(readout, var=result, duration="2us", integration="full")

    # ========== Use in sequence context ==========

    with build_sequence() as seq:
        var_decl("state", "complex", unit="mV")

        # Build up gates using sequence blocks
        x90_gate("q0")
        x_gate("q0")
        y_gate("q0")
        x90_gate("q0")

        # Manual readout (sequence context)
        play("drive0", square_pulse(duration="2us", amplitude="40mV"))
        record("readout0", var="state", duration="2us")

    # ========== Use in schedule context ==========

    with build_schedule() as sched:
        var_decl("r0", "complex", unit="mV")
        var_decl("r1", "complex", unit="mV")

        # Reset both qubits in parallel
        reset0 = add_block(qubit_reset("q0"), name="reset0")
        add_block(qubit_reset("q1"), name="reset1", ref_op=reset0, ref_pt="start")

        # Entangling gate sequence
        gate = add_block(
            dispersive_readout("drive0", "readout0", "r0"),
            name="readout0",
            ref_op=reset0,
            ref_pt="end",
            rel_time="50ns"
        )

        # Simultaneous readout
        add_block(
            dispersive_readout("drive1", "readout1", "r1"),
            name="readout1",
            ref_op=gate,
            ref_pt="start"
        )

This example demonstrates:

- Simple gate operations as ``@nested_sequence`` blocks
- Complex calibration routines as ``@nested_schedule`` blocks
- Using sequence blocks in sequences (simple sequential composition)
- Using schedule blocks in schedules (with explicit timing and parallelism)
