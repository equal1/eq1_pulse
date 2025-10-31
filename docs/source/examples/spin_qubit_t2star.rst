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

.. only:: html

   .. figure:: ../_static/t2star_ramsey_pulse_diagram.svg
      :align: center
      :alt: T2* Ramsey pulse sequence diagram

      T2* Ramsey pulse sequence showing free evolution between π/2 pulses

.. only:: latex

   .. figure:: ../_static/t2star_ramsey_pulse_diagram.pdf
      :align: center
      :alt: T2* Ramsey pulse sequence diagram

      T2* Ramsey pulse sequence showing free evolution between π/2 pulses

What Happens
~~~~~~~~~~~~

1. **First π/2 pulse**: Creates equal superposition \|0> + \|1>
2. **Free evolution**: Qubit accumulates phase, dephases due to noise
3. **Second π/2 pulse**: Converts phase to population
4. **Readout**: Measures excited state probability

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

.. only:: html

   .. figure:: ../_static/ramsey_detuning_pulse_diagram.svg
      :align: center
      :alt: Ramsey with detuning pulse sequence diagram

      Ramsey with detuning pulse sequence showing frequency shift

.. only:: latex

   .. figure:: ../_static/ramsey_detuning_pulse_diagram.pdf
      :align: center
      :alt: Ramsey with detuning pulse sequence diagram

      Ramsey with detuning pulse sequence showing frequency shift

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

.. only:: html

   .. figure:: ../_static/hahn_echo_pulse_diagram.svg
      :align: center
      :alt: Hahn echo (spin echo) pulse sequence diagram

      Hahn echo pulse sequence showing π pulse refocusing

.. only:: latex

   .. figure:: ../_static/hahn_echo_pulse_diagram.pdf
      :align: center
      :alt: Hahn echo (spin echo) pulse sequence diagram

      Hahn echo pulse sequence showing π pulse refocusing

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
