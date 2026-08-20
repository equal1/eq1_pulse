Spin Qubit Rabi Oscillations
=============================

.. note::

   These examples are provided for **illustration purposes only** and may not represent realistic experimental parameters or physical hardware configurations. They demonstrate the API usage patterns rather than actual quantum device specifications.

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

.. plot::
   :align: center
   :caption: Rabi pulse sequence with variable amplitude drive pulse followed by readout. The drive pulse amplitude is swept from 25 to 75 mV.

   from rabi_diagram import create_rabi_diagram
   create_rabi_diagram()

Code Example
~~~~~~~~~~~~

.. literalinclude:: ../../../examples/spin_qubit_rabi.py
   :language: python
   :pyobject: example_amplitude_rabi

Time Rabi
---------

In a time Rabi experiment, we sweep the pulse duration while keeping amplitude fixed. This is useful when amplitude is already calibrated.

Pulse Sequence Diagram
~~~~~~~~~~~~~~~~~~~~~~~

.. plot::
   :align: center
   :caption: Duration Rabi pulse sequence showing variable duration drive pulse.

   from duration_rabi_diagram import create_duration_rabi_diagram
   create_duration_rabi_diagram()

Code Example
~~~~~~~~~~~~

.. literalinclude:: ../../../examples/spin_qubit_rabi.py
   :language: python
   :pyobject: example_time_rabi

Complete Example Script

Frequency Rabi (Spectroscopy)
------------------------------

In frequency Rabi (qubit spectroscopy), we sweep the drive frequency to find the qubit transition frequency. This is essential for initial qubit characterization.

Pulse Sequence Diagram
~~~~~~~~~~~~~~~~~~~~~~~

.. plot::
   :align: center
   :caption: Frequency spectroscopy pulse sequence showing frequency sweep.

   from frequency_spectroscopy_diagram import create_frequency_spectroscopy_diagram
   create_frequency_spectroscopy_diagram()

Code Example
~~~~~~~~~~~~

.. literalinclude:: ../../../examples/spin_qubit_rabi.py
   :language: python
   :pyobject: example_frequency_rabi

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
