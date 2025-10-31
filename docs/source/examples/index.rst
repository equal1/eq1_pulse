Examples and Tutorials
======================

This section provides practical examples of using the eq1_pulse library for common quantum computing experiments, with a focus on spin qubit applications.

.. toctree::
   :maxdepth: 2
   :caption: Examples:

   basic_usage
   spin_qubit_rabi
   spin_qubit_t2star

Overview
--------

The examples are organized by complexity and application:

Basic Usage
~~~~~~~~~~~

Simple examples demonstrating core concepts:

* Creating sequences and schedules
* Playing pulses
* Using control flow (loops, conditionals)
* Performing measurements

See :doc:`basic_usage` for introductory examples.

Spin Qubit Experiments
~~~~~~~~~~~~~~~~~~~~~~~

Complete experimental protocols for spin qubit characterization:

**Rabi Oscillations** (:doc:`spin_qubit_rabi`)
    Calibrate pulse parameters and measure qubit properties by sweeping amplitude, duration, or frequency.

**T2* Dephasing** (:doc:`spin_qubit_t2star`)
    Measure coherence times using Ramsey and echo sequences to characterize noise and optimize qubit performance.

Running the Examples
--------------------

All example scripts are located in the ``examples/`` directory of the repository:

.. code-block:: bash

    cd eq1_pulse
    python examples/builder_example.py
    python examples/spin_qubit_rabi.py
    python examples/spin_qubit_t2star.py

Each script will:

1. Build pulse sequences using the builder interface
2. Print progress and descriptions
3. Output JSON representations of the sequences
4. Display expected experimental results

Example Output
--------------

When you run an example, you'll see output like:

.. code-block:: text

    ======================================================================
    Example 1: Amplitude Rabi Oscillation
    ======================================================================
    Sweep drive amplitude to calibrate π pulse

    Created sequence with 1 operations
    {
      "type": "Sequence",
      "items": [
        {
          "type": "For",
          "variable": "amp",
          ...
        }
      ]
    }

    Expected result: Sinusoidal oscillation in excited state probability
    π pulse amplitude: First minimum in oscillation

Understanding the JSON Output
------------------------------

The JSON output represents the complete pulse sequence in a portable format. Key sections:

**Sequence Structure**:

.. code-block:: json

    {
      "type": "Sequence",
      "items": [...]
    }

A sequence contains an ordered list of operations.

**Control Flow**:

.. code-block:: json

    {
      "type": "For",
      "variable": "amp",
      "values": {"type": "LinSpace", "start": 0, "stop": 100, "num": 50},
      "body": {...}
    }

Loops sweep over parameter ranges.

**Operations**:

.. code-block:: json

    {
      "type": "Play",
      "channel": "qubit",
      "pulse": {
        "type": "SquarePulse",
        "duration": {"ns": 100},
        "amplitude": {"V": [0.05, 0]}
      }
    }

Individual pulse operations with all parameters specified.

Modifying Examples
------------------

The examples are designed to be easily modified for your specific hardware:

Adjusting Parameters
~~~~~~~~~~~~~~~~~~~~

Edit pulse parameters to match your qubit:

.. code-block:: python

    # Change pulse duration
    play("qubit", square_pulse(
        duration="50ns",  # Was 100ns
        amplitude="80mV"
    ))

    # Adjust sweep range
    amplitude_sweep = LinSpace(
        start=0.0,
        stop=200.0,  # Was 100.0
        num=100      # More points
    )

Changing Channel Names
~~~~~~~~~~~~~~~~~~~~~~

Use channel names that match your hardware:

.. code-block:: python

    # Instead of generic "qubit"
    play("Q1_XY", pulse)
    measure("Q1_RO", ...)

Adding Measurements
~~~~~~~~~~~~~~~~~~~

Extend sequences with additional measurements:

.. code-block:: python

    # Add intermediate measurement
    measure("qubit", result_var="mid_result", ...)

    # Conditional on result
    with if_("mid_result"):
        play("qubit", correction_pulse)

Next Steps
----------

After exploring the examples:

1. **Read the builder guide**: :doc:`/user_guide/builder_guide` for detailed API documentation
2. **Check the API reference**: :doc:`/autoapi/eq1_pulse/models/index` for complete model specifications
3. **Adapt for your hardware**: Modify examples to match your quantum processor
4. **Create custom sequences**: Build your own experiments using the patterns shown

Contributing Examples
---------------------

We welcome contributions of additional examples! If you've developed interesting pulse sequences:

1. Fork the repository
2. Add your example to ``examples/``
3. Create documentation in ``docs/source/examples/``
4. Submit a pull request

Good examples to contribute:

* Different qubit modalities (superconducting, trapped ions, etc.)
* Advanced calibration protocols
* Multi-qubit experiments
* Custom pulse shaping techniques
* Error mitigation sequences
