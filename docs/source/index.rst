.. eq1lab documentation master file, created by
   sphinx-quickstart on Tue Aug  6 14:36:35 2024.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

eq1_pulse: Pulse-Level Quantum Programming
===========================================

``eq1_pulse`` is a Python library for creating hardware-agnostic pulse-level quantum programs. It provides a flexible intermediate representation for quantum operations with precise control over timing, amplitudes, phases, and frequencies.

.. toctree::
   :maxdepth: 2
   :caption: User Guide

   user_guide/index

.. toctree::
   :maxdepth: 2
   :caption: Examples

   examples/index

.. toctree::
   :maxdepth: 3
   :caption: API Reference

   autoapi/eq1_pulse/models/index.rst

Quick Links
-----------

* :doc:`user_guide/introduction` - Get started with eq1_pulse
* :doc:`user_guide/builder_guide` - Learn the builder interface
* :doc:`examples/basic_usage` - Simple examples to try
* :doc:`examples/spin_qubit_rabi` - Rabi oscillation experiments
* :doc:`examples/spin_qubit_t2star` - Coherence time measurements

Key Features
------------

* **Hardware-agnostic** pulse program representation
* **Builder interface** for intuitive program construction
* **Type-safe** models with automatic validation
* Support for **sequences** and **schedules**
* **Control flow**: loops, conditionals, and branching
* **Measurement** operations with discrimination
* **JSON serialization** for portability

Installation
------------

.. code-block:: bash

    pip install eq1_pulse@git+https://github.com/equal1/eq1_pulse.git

Quick Example
-------------

.. code-block:: python

    from eq1_pulse.builder import *

    with build_sequence() as seq:
        # Play a pulse
        play("qubit", square_pulse(duration="100ns", amplitude="50mV"))

        # Measure
        var_decl("result", "complex", unit="mV")
        measure("qubit", result_var="result", duration="1us", amplitude="30mV")

    # Export to JSON
    print(seq.model_dump_json(indent=2))


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
