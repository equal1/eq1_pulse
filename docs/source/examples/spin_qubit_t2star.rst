Spin Qubit T2* (Dephasing) Measurement
=======================================

The T2* (T-two-star) time characterizes how quickly a qubit loses phase coherence due to inhomogeneous dephasing. This includes both intrinsic decoherence and quasi-static noise sources like charge noise and nuclear spin fluctuations.

For spin qubits, T2* measurements help:

* Characterize charge noise and nuclear spin bath effects
* Optimize qubit operating points (sweet spots)
* Assess qubit quality
* Determine limits for gate operation fidelity
* Guide noise mitigation strategies

T2* is measured using a Ramsey experiment: **π/2 - wait(τ) - π/2 - measure**

Basic Ramsey Sequence
---------------------

The standard Ramsey sequence creates a superposition, allows free evolution, then projects back to measure the accumulated phase.

Pulse Sequence Diagram
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    Channel: qubit
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
              ┌─────┐            ┌─────┐      ┌──────────┐
              │     │            │     │      │          │
    ──────────┤ π/2 ├────wait(τ)─┤ π/2 ├──────┤  Readout ├─────
              │     │            │     │      │          │
              │ 25ns│            │ 25ns│      │          │
              └─────┘            └─────┘      └──────────┘

              |←─── Free evolution time τ ───→|

    Sweep: τ from 0 → 10 μs

What Happens
~~~~~~~~~~~~

1. **First π/2 pulse**: Creates equal superposition |0⟩ + |1⟩
2. **Free evolution**: Qubit accumulates phase, dephases due to noise
3. **Second π/2 pulse**: Converts phase to population
4. **Readout**: Measures excited state probability

Expected Results
~~~~~~~~~~~~~~~~

.. code-block:: text

    P(|1⟩)
      1.0 ┤  ╱╲
          │ ╱  ╲  ╱╲
          │╱    ╲╱  ╲  ╱╲      ← Envelope decays as e^(-t/T2*)
      0.5 ┤      ╲   ╲╱  ╲─────
          │       ╲
          │        ╲─────────── ← Final decay to 0.5
      0.0 ┤
          └────┴────┴────┴────┴────┴────┴────┴────┴────┴──
               0    2    4    6    8   10   12   14   16
                          Time τ (μs)

    Key features:
    - Damped sinusoidal oscillation
    - Decay envelope: exp(-τ/T2*)
    - Oscillation frequency: detuning from qubit resonance
    - Final value: 0.5 (complete dephasing)

Code Example
~~~~~~~~~~~~

.. code-block:: python

    from eq1_pulse.builder import *
    from eq1_pulse.models.basic_types import LinSpace

    with build_sequence() as seq:
        var_decl("raw", "complex", unit="mV")
        var_decl("state", "bool")
        var_decl("tau", "float", unit="us")

        # Sweep free evolution time from 0 to 10 μs
        delay_sweep = LinSpace(start=0.0, stop=10.0, num=100)

        with for_("tau", delay_sweep):
            # First π/2 pulse (create superposition)
            play(
                "qubit",
                square_pulse(
                    duration="25ns",
                    amplitude="80mV",
                ),
            )

            # Free evolution time (variable)
            wait("qubit", duration=var("tau"))

            # Second π/2 pulse (convert phase to population)
            play(
                "qubit",
                square_pulse(
                    duration="25ns",
                    amplitude="80mV",
                ),
            )

            # Measurement
            measure_and_discriminate(
                "qubit",
                raw_var="raw_result",
                result_var="qubit_state",
                threshold="0.5mV",
                duration="1us",
                amplitude="50mV",
            )

            # Store result
            store("ramsey", "qubit_state", mode="average")

            # Wait for qubit to relax
            wait("qubit", duration="20us")

Ramsey with Detuning
--------------------

Adding an intentional frequency detuning creates faster oscillations, making it easier to observe both the oscillation frequency and the decay envelope.

Pulse Sequence Diagram
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    Channel: qubit
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    shift_freq(+δ)
         │        ┌─────┐            ┌─────┐      ┌──────────┐
         │        │     │            │     │      │          │
         └───────►│ π/2 ├────wait(τ)─┤ π/2 ├──────┤  Readout ├──
                  │     │            │     │      │          │
                  │ 25ns│            │ 25ns│      │          │
                  └─────┘            └─────┘      └──────────┘
                                                         │
                                                  shift_freq(-δ)

    Detuning: δ = +5 MHz
    Sweep: τ from 0 → 5 μs

Expected Results
~~~~~~~~~~~~~~~~

.. code-block:: text

    P(|1⟩)
      1.0 ┤ ╱╲ ╱╲ ╱╲ ╱╲ ╱╲
          │╱  V  V  V  V  ╲ ╱╲     ← Faster oscillations
          │               V  ╲ ╱╲  ← Same decay envelope
      0.5 ┤                  V  ╲──
          │
          │
      0.0 ┤
          └────┴────┴────┴────┴────┴────┴────┴────┴────┴──
               0    1    2    3    4    5    6    7    8
                          Time τ (μs)

    Oscillation frequency = detuning (5 MHz)
    Decay rate unchanged (still T2*)

Code Example
~~~~~~~~~~~~

.. code-block:: python

    from eq1_pulse.builder import *
    from eq1_pulse.models.basic_types import LinSpace

    with build_sequence() as seq:
        var_decl("raw", "complex", unit="mV")
        var_decl("state", "bool")
        var_decl("tau", "float", unit="us")

        # Detuning from qubit resonance
        detuning = "5MHz"

        # Sweep delay time
        delay_sweep = LinSpace(start=0.0, stop=5.0, num=150)

        with for_("tau", delay_sweep):
            # Apply detuning
            shift_frequency("qubit", detuning)

            # π/2 pulse
            play("qubit", square_pulse(duration="25ns", amplitude="80mV"))

            # Free evolution
            wait("qubit", duration=var("tau"))

            # π/2 pulse
            play("qubit", square_pulse(duration="25ns", amplitude="80mV"))

            # Reset frequency
            shift_frequency("qubit", "-5MHz")

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
            store("ramsey_detuned", "qubit_state", mode="average")

            # Wait
            wait("qubit", duration="20us")

Echo Sequence (T2 Measurement)
-------------------------------

The spin echo sequence refocuses quasi-static noise, measuring the true decoherence time T2 (without inhomogeneous contributions).

Pulse Sequence Diagram
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    Channel: qubit
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
              ┌─────┐          ┌───┐          ┌─────┐      ┌──────────┐
              │     │          │   │          │     │      │          │
    ──────────┤ π/2 ├──wait(τ)─┤ π ├──wait(τ)─┤ π/2 ├──────┤  Readout ├─
              │     │          │   │          │     │      │          │
              │ 25ns│          │50n│          │ 25ns│      │          │
              └─────┘          └───┘          └─────┘      └──────────┘

              |← τ/2 →|  π pulse  |← τ/2 →|
                       (refocus)

    Sweep: τ from 0 → 50 μs

Expected Results
~~~~~~~~~~~~~~~~

.. code-block:: text

    P(|1⟩)
      1.0 ┤╲
          │ ╲
          │  ╲                      ← Slower decay
      0.5 ┤   ╲─────────────────────  (T2 > T2*)
          │
          │
      0.0 ┤
          └────┴────┴────┴────┴────┴────┴────┴────┴────┴──
               0   10   20   30   40   50   60   70   80
                          Total time τ (μs)

    T2 > T2* because:
    - π pulse refocuses quasi-static noise
    - Only measures true decoherence
    - Typically T2 ≈ 2×T2* for spin qubits

Code Example
~~~~~~~~~~~~

.. code-block:: python

    from eq1_pulse.builder import *
    from eq1_pulse.models.basic_types import LinSpace

    with build_sequence() as seq:
        var_decl("raw", "complex", unit="mV")
        var_decl("state", "bool")
        var_decl("tau", "float", unit="us")

        # Sweep total evolution time
        delay_sweep = LinSpace(start=0.0, stop=50.0, num=100)

        with for_("tau", delay_sweep):
            # First π/2 pulse
            play("qubit", square_pulse(duration="25ns", amplitude="80mV"))

            # First half of evolution
            # Note: tau/2 requires expression evaluation
            wait("qubit", duration=var("tau"))  # Simplified: use full tau

            # π pulse (refocusing)
            play("qubit", square_pulse(duration="50ns", amplitude="80mV"))

            # Second half of evolution
            wait("qubit", duration=var("tau"))

            # Final π/2 pulse
            play("qubit", square_pulse(duration="25ns", amplitude="80mV"))

            # Measure
            measure_and_discriminate(
                "qubit",
                raw_var="raw_result",
                result_var="qubit_state",
                threshold="0.5mV",
                duration="1us",
                amplitude="50mV",
            )

            store("echo", "qubit_state", mode="average")
            wait("qubit", duration="100us")

Data Analysis
-------------

Extracting T2*
~~~~~~~~~~~~~~

Fit the Ramsey data to:

.. math::

    P(|1\\rangle) = A \\cdot e^{-t/T_2^*} \\cdot \\cos(2\\pi f_{\\text{det}} t + \\phi) + C

Where:

* :math:`A` = oscillation amplitude
* :math:`T_2^*` = dephasing time (fit parameter)
* :math:`f_{\\text{det}}` = detuning frequency
* :math:`\\phi` = initial phase
* :math:`C` = offset (typically 0.5)

Extracting T2
~~~~~~~~~~~~~

Fit the echo data to:

.. math::

    P(|1\\rangle) = A \\cdot e^{-t/T_2} + C

Simpler exponential decay without oscillations.

Relationship Between T1, T2*, and T2
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For a qubit:

.. math::

    \\frac{1}{T_2} \\leq \\frac{1}{2T_1} + \\frac{1}{T_2^{\\text{pure}}}

Where :math:`T_2^{\\text{pure}}` is pure dephasing time.

In the limit where :math:`T_2^{\\text{pure}} \\gg T_1`:

.. math::

    T_2 \\approx 2T_1

Experimental Considerations
----------------------------

For Spin Qubits
~~~~~~~~~~~~~~~

Typical values for GaAs spin qubits:

* **T2***: 0.1 - 10 μs
* **T2**: 1 - 100 μs
* **T1**: 1 - 100 μs
* **Typical detuning**: 1 - 10 MHz

Noise Sources
~~~~~~~~~~~~~

**Charge noise**:

* Dominant for singlet-triplet qubits
* Couples via detuning
* Can be reduced at sweet spots

**Nuclear spin bath**:

* Hyperfine interaction with nuclear spins
* Causes T2* ~ 10-100 ns in GaAs
* Can be suppressed with:

  * Nuclear spin polarization
  * Isotopic purification (e.g., :math:`^{28}\\text{Si}`)
  * Dynamical decoupling sequences

**Magnetic field noise**:

* Affects Zeeman splitting
* Can be reduced with magnetic shielding

Optimization Strategies
~~~~~~~~~~~~~~~~~~~~~~~

1. **Find sweet spots**: Operating points where :math:`\\partial E / \\partial \\epsilon = 0`
2. **Use echo sequences**: Refocus quasi-static noise
3. **Apply CPMG**: Multiple π pulses extend coherence
4. **Optimize gates**: Shorter gates reduce dephasing during operations

Common Issues
~~~~~~~~~~~~~

**Very fast decay** (T2* < 100 ns):

* Strong charge noise coupling
* Move to different operating point
* Check gate voltage stability

**No oscillations visible**:

* T2* too short relative to sweep range
* Reduce sweep range
* Add intentional detuning

**Oscillation frequency unexpected**:

* Qubit frequency has drifted
* Re-run spectroscopy
* Check DC voltage stability

Complete Example Script
------------------------

The complete runnable example is available:

.. code-block:: bash

    python examples/spin_qubit_t2star.py

This generates sequences for Ramsey, detuned Ramsey, and echo experiments.

See Also
--------

* :doc:`spin_qubit_rabi` - Rabi oscillation experiments
* :doc:`/user_guide/builder_guide` - Builder interface guide
* :doc:`/autoapi/eq1_pulse/builder/index` - Builder API reference
