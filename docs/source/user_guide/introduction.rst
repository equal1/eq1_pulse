Introduction to eq1_pulse
==========================

Overview
--------

``eq1_pulse`` is a Python library that provides a uniform and portable intermediate representation for pulse-level quantum programs. It enables you to describe quantum operations at the pulse level with precise control over timing, amplitudes, phases, and frequencies.

The library is designed to:

* Provide a **hardware-agnostic** representation of pulse programs
* Support both **sequence-based** (ordered operations) and **schedule-based** (timed operations) programming models
* Enable **control flow** including loops, conditionals, and branching
* Offer a **builder interface** for intuitive pulse program construction
* Support **quantum measurements** with discrimination and conditional feedback
* Maintain **type safety** with Pydantic-based models

Key Features
------------

Hardware-Agnostic Design
~~~~~~~~~~~~~~~~~~~~~~~~

Programs written with ``eq1_pulse`` are portable across different quantum hardware platforms. The library focuses on the logical description of pulse operations rather than hardware-specific implementation details.

Flexible Programming Models
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Sequences**
    Ordered operations where timing is implicit. Each operation follows the previous one on the same channel.

**Schedules**
    Explicitly timed operations with precise control over when each operation starts, using reference points and relative timing.

Rich Type System
~~~~~~~~~~~~~~~~

Built on Pydantic models, the library provides:

* Type-safe construction and validation
* Automatic unit conversion (e.g., ``V`` ↔ ``mV``, ``s`` ↔ ``ns``)
* JSON serialization/deserialization
* Schema generation for documentation

Builder Interface
~~~~~~~~~~~~~~~~~

A Pythonic context manager-based API for constructing pulse programs:

.. code-block:: python

    from eq1_pulse.builder import *

    with build_sequence() as seq:
        play("qubit", square_pulse(duration="100ns", amplitude="50mV"))
        measure("qubit", result_var="result", duration="1us", amplitude="30mV")

Installation
------------

Using pip from GitHub:

.. code-block:: bash

    pip install eq1_pulse@git+https://github.com/equal1/eq1_pulse.git

For development installation:

.. code-block:: bash

    git clone https://github.com/equal1/eq1_pulse.git
    cd eq1_pulse
    pip install -e .

Quick Start
-----------

Here's a minimal example creating a simple pulse sequence:

.. code-block:: python

    from eq1_pulse.builder import *

    # Create a sequence
    with build_sequence() as seq:
        # Play a square pulse on the 'drive' channel
        play("drive", square_pulse(duration="10us", amplitude="100mV"))

        # Wait for 5 microseconds
        wait("drive", duration="5us")

        # Play another pulse
        play("drive", square_pulse(duration="20us", amplitude="50mV"))

    # Export to JSON
    print(seq.model_dump_json(indent=2))

Core Concepts
-------------

Channels
~~~~~~~~

Operations are applied to named channels representing physical control lines or measurement devices. Examples:

* ``"qubit"`` - qubit control line
* ``"drive"`` - drive/excitation channel
* ``"readout"`` - measurement/readout channel

Pulses
~~~~~~

Pulses are waveforms with defined shape, duration, amplitude, and optional frequency/phase:

* **Square pulse** - constant amplitude
* **Sine pulse** - sinusoidal waveform
* **Externally defined pulse** - functions generating the waveform, such as Gaussian or DRAG pulses
* **Arbitrary pulse** - user-defined waveform samples with interpolation

Basic Types
~~~~~~~~~~~

The library provides precise types for physical quantities:

* ``Duration`` - time intervals (nonnegative)
* ``Time`` - absolute or relative time points
* ``Frequency`` - oscillation frequencies
* ``Amplitude`` - complex voltage amplitudes
* ``Voltage`` - real voltages
* ``Angle``/``Phase`` - rotation angles
* ``Threshold`` - discrimination thresholds

Variables
~~~~~~~~~

Named variables store measurement results or sweep parameters:

.. code-block:: python

    var_decl("result", "complex", unit="mV")
    var_decl("amplitude", "float", unit="mV")

Control Flow
~~~~~~~~~~~~

**Repetition**
    Repeat operations a fixed number of times:

    .. code-block:: python

        with repeat(10):
            play("qubit", pulse)

**Iteration**
    Loop over a range or sequence of values:

    .. code-block:: python

        with for_("freq", range(4000, 6000, 100)):
            set_frequency("qubit", var("freq"))
            play("qubit", pulse)

**Conditionals**
    Execute operations based on measurement outcomes:

    .. code-block:: python

        with if_("state"):
            play("qubit", correction_pulse)

Next Steps
----------

* :doc:`builder_guide` - Detailed guide to the builder interface
* :doc:`/examples/index` - Example programs and tutorials
* :doc:`/autoapi/eq1_pulse/models/index` - API reference
