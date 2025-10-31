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

.. code-block:: text

    Channel: qubit
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
              ┌────┐         ┌──────────┐
              │    │         │          │
    ──────────┤    ├─────────┤  Readout ├──────────────
              │ X  │  wait   │          │
              │var │         │          │
              └────┘         └──────────┘

    Sweep: amplitude from 0 → 100 mV

Expected Results
~~~~~~~~~~~~~~~~

.. code-block:: text

    P(|1⟩)
      1.0 ┤                 ╭╮                ╭╮
          │                ╱  ╲              ╱  ╲
          │               ╱    ╲            ╱    ╲
      0.5 ┤              ╱      ╲          ╱      ╲
          │             ╱        ╲        ╱        ╲
          │   ╭────────╯          ╰──────╯          ╰────
      0.0 ┤───╯
          └────┴────┴────┴────┴────┴────┴────┴────┴────┴──
               0   20   40   60   80  100  120  140  160
                            Amplitude (mV)

    Key features:
    - Sinusoidal oscillation
    - π pulse: first minimum (amplitude for complete inversion)
    - π/2 pulse: first maximum (amplitude for equal superposition)
    - Rabi frequency ∝ amplitude

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

.. code-block:: text

    Channel: qubit
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
              ┌──var──┐       ┌──────────┐
              │       │       │          │
    ──────────┤   X   ├───────┤  Readout ├──────────────
              │       │ wait  │          │
              │ 80mV  │       │          │
              └───────┘       └──────────┘

    Sweep: duration from 0 → 200 ns

Expected Results
~~~~~~~~~~~~~~~~

.. code-block:: text

    P(|1⟩)
      1.0 ┤         ╱╲           ╱╲          ╱╲
          │        ╱  ╲         ╱  ╲        ╱  ╲
          │       ╱    ╲       ╱    ╲      ╱    ╲
      0.5 ┤      ╱      ╲     ╱      ╲    ╱      ╲
          │     ╱        ╲   ╱        ╲  ╱        ╲
          │────╯          ╲─╯          ╲╯          ╲──
      0.0 ┤
          └────┴────┴────┴────┴────┴────┴────┴────┴────┴──
               0    40   80  120  160  200  240  280  320
                         Duration (ns)

    Key features:
    - Oscillation period = π pulse duration
    - First maximum at π pulse duration
    - Rabi frequency ∝ 1/period

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

Frequency Rabi (Spectroscopy)
------------------------------

In frequency Rabi (qubit spectroscopy), we sweep the drive frequency to find the qubit transition frequency. This is essential for initial qubit characterization.

Pulse Sequence Diagram
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    Channel: qubit
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    set_freq(f)
         │         ┌────┐         ┌──────────┐
         │         │    │         │          │
         └────────►│ X  ├─────────┤  Readout ├──────────
                   │    │  wait   │          │
                   │    │         │          │
                   └────┘         └──────────┘

    Sweep: frequency from 14.0 → 16.0 GHz
           (for GaAs spin qubits)

Expected Results
~~~~~~~~~~~~~~~~

.. code-block:: text

    P(|1⟩)
      1.0 ┤
          │
          │              ╱────╲
      0.5 ┤            ╱        ╲
          │          ╱            ╲
          │──────────                ──────────────────
      0.0 ┤
          └────┴────┴────┴────┴────┴────┴────┴────┴────┴──
              14.0  14.5  15.0  15.5  16.0  16.5  17.0
                       Frequency (GHz)

    Key features:
    - Peak at qubit resonance frequency
    - Width proportional to 1/T2*
    - Height depends on π pulse calibration

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

Experimental Considerations
----------------------------

For Spin Qubits
~~~~~~~~~~~~~~~

Spin qubits in quantum dots have specific characteristics:

* **Typical frequencies**: 10-20 GHz (depends on magnetic field)
* **Typical Rabi frequencies**: 1-10 MHz
* **Typical pulse durations**: 10-100 ns for π pulse
* **Relaxation time (T1)**: 1-100 μs
* **Dephasing time (T2*)**: 0.1-10 μs
* **Wait time**: Should be > 5×T1 for full relaxation

Calibration Workflow
~~~~~~~~~~~~~~~~~~~~

1. **Find resonance** (Frequency Rabi):

   * Sweep frequency with saturating pulse
   * Identify peak in excited state population
   * This is your qubit frequency

2. **Calibrate amplitude** (Amplitude Rabi):

   * Fix duration (e.g., 100 ns)
   * Sweep amplitude
   * π pulse amplitude = first minimum
   * π/2 pulse amplitude = first maximum

3. **Calibrate timing** (Time Rabi):

   * Fix amplitude from step 2
   * Sweep duration
   * π pulse duration = first maximum
   * Verify consistency with amplitude Rabi

Common Issues
~~~~~~~~~~~~~

**No oscillation observed**:

* Check if pulse amplitude is sufficient
* Verify qubit is at the correct frequency
* Ensure measurement threshold is appropriate
* Check if T2* is too short (oscillations decay too fast)

**Oscillations decay too quickly**:

* T2* is limiting your measurement
* Reduce number of points or sweep range
* Improve qubit isolation from noise
* Try different qubit operating point

**Oscillations not centered at 0.5**:

* Measurement pulse may be causing excitation/relaxation
* Adjust measurement amplitude or duration
* Check for qubit heating effects
* Verify proper initialization to ground state

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
