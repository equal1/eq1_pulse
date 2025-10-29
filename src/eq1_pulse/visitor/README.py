"""Visitor Infrastructure for Pulse Models.

Overview
--------

This subpackage provides a visitor pattern infrastructure for traversing
Schedule and Sequence models recursively. The visitor pattern allows you to
separate the traversal logic from the operations being performed on the nodes.

Architecture
------------

The visitor infrastructure consists of:

1. **Base Visitors** (``base.py``):
   - ``BaseVisitor``: Abstract base class with visit methods for all operation types
   - ``SequenceVisitor``: Specialized visitor for OpSequence models
   - ``ScheduleVisitor``: Specialized visitor for Schedule models

2. **Converters** (``converters.py``):
   - ``schedule_to_sequence()``: Convert Schedule to OpSequence
   - ``sequence_to_schedule()``: Convert OpSequence to Schedule
   - ``to_absolute_timing()``: Convert to absolute timing for visualization

3. **Examples** (``examples.py``):
   - ``ChannelCollectorSequence``: Collect all channels used in a sequence
   - ``ChannelCollectorSchedule``: Collect all channels used in a schedule

Model Structure
---------------

The visitor infrastructure handles the following model hierarchy:

**Root Structures:**
- ``OpSequence``: A sequence of operations with implicit timing
- ``Schedule``: A collection of scheduled operations with explicit timing

**Container Operations:**
- ``Repetition`` / ``SchedRepetition``: Repeated execution
- ``Iteration`` / ``SchedIteration``: Iteration over values
- ``Conditional`` / ``SchedConditional``: Conditional execution
- Nested ``OpSequence`` / ``Schedule``

**Leaf Operations:**

Channel Operations:
- ``Play``: Play a pulse
- ``Wait``: Wait for a duration
- ``Barrier``: Synchronization barrier
- ``SetFrequency`` / ``ShiftFrequency``: Frequency control
- ``SetPhase`` / ``ShiftPhase``: Phase control
- ``Record``: Record data
- ``Trace``: Trace measurement
- ``CompensateDC``: DC compensation

Data Operations:
- ``VariableDecl``: Variable declaration
- ``PulseDecl``: Pulse declaration
- ``Discriminate``: Discrimination operation
- ``Store``: Store operation

Usage
-----

Creating a Custom Visitor
~~~~~~~~~~~~~~~~~~~~~~~~~~

To create a custom visitor, subclass either ``SequenceVisitor`` or ``ScheduleVisitor``
and override the methods you need:

.. code-block:: python

    from eq1_pulse.visitor import SequenceVisitor

    class MyVisitor(SequenceVisitor[int]):
        def visit_play(self, node):
            # Custom logic for Play operations
            return 1

        def generic_visit(self, node):
            # Fallback for other operations
            return 0

        def combine_sequence_results(self, node, results):
            # Combine results from a sequence
            return sum(results)

Using the Channel Collector
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The channel collector is a useful utility for finding all channels used:

.. code-block:: python

    from eq1_pulse.models import OpSequence, Play
    from eq1_pulse.models.pulse_types import Gaussian
    from eq1_pulse.visitor.examples import ChannelCollectorSequence

    seq = OpSequence([
        Play("ch1", Gaussian(duration=100e-9, sigma=10e-9)),
        Play("ch2", Gaussian(duration=100e-9, sigma=10e-9)),
    ])

    collector = ChannelCollectorSequence()
    channels = collector.visit_opsequence(seq)
    print(channels)  # {'ch1', 'ch2'}

Visitor Pattern Details
-----------------------

The visitor pattern works by:

1. **Dispatching**: The ``visit()`` method dispatches to specific visit methods
   based on the node type (e.g., ``visit_play()`` for Play operations).

2. **Recursive Traversal**: Container operations (Repetition, Iteration, etc.)
   recursively visit their body/children.

3. **Result Combining**: Methods like ``combine_sequence_results()`` allow you
   to aggregate results from child nodes.

Key Principles
--------------

**Synchronization Blocks**

Every iteration block, conditional, or subsequence/subschedule is a block that
synchronizes all channels used within at begin/end. This is important for both
conversion algorithms and timing analysis.

**Timing Models**

- **Sequence**: Implicit timing based on earliest possible start time
- **Schedule**: Explicit relative timing with reference points
- **Absolute Timing**: Computed timing for visualization

Future Enhancements
-------------------

The converter functions (``schedule_to_sequence``, ``sequence_to_schedule``,
``to_absolute_timing``) are placeholders. Implementation will require:

1. **Schedule to Sequence**:
   - Convert relative timing to Wait operations
   - Insert waits to maintain timing relationships
   - Handle synchronization at block boundaries

2. **Sequence to Schedule**:
   - Convert Wait operations to relative timing
   - Compute reference points and offsets
   - Handle synchronization at block boundaries

3. **Absolute Timing**:
   - Compute absolute start/end times for all operations
   - Track per-channel timelines
   - Handle control flow (loops, conditionals)
   - Generate visualization-friendly data structure
"""

__all__ = ()  # This is a documentation module
