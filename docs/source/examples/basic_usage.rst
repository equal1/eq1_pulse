Basic Usage Examples
====================

This page demonstrates basic usage of the eq1_pulse builder interface with simple, focused examples.

Creating a Simple Sequence
---------------------------

The most basic pulse sequence applies operations sequentially:

.. code-block:: python

    from eq1_pulse.builder import *

    # Create a sequence context
    with build_sequence() as seq:
        # Play a square pulse on the drive channel
        play("drive", square_pulse(duration="10us", amplitude="100mV"))

        # Play a sine pulse on readout
        play("readout", sine_pulse(
            duration="5us",
            amplitude="50mV",
            frequency="5GHz"
        ))

    # The sequence is now built and available in 'seq'
    print(seq.model_dump_json(indent=2))

Pulse Sequence Diagram
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    Channel: drive
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
              ┌──────────────────┐
              │                  │
    ──────────┤  Square 100mV    ├──────────────
              │                  │
              │      10 μs       │
              └──────────────────┘

    Channel: readout
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
              ┌──────────┐
              │  ∿∿∿∿∿∿  │
    ──────────┤ Sine 50mV├────────────────────
              │  5 GHz   │
              │   5 μs   │
              └──────────┘

JSON Output
~~~~~~~~~~~

.. code-block:: json

    {
      "type": "Sequence",
      "items": [
        {
          "op_type": "play",
          "channel": "drive",
          "pulse": {
            "type": "SquarePulse",
            "duration": {
              "us": 10.0
            },
            "amplitude": {
              "V": [
                0.1,
                0.0
              ]
            },
            "phase": null
          }
        },
        {
          "op_type": "play",
          "channel": "readout",
          "pulse": {
            "type": "SinePulse",
            "duration": {
              "us": 5.0
            },
            "amplitude": {
              "V": [
                0.05,
                0.0
              ]
            },
            "frequency": {
              "GHz": 5.0
            },
            "phase": null
          }
        }
      ]
    }

Synchronizing Channels with Barriers
-------------------------------------

Use ``barrier()`` to synchronize multiple channels:

.. code-block:: python

    with build_sequence() as seq:
        # First set of pulses (can execute in parallel)
        play("drive", square_pulse(duration="10us", amplitude="100mV"))
        play("readout", square_pulse(duration="5us", amplitude="50mV"))

        # Wait for both channels to complete
        barrier("drive", "readout")

        # After barrier, these start at the same time
        play("drive", square_pulse(duration="20us", amplitude="80mV"))
        play("readout", square_pulse(duration="20us", amplitude="40mV"))

Pulse Sequence Diagram
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    Channel: drive
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
              ┌──────────┐      ▮
              │          │      ▮ barrier
    ──────────┤  100mV   ├──────▮────┌────────────────────┐
              │   10μs   │      ▮    │       80mV         │
              └──────────┘      ▮    │        20μs        │
                                     └────────────────────┘

    Channel: readout
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
              ┌─────┐            ▮
              │ 50mV│            ▮ barrier
    ──────────┤ 5μs ├────────────▮────┌────────────────────┐
              │     │            ▮    │       40mV         │
              └─────┘            ▮    │        20μs        │
                                      └────────────────────┘

JSON Output
~~~~~~~~~~~

.. code-block:: json

    {
      "type": "Sequence",
      "items": [
        {
          "op_type": "play",
          "channel": "drive",
          "pulse": {
            "type": "SquarePulse",
            "duration": {
              "us": 10.0
            },
            "amplitude": {
              "V": [
                0.1,
                0.0
              ]
            },
            "phase": null
          }
        },
        {
          "op_type": "play",
          "channel": "readout",
          "pulse": {
            "type": "SquarePulse",
            "duration": {
              "us": 5.0
            },
            "amplitude": {
              "V": [
                0.05,
                0.0
              ]
            },
            "phase": null
          }
        },
        {
          "op_type": "barrier",
          "channels": [
            "drive",
            "readout"
          ]
        },
        {
          "op_type": "play",
          "channel": "drive",
          "pulse": {
            "type": "SquarePulse",
            "duration": {
              "us": 20.0
            },
            "amplitude": {
              "V": [
                0.08,
                0.0
              ]
            },
            "phase": null
          }
        },
        {
          "op_type": "play",
          "channel": "readout",
          "pulse": {
            "type": "SquarePulse",
            "duration": {
              "us": 20.0
            },
            "amplitude": {
              "V": [
                0.04,
                0.0
              ]
            },
            "phase": null
          }
        }
      ]
    }

Using Repetition
----------------

Repeat a block of operations a fixed number of times:

.. code-block:: python

    with build_sequence() as seq:
        # Repeat 10 times
        with repeat(10):
            play("qubit", square_pulse(duration="50ns", amplitude="100mV"))
            wait("qubit", duration="50ns")

This creates 10 identical pulse-wait cycles.

JSON Output
~~~~~~~~~~~

.. code-block:: json

    {
      "type": "Sequence",
      "items": [
        {
          "op_type": "repeat",
          "count": 10,
          "body": {
            "type": "Sequence",
            "items": [
              {
                "op_type": "play",
                "channel": "qubit",
                "pulse": {
                  "type": "SquarePulse",
                  "duration": {
                    "ns": 50.0
                  },
                  "amplitude": {
                    "V": [
                      0.1,
                      0.0
                    ]
                  },
                  "phase": null
                }
              },
              {
                "op_type": "wait",
                "channel": "qubit",
                "duration": {
                  "ns": 50.0
                }
              }
            ]
          }
        }
      ]
    }

Iterating with ``for_`` Loops
------------------------------

Loop over a range of values:

.. code-block:: python

    with build_sequence() as seq:
        # Declare loop variable
        var_decl("freq", "float", unit="MHz")

        # Iterate from 4000 to 6000 MHz in steps of 100
        with for_("freq", range(4000, 6000, 100)):
            # Set frequency to loop variable
            set_frequency("qubit", var("freq"))

            # Play pulse
            play("qubit", square_pulse(duration="100ns", amplitude="50mV"))

            # Wait between iterations
            wait("qubit", duration="100ns")

Linear Sweep with LinSpace
~~~~~~~~~~~~~~~~~~~~~~~~~~~

For precise linear sweeps, use ``LinSpace``:

.. code-block:: python

    from eq1_pulse.models.basic_types import LinSpace

    with build_sequence() as seq:
        var_decl("amplitude", "float", unit="mV")

        # 50 evenly-spaced points from 0 to 100 mV
        amp_sweep = LinSpace(start=0.0, stop=100.0, num=50)

        with for_("amplitude", amp_sweep):
            play("qubit", square_pulse(
                duration="100ns",
                amplitude=var("amplitude")
            ))
            wait("qubit", duration="10us")

Basic Measurement
-----------------

Perform a measurement and store the result:

.. code-block:: python

    with build_sequence() as seq:
        # Declare variable to store result
        var_decl("result", "complex", unit="mV")

        # Apply excitation pulse
        play("qubit", square_pulse(duration="100ns", amplitude="50mV"))

        # Measure the qubit
        measure(
            "qubit",
            result_var="result",
            duration="1us",
            amplitude="30mV",
            integration="demod",
            frequency="6GHz"
        )

The measurement result is stored in the ``result`` variable.

JSON Output
~~~~~~~~~~~

.. code-block:: json

    {
      "type": "Sequence",
      "items": [
        {
          "op_type": "var_decl",
          "variable": "result",
          "var_type": "complex",
          "unit": "mV"
        },
        {
          "op_type": "play",
          "channel": "qubit",
          "pulse": {
            "type": "SquarePulse",
            "duration": {
              "ns": 100.0
            },
            "amplitude": {
              "V": [
                0.05,
                0.0
              ]
            },
            "phase": null
          }
        },
        {
          "op_type": "play",
          "channel": "qubit",
          "pulse": {
            "type": "SquarePulse",
            "duration": {
              "us": 1.0
            },
            "amplitude": {
              "V": [
                0.03,
                0.0
              ]
            },
            "phase": null
          }
        },
        {
          "op_type": "record",
          "channel": "qubit",
          "duration": {
            "us": 1.0
          },
          "result_var": "result",
          "integration": {
            "type": "demod",
            "frequency": {
              "GHz": 6.0
            }
          }
        }
      ]
    }

Measurement with Discrimination
--------------------------------

Measure and classify the result into a binary state:

.. code-block:: python

    with build_sequence() as seq:
        # Declare variables
        var_decl("raw_result", "complex", unit="mV")
        var_decl("qubit_state", "bool")

        # Apply π pulse
        play("qubit", square_pulse(duration="50ns", amplitude="100mV"))

        # Measure and discriminate
        measure_and_discriminate(
            "qubit",
            raw_var="raw_result",
            result_var="qubit_state",
            threshold="0.5mV",
            duration="1us",
            amplitude="30mV"
        )

        # qubit_state is True if raw_result > threshold

Conditional Operations
----------------------

Execute operations based on a measurement outcome:

.. code-block:: python

    with build_sequence() as seq:
        var_decl("result", "complex", unit="mV")

        # Measure
        measure("qubit", result_var="result", duration="1us", amplitude="50mV")

        # Apply correction if result indicates excited state
        with if_("result"):
            play("qubit", square_pulse(duration="50ns", amplitude="100mV"))

With else clause:

.. code-block:: python

    with build_sequence() as seq:
        var_decl("state", "bool")

        measure_and_discriminate(
            "qubit",
            raw_var="raw",
            result_var="state",
            threshold="0.5mV",
            duration="1us",
            amplitude="30mV"
        )

        with if_("state"):
            # State is |1⟩
            play("qubit", square_pulse(duration="50ns", amplitude="100mV"))
        with else_():
            # State is |0⟩
            play("qubit", square_pulse(duration="25ns", amplitude="50mV"))

Storing Results
---------------

Store measurement results to a named stream:

.. code-block:: python

    with build_sequence() as seq:
        var_decl("result", "complex", unit="mV")
        var_decl("i", "float", unit="mV")

        # Sweep and store
        sweep = LinSpace(start=0.0, stop=100.0, num=50)

        with for_("i", sweep):
            play("qubit", square_pulse(duration="100ns", amplitude=var("i")))
            measure("qubit", result_var="result", duration="1us", amplitude="30mV")

            # Store to stream (averaged across repetitions)
            store("sweep_data", "result", mode="average")

Storage modes:

* ``"append"`` - add each value to the stream
* ``"average"`` - accumulate running average
* ``"buffer"`` - store in a buffer for later processing

Using Schedules
---------------

For explicit timing control, use schedules instead of sequences:

.. code-block:: python

    with build_schedule() as sched:
        # First operation (starts at default time)
        op1 = play("qubit", square_pulse(duration="100ns", amplitude="50mV"))

        # Second operation starts 500ns after first one ends
        op2 = play(
            "qubit",
            square_pulse(duration="100ns", amplitude="30mV"),
            ref_op=op1,
            ref_pt="end",
            rel_time="500ns"
        )

        # Readout starts when second pulse starts
        play(
            "readout",
            square_pulse(duration="1us", amplitude="20mV"),
            ref_op=op2,
            ref_pt="start",
            ref_pt_new="start",
            rel_time="0ns"
        )

Schedule Diagram
~~~~~~~~~~~~~~~~

.. code-block:: text

    Channel: qubit
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
              ┌────┐                    ┌────┐
              │50mV│                    │30mV│
    ──────────┤100n├────────────────────┤100n├────────────
              │ s  │  500ns delay       │ s  │
              └────┘                    └────┘
               op1 ──────500ns──────────▶ op2

    Channel: readout
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                                        ┌──────────────┐
                                        │    20mV      │
    ────────────────────────────────────┤     1μs      ├────
                                        │              │
                                        └──────────────┘
                                         (starts with op2)

Working with Different Pulse Shapes
------------------------------------

Square Pulse
~~~~~~~~~~~~

Constant amplitude:

.. code-block:: python

    pulse = square_pulse(duration="100ns", amplitude="50mV", phase="0deg")

Gaussian Pulse
~~~~~~~~~~~~~~

Gaussian envelope reduces spectral leakage:

.. code-block:: python

    pulse = gaussian_pulse(
        duration="200ns",
        amplitude="50mV",
        sigma="40ns",  # Width parameter
        frequency="5.2GHz",
        phase="0deg"
    )

DRAG Pulse
~~~~~~~~~~

Derivative Removal by Adiabatic Gate (reduces leakage):

.. code-block:: python

    pulse = drag_pulse(
        duration="200ns",
        amplitude="50mV",
        sigma="40ns",
        beta=0.5,  # DRAG parameter
        frequency="5.2GHz"
    )

Setting Phase and Frequency
----------------------------

Absolute Settings
~~~~~~~~~~~~~~~~~

.. code-block:: python

    with build_sequence() as seq:
        # Set absolute frequency
        set_frequency("qubit", frequency="5.2GHz")

        # Set absolute phase
        set_phase("qubit", phase="90deg")

        play("qubit", pulse)

Relative Shifts
~~~~~~~~~~~~~~~

.. code-block:: python

    with build_sequence() as seq:
        # Shift frequency by offset
        shift_frequency("qubit", "100MHz")

        # Shift phase by offset
        shift_phase("qubit", "45deg")

        play("qubit", pulse)

Complete Example: Simple Experiment
------------------------------------

Here's a complete example combining multiple concepts:

.. code-block:: python

    from eq1_pulse.builder import *
    from eq1_pulse.models.basic_types import LinSpace

    # Build a frequency sweep experiment
    with build_sequence() as seq:
        # Declare variables
        var_decl("freq", "float", unit="GHz")
        var_decl("result", "complex", unit="mV")
        var_decl("state", "bool")

        # Frequency sweep from 5.0 to 5.5 GHz
        freq_sweep = LinSpace(start=5.0, stop=5.5, num=50)

        # Repeat experiment 100 times for averaging
        with repeat(100):
            with for_("freq", freq_sweep):
                # Set frequency
                set_frequency("qubit", var("freq"))

                # Apply excitation pulse
                play("qubit", square_pulse(duration="100ns", amplitude="50mV"))

                # Measure and discriminate
                measure_and_discriminate(
                    "qubit",
                    raw_var="result",
                    result_var="state",
                    threshold="0.5mV",
                    duration="1us",
                    amplitude="30mV"
                )

                # Store result (averaged)
                store("spectroscopy", "state", mode="average")

                # Wait for qubit to relax
                wait("qubit", duration="10us")

    # Export the sequence
    json_output = seq.model_dump_json(indent=2)
    print(json_output)

This creates a complete spectroscopy experiment that:

1. Sweeps frequency from 5.0 to 5.5 GHz
2. Applies an excitation pulse at each frequency
3. Measures and discriminates the result
4. Stores averaged results
5. Repeats 100 times for statistics

Next Steps
----------

* Try modifying these examples for your hardware
* Explore :doc:`spin_qubit_rabi` for more complex experiments
* Read the :doc:`/user_guide/builder_guide` for complete API documentation
