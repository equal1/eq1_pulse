Spin Qubit T2* (Dephasing) Measurement
=======================================

.. note::

   These examples are provided for **illustration purposes only** and may not represent realistic experimental parameters or physical hardware configurations. They demonstrate the API usage patterns rather than actual quantum device specifications.

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

.. plot::
   :align: center
   :caption: T2* Ramsey pulse sequence showing free evolution between π/2 pulses.

   from t2star_ramsey_diagram import create_t2star_ramsey_diagram
   create_t2star_ramsey_diagram()

What Happens
~~~~~~~~~~~~

1. **First π/2 pulse**: Creates equal superposition \|0> + \|1>
2. **Free evolution**: Qubit accumulates phase, dephases due to noise
3. **Second π/2 pulse**: Converts phase to population
4. **Readout**: Measures excited state probability

Code Example
~~~~~~~~~~~~

.. literalinclude:: ../../../examples/spin_qubit_t2star.py
   :language: python
   :pyobject: example_basic_t2star

Ramsey with Detuning
--------------------

Adding an intentional frequency detuning creates faster oscillations, making it easier to observe both the oscillation frequency and the decay envelope.

Pulse Sequence Diagram
~~~~~~~~~~~~~~~~~~~~~~~

.. plot::
   :align: center
   :caption: Ramsey with detuning pulse sequence showing frequency shift.

   from ramsey_detuning_diagram import create_ramsey_detuning_diagram
   create_ramsey_detuning_diagram()

Code Example
~~~~~~~~~~~~

.. literalinclude:: ../../../examples/spin_qubit_t2star.py
   :language: python
   :pyobject: example_t2star_with_detuning

Echo Sequence (T2 Measurement)
-------------------------------

The spin echo sequence refocuses quasi-static noise, measuring the true decoherence time T2 (without inhomogeneous contributions).

Pulse Sequence Diagram
~~~~~~~~~~~~~~~~~~~~~~~

.. plot::
   :align: center
   :caption: Hahn echo pulse sequence showing π pulse refocusing.

   from hahn_echo_diagram import create_hahn_echo_diagram
   create_hahn_echo_diagram()

Code Example
~~~~~~~~~~~~

.. literalinclude:: ../../../examples/spin_qubit_t2star.py
   :language: python
   :pyobject: example_t2star_echo

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
