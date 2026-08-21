External Block Examples
========================

.. note::

   These examples are provided for **illustration purposes only** and may not represent realistic experimental parameters or physical hardware configurations. They demonstrate the API usage patterns rather than actual quantum device specifications.

An :class:`~eq1_pulse.models.ExternalBlock` reserves a set of channels for the duration of an
externally defined program without describing its contents in this IR -- the seed of OpenQASM
``box`` and the way an OpenPulse ``defcal`` is consumed. See :class:`~eq1_pulse.models.ExternalBlock`
for the full reservation and timing semantics.

Named Channel Roles
--------------------

Use ``channels={"role": channel, ...}`` when the referenced program distinguishes between the
channels it uses (e.g. drive vs. readout):

.. literalinclude:: ../../../examples/external_block_example.py
   :language: python
   :pyobject: example_named_channel_roles

Positional Channels
--------------------

When the roles do not matter, channels can be passed positionally. Placeholder role keys
(``"0"``, ``"1"``, ...) are generated deterministically in argument order:

.. literalinclude:: ../../../examples/external_block_example.py
   :language: python
   :pyobject: example_positional_channels

Timed vs. Flex Duration
-------------------------

``duration=D`` is a hard total-duration constraint; ``duration=None`` is *flex*, meaning the
duration is whatever the referenced program naturally takes:

.. literalinclude:: ../../../examples/external_block_example.py
   :language: python
   :pyobject: example_timed_vs_flex

Pure Reservation
------------------

With ``program=None``, an ``ExternalBlock`` reserves channels for an externally driven interval
without referencing any program at all:

.. literalinclude:: ../../../examples/external_block_example.py
   :language: python
   :pyobject: example_pure_reservation

Results Binding
-----------------

``results`` binds output variables the referenced program writes into. Each variable must already
be declared in an enclosing scope:

.. literalinclude:: ../../../examples/external_block_example.py
   :language: python
   :pyobject: example_results_binding

Running the Examples
----------------------

Execute the complete example script:

.. code-block:: bash

    python examples/external_block_example.py

See Also
--------

* :doc:`/user_guide/builder_guide` - Builder interface documentation
* :doc:`/autoapi/eq1_pulse/models/index` - Model API reference, including :class:`~eq1_pulse.models.ExternalBlock`
