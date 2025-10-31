Spin Qubit Rabi Oscillations
=============================

Rabi oscillations are a fundamental characterization technique for qubits. By sweeping a pulse parameter (amplitude, duration, or frequency) while measuring the excited state population, we can:

* Calibrate π and π/2 pulses
* Measure the Rabi frequency
* Find the qubit resonance frequency
* Characterize qubit-photon coupling

This page demonstrates three types of Rabi experiments for spin qubits.

Amplitude Rabi
--------------

In an amplitude Rabi experiment, we sweep the drive amplitude while keeping duration fixed. This is the most common method for calibrating pulse parameters.

Pulse Sequence Diagram
~~~~~~~~~~~~~~~~~~~~~~~

.. only:: html

   .. figure:: ../_static/rabi_pulse_diagram.svg
      :align: center
      :width: 90%
      :name: rabi-pulse-diagram

      Rabi pulse sequence with variable amplitude drive pulse followed by readout. The drive pulse amplitude is swept from 25 to 75 mV.

.. only:: latex

   .. figure:: ../_static/rabi_pulse_diagram.pdf
      :align: center
      :width: 90%
      :name: rabi-pulse-diagram

      Rabi pulse sequence with variable amplitude drive pulse followed by readout. The drive pulse amplitude is swept from 25 to 75 mV.

Code Example
~~~~~~~~~~~~

.. code-block:: python

    from eq1_pulse.builder import *
    from eq1_pulse.models.basic_types import LinSpace

    with build_sequence() as seq:
        # Declare variables
        var_decl("raw", "complex", unit="mV")
        var_decl("state", "bool")
        var_decl("amp", "float", unit="mV")

        # Sweep amplitude from 0 to 100 mV in 50 steps
        amplitude_sweep = LinSpace(start=0.0, stop=100.0, num=50)

        with for_("amp", amplitude_sweep):
            # Apply drive pulse with variable amplitude
            play(
                "qubit",
                square_pulse(
                    duration="100ns",
                    amplitude=var("amp")
                ),
            )

            # Measure qubit state
            measure_and_discriminate(
                "qubit",
                raw_var="raw_result",
                result_var="qubit_state",
                threshold="0.5mV",
                duration="1us",
                amplitude="50mV",
            )

            # Store the result
            store("rabi_amp", "qubit_state", mode="average")

            # Wait for qubit to relax
            wait("qubit", duration="10us")

Time Rabi
---------

In a time Rabi experiment, we sweep the pulse duration while keeping amplitude fixed. This is useful when amplitude is already calibrated.

Pulse Sequence Diagram
~~~~~~~~~~~~~~~~~~~~~~~

.. only:: html

   .. figure:: ../_static/duration_rabi_pulse_diagram.svg
      :align: center
      :alt: Duration Rabi pulse sequence diagram

      Duration Rabi pulse sequence showing variable duration drive pulse

.. only:: latex

   .. figure:: ../_static/duration_rabi_pulse_diagram.pdf
      :align: center
      :alt: Duration Rabi pulse sequence diagram

      Duration Rabi pulse sequence showing variable duration drive pulse

Code Example
~~~~~~~~~~~~

.. code-block:: python

    from eq1_pulse.builder import *
    from eq1_pulse.models.basic_types import LinSpace

    with build_sequence() as seq:
        var_decl("raw", "complex", unit="mV")
        var_decl("state", "bool")
        var_decl("t_drive", "float", unit="ns")

        # Sweep duration from 0 to 200 ns in 100 steps
        duration_sweep = LinSpace(start=0.0, stop=200.0, num=100)

        with for_("t_drive", duration_sweep):
            # Apply drive pulse with variable duration
            play(
                "qubit",
                square_pulse(
                    duration=var("t_drive"),
                    amplitude="80mV"
                ),
            )

            # Measure and discriminate
            measure_and_discriminate(
                "qubit",
                raw_var="raw_result",
                result_var="qubit_state",
                threshold="0.5mV",
                duration="1us",
                amplitude="50mV",
            )

            # Store result
            store("rabi_time", "qubit_state", mode="average")

            # Relaxation time
            wait("qubit", duration="10us")

Complete Example Script

Frequency Rabi (Spectroscopy)
------------------------------

In frequency Rabi (qubit spectroscopy), we sweep the drive frequency to find the qubit transition frequency. This is essential for initial qubit characterization.

Pulse Sequence Diagram
~~~~~~~~~~~~~~~~~~~~~~~

.. only:: html

   .. figure:: ../_static/frequency_spectroscopy_pulse_diagram.svg
      :align: center
      :alt: Frequency spectroscopy pulse sequence diagram

      Frequency spectroscopy pulse sequence showing frequency sweep

.. only:: latex

   .. figure:: ../_static/frequency_spectroscopy_pulse_diagram.pdf
      :align: center
      :alt: Frequency spectroscopy pulse sequence diagram

      Frequency spectroscopy pulse sequence showing frequency sweep

Code Example
~~~~~~~~~~~~
           (for GaAs spin qubits)

Code Example
~~~~~~~~~~~~

.. code-block:: python

    from eq1_pulse.builder import *
    from eq1_pulse.models.basic_types import LinSpace

    with build_sequence() as seq:
        var_decl("raw", "complex", unit="mV")
        var_decl("state", "bool")
        var_decl("freq", "float", unit="GHz")

        # Sweep frequency around expected qubit frequency
        # For spin qubits in GaAs: typically 10-20 GHz
        freq_sweep = LinSpace(start=14.0, stop=16.0, num=200)

        with for_("freq", freq_sweep):
            # Set drive frequency
            set_frequency("qubit", var("freq"))

            # Apply π/2 pulse (or saturating pulse)
            play(
                "qubit",
                square_pulse(
                    duration="50ns",
                    amplitude="100mV",
                ),
            )

            # Measure
            measure_and_discriminate(
                "qubit",
                raw_var="raw_result",
                result_var="qubit_state",
                threshold="0.5mV",
                duration="1us",
                amplitude="50mV",
            )

            # Store
            store("spectroscopy", "qubit_state", mode="average")

            # Wait
            wait("qubit", duration="10us")

Complete Example Script
------------------------

The complete runnable example is available in the repository:

.. code-block:: bash

    python examples/spin_qubit_rabi.py

This will generate sequences for all three types of Rabi experiments and print the JSON representation of each sequence.

See Also
--------

* :doc:`spin_qubit_t2star` - T2* dephasing measurements
* :doc:`/user_guide/builder_guide` - Detailed builder interface documentation
* :doc:`/autoapi/eq1_pulse/builder/index` - Builder API reference
