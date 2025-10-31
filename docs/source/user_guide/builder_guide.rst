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

    square_pulse(duration, amplitude, phase=None)

Example:

.. code-block:: python

    pulse = square_pulse(duration="100ns", amplitude="50mV")
    pulse = square_pulse(duration="100ns", amplitude="50mV", phase="90deg")

Sine Pulse
~~~~~~~~~~

A sinusoidal waveform:

.. code-block:: python

    sine_pulse(duration, amplitude, frequency, phase=None)

Example:

.. code-block:: python

    pulse = sine_pulse(
        duration="1us",
        amplitude="30mV",
        frequency="5GHz",
        phase="0deg"
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
* ``"window"`` - integrate with custom window function

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
        # Qubit was in |1⟩, apply correction
        play("qubit", square_pulse(duration="100ns", amplitude="50mV"))
    with else_():
        # Qubit was in |0⟩, do nothing
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
