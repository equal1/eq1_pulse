Builder Interface Guide
=======================

The builder interface provides a high-level, Pythonic API for constructing pulse sequences. It uses Python context managers and provides functions that closely mirror the underlying model structure while offering a more intuitive programming experience.

.. note::

    An explicitly-timed **schedule** builder also exists (:mod:`eq1_pulse.builder.experimental`), but it
    is unused and scheduled for removal -- see :doc:`/experimental/schedule`.

Getting Started
---------------

Import the builder functions:

.. code-block:: python

    from eq1_pulse.builder import *

The Builder vs. the Model
--------------------------

The builder takes what you mean; the model takes what the wire says.

``play("qubit", square_pulse(duration="10us", amplitude="100mV"))`` accepts a channel name as a
bare string, a duration as a unit-suffixed string, and an amplitude the same way. Of these, only the
channel string is a wire form: :class:`~eq1_pulse.models.channel_ops.Play` is typed to accept a bare
string directly, because that *is* the canonical spelling of a channel reference. The duration and
amplitude strings are not -- ``"10us"``/``"100mV"`` are authoring conveniences the builder resolves
into the canonical unit objects (``{"us": 10}``, ``{"mV": 100}``) before constructing anything, and
``model_validate`` never accepts them.

.. code-block:: python

    from eq1_pulse.builder import build_sequence, play, square_pulse
    from eq1_pulse.models.sequence import OpSequence

    with build_sequence() as seq:
        play("qubit", square_pulse(duration="10us", amplitude="100mV"))

    # The builder produced this canonical JSON document -- durations and amplitudes as unit
    # objects, the channel as its bare name -- not the "10us" / "100mV" strings that were written:
    document = seq.model_dump_json(indent=2)
    print(document)

    # Anything that produces this same document, from any source, re-reads into an identical
    # sequence: model_validate() never sees or accepts the authoring strings, only the wire form.
    assert OpSequence.model_validate_json(document) == seq

This is why a model's `*Like` type aliases (:data:`~eq1_pulse.models.basic_types.DurationLike`,
:data:`~eq1_pulse.models.reference_types.ChannelRefLike`, ...) exist only in the builder's function
signatures, under ``TYPE_CHECKING``: they describe what a *constructor call* accepts, not what
``model_validate`` accepts from the wire.

Wire format
-----------

Two conventions coexist in the wire form, and code that builds or reads a document by hand needs to
know which one applies where.

**Operations nest.** Every operation serializes as a single-key object whose sole key names the
operation, e.g. :class:`~eq1_pulse.models.channel_ops.Play`:

.. code-block:: json

    {
      "play": {
        "channel": "qubit",
        "pulse": {
          "pulse_type": "square",
          "duration": {"ns": 100},
          "amplitude": {"mV": 50}
        }
      }
    }

**Pulses and integrations stay flat.** :obj:`~eq1_pulse.models.pulse_types.PulseType` and the
integration types keep their discriminator field (``pulse_type`` / ``integration_type``) inline
alongside their other fields instead of nesting under a key:

.. code-block:: json

    {"pulse_type": "square", "duration": {"ns": 100}, "amplitude": {"mV": 50}}

.. code-block:: json

    {"integration_type": "full"}

**Expression operator nodes nest, with the operator under** ``op``. A
:class:`~eq1_pulse.models.expressions.BinaryExpr` and its sibling operator nodes serialize the same
way operations do -- keyed by field name -- with the operator symbol carried in an ``op`` field:

.. code-block:: json

    {"binary_op": {"op": "+", "lhs": {"...": "..."}, "rhs": {"...": "..."}}}

``LiteralExpr`` and ``SymbolExpr`` do not opt into this nesting and keep their flat form.

**A bare variable name stays bare.** Fields typed :obj:`~eq1_pulse.models.reference_types.VarName`
-- ``Discriminate.target``/``source``, ``Record.var``, ``IterationBase.var`` among them -- hold the
identifier directly:

.. code-block:: json

    {"for": {"var": "amp", "items": {"...": "..."}, "body": ["..."]}}

Everywhere else a variable reference appears in a union position alongside a literal value or an
external reference -- for example a pulse's ``amplitude`` -- it is a
:class:`~eq1_pulse.models.reference_types.VariableRef` and keeps its own tag:

.. code-block:: json

    {"amplitude": {"var": "amp"}}

The field name and the tag both happen to read ``var`` here, which is exactly the case to watch for:
``"var": "amp"`` (bare, field is ``VarName``) and ``{"var": "amp"}`` (tagged, field holds a
``VariableRef``) are not interchangeable, and only one is valid at a given field.

Building Sequences
-------------------

A **sequence** is an ordered list of operations where timing is implicit. Operations on the same channel execute sequentially.

.. code-block:: python

    with build_sequence() as seq:
        play("qubit", square_pulse(duration="100ns", amplitude="50mV"))
        wait("qubit", duration="50ns")
        play("qubit", square_pulse(duration="100ns", amplitude="50mV"))

In this sequence:

1. First pulse plays for 100ns
2. Then waits 50ns
3. Then second pulse plays for 100ns

Total time on the ``"qubit"`` channel: 250ns

Core Operations
---------------

Playing Pulses
~~~~~~~~~~~~~~

The ``play()`` function sends a pulse to a channel:

.. code-block:: python

    play(channel, pulse, *, scale_amp=None, cond=None)

Parameters:

* ``channel`` - The channel to play on
* ``pulse`` - The pulse to play
* ``scale_amp`` - Optional amplitude scaling factor (float, complex, or variable)
* ``cond`` - Optional condition variable (pulse plays only if condition is true)

Example:

.. code-block:: python

    with build_sequence() as seq:
        play("drive", square_pulse(duration="10us", amplitude="100mV"))

        # With amplitude scaling
        play("drive", square_pulse(duration="10us", amplitude="100mV"), scale_amp=0.5)

Waiting
~~~~~~~

The ``wait()`` function creates a delay on a channel:

.. code-block:: python

    wait(*channels, duration)

Example:

.. code-block:: python

    wait("qubit", duration="100ns")

Setting Frequency
~~~~~~~~~~~~~~~~~

The ``set_frequency()`` function changes the oscillator frequency for a channel:

.. code-block:: python

    set_frequency(channel, frequency)

Example:

.. code-block:: python

    set_frequency("qubit", frequency="5.2GHz")

    # Or with a variable
    set_frequency("qubit", var("freq"))

Setting Phase
~~~~~~~~~~~~~

The ``set_phase()`` function updates the phase of a channel:

.. code-block:: python

    set_phase(channel, phase)

Example:

.. code-block:: python

    set_phase("drive", phase="90deg")

Shifting Phase
~~~~~~~~~~~~~~

The ``shift_phase()`` function adds an offset to the current phase:

.. code-block:: python

    shift_phase(channel, phase)

Example:

.. code-block:: python

    shift_phase("drive", phase="45deg")

Barriers
~~~~~~~~

The ``barrier()`` function synchronizes multiple channels:

.. code-block:: python

    barrier(*channels)

Example:

.. code-block:: python

    # Ensure both channels reach this point before continuing
    barrier("drive", "readout")

    # After barrier, these start at the same time
    play("drive", pulse1)
    play("readout", pulse2)

Wait for Trigger
~~~~~~~~~~~~~~~~

The ``wait_for_trigger()`` function blocks a channel's own timeline until a digital trigger line
goes high:

.. code-block:: python

    wait_for_trigger(channel)

The channel must be a digital input line -- nothing in the model enforces this, it is a property
of the target's hardware configuration. This is **not** a barrier: it blocks only the channel it
is called on, and other channels continue independently. To make several channels wait on one
trigger, combine ``barrier()`` with a ``wait_for_trigger()`` on each:

.. code-block:: python

    barrier("ch1", "ch2")
    wait_for_trigger("ch1")
    wait_for_trigger("ch2")

Example:

.. code-block:: python

    from eq1_pulse.builder import *

    with build_sequence():
        # Tell external instrumentation to start, then block until it acknowledges.
        play("trig_out", trigger_pulse(duration="100ns"))
        wait_for_trigger("trig_in")

        play("q0_drive", square_pulse(duration="25ns", amplitude="80mV"))

DC Compensation
~~~~~~~~~~~~~~~

The ``compensate_dc()`` function plays a square wave sized so the channel's accumulated
(integrated) output returns to a zero average since the last reset. This is used to cancel out DC
offset built up by asymmetric pulse sequences, which can otherwise saturate AC-coupled readout
or drive lines over many shots:

.. code-block:: python

    compensate_dc(channel, *, duration, max_amp=None, rise_time=None, fall_time=None)

Parameters:

* ``channel`` - The channel to compensate
* ``duration`` - Duration of the compensation pulse, or :obj:`None` to reset the accumulator to
  zero *without* playing anything
* ``max_amp`` - Optional cap on the compensation pulse amplitude. If the ideal amplitude would
  exceed it, only part of the accumulated area is compensated, leaving the rest for a later call
* ``rise_time`` / ``fall_time`` - Optional linear ramps at the start/end of the pulse

Example:

.. code-block:: python

    with build_sequence():
        play("qubit", square_pulse(duration="200ns", amplitude="100mV"))

        # Bring the accumulated DC offset back to zero, capped at 150mV
        compensate_dc("qubit", duration="200ns", max_amp="150mV")

        # Elsewhere: reset the accumulator without playing anything
        compensate_dc("qubit", duration=None)

Pulse Shapes
------------

.. important::
    **Amplitude and Phase**: All pulse amplitudes in eq1_pulse are **complex numbers**. The magnitude represents
    the pulse strength, and the phase is encoded in the complex argument. You can specify phase in several ways:

    1. **Recommended**: Use ``Amplitude`` and ``Phase`` types with matrix multiplication:
       ``Amplitude(mV=50) @ Phase(deg=90)``
    2. Using string notation and the phase helper function: ``"50mV" @ phase("90deg")``
    3. Using channel-level phase operations: ``set_phase``, ``shift_phase`` (rotates all pulses on a channel)

    The ``Phase`` is converted to :math:`e^{i\phi}` when matrix-multiplied with ``Amplitude``.

Square Pulse
~~~~~~~~~~~~

A constant-amplitude rectangular pulse:

.. code-block:: python

    square_pulse(*, duration, amplitude, rise_time=None, fall_time=None)

The ``rise_time`` and ``fall_time`` parameters define linear ramps at the beginning and end of the pulse,
enabling trapezoidal or ramp-shaped pulses. These times are included in the total pulse duration.

.. note::
    Phase is controlled through the **complex amplitude** parameter. Use ``Amplitude`` and ``Phase``
    types with the ``Phase``  to encode phase while preserving units.
    Alternatively, use channel-level phase operations (``set_phase``, ``shift_phase``).

Example:

.. code-block:: python

    from eq1_pulse.builder import *
    from eq1_pulse.models import Amplitude, Phase

    # Basic square pulse with real amplitude
    pulse = square_pulse(duration="100ns", amplitude="50mV")

    # Pulse with 90-degree phase shift
    pulse = square_pulse(
        duration="100ns",
        amplitude=Amplitude(mV=50) @ Phase(deg=90)
    )

    # Ramp pulse with rise and fall times
    ramp = square_pulse(
        duration="100ns",
        amplitude="50mV",
        rise_time="10ns",
        fall_time="10ns"
    )

Sine Pulse
~~~~~~~~~~

A sinusoidal waveform:

.. code-block:: python

    sine_pulse(*, duration, amplitude, frequency, to_frequency=None)

The ``to_frequency`` parameter enables frequency-swept (chirp) pulses. When specified, the frequency
linearly sweeps from ``frequency`` to ``to_frequency`` over the pulse duration.

.. note::
    Phase is controlled through the **complex amplitude** parameter.
    Matrix-multiply ``Amplitude`` with the ``Phase`` to encode phase while preserving units.
    Alternatively, use channel-level phase operations (``set_phase``, ``shift_phase``).

Example:

.. code-block:: python

    from eq1_pulse.builder import *

    # Basic sine pulse at fixed frequency
    pulse = sine_pulse(
        duration="1us",
        amplitude="30mV",
        frequency="5GHz"
    )

    # Sine pulse with 45-degree phase shift
    pulse = sine_pulse(
        duration="1us",
        amplitude="30mV" @ phase("45deg"),
        frequency="5GHz"
    )

    # Chirp pulse with frequency sweep and 90-degree initial phase shift
    chirp = sine_pulse(
        duration="1us",
        amplitude="30mV" @ phase(deg=90),
        frequency="5GHz",
        to_frequency="6GHz"
    )

External Pulse
~~~~~~~~~~~~~~

Reference a pulse shape defined in an external library or function:

.. code-block:: python

    external_pulse(function, *, duration, amplitude, params=None)

The ``function`` parameter should be a fully qualified name (e.g., ``"my_lib.gaussian"``).
The external function is expected to generate the pulse waveform.

Example:

.. code-block:: python

    # Reference a Gaussian pulse from external library
    pulse = external_pulse(
        "pulse_lib.gaussian",
        duration="200ns",
        amplitude="50mV",
        params={"sigma": 40}
    )

    # Reference a DRAG pulse
    drag = external_pulse(
        "pulse_lib.drag",
        duration="200ns",
        amplitude="50mV",
        params={
            "sigma": 40,
            "beta": 0.5
        }
    )

Arbitrary Sampled Pulse
~~~~~~~~~~~~~~~~~~~~~~~~

Define a custom pulse using explicit sample points:

.. code-block:: python

    arbitrary_pulse(samples, *, duration, amplitude, interpolation=None, time_points=None)

Samples should be normalized (peak value of 1.0) and will be scaled by the amplitude.

Example:

.. code-block:: python

    # Triangle pulse
    triangle = arbitrary_pulse(
        samples=[0.0, 0.5, 1.0, 0.5, 0.0],
        duration="100ns",
        amplitude="50mV"
    )

    # Complex IQ pulse
    iq_samples = [0.0+0.0j, 0.5+0.3j, 1.0+0.0j, 0.5-0.3j, 0.0+0.0j]
    iq_pulse = arbitrary_pulse(
        samples=iq_samples,
        duration="80ns",
        amplitude="75mV",
        interpolation="linear"
    )

    # Pulse with explicit time points
    custom = arbitrary_pulse(
        samples=[0.0, 1.0, 1.0, 0.0],
        duration="200ns",
        amplitude="60mV",
        time_points=[0.0, 0.2, 0.8, 1.0]  # Normalized time points
    )

Step Pulse
~~~~~~~~~~

Steps the channel to a new amplitude and leaves it there:

.. code-block:: python

    step_pulse(*, duration, amplitude)

The amplitude is reached instantaneously at the start -- there is no ramp. Unlike every other
pulse, the level does **not** return to the previous base level afterwards: it persists past the
end of the pulse and becomes the channel's new base level, which subsequent pulses on that
channel are relative to. ``duration`` is how long the step occupies the channel, not how long the
level lasts -- it exists only so the next operation on the channel is correctly ordered after
this one.

Example:

.. code-block:: python

    from eq1_pulse.builder import *

    # Move the DC bias to a new operating point and leave it there.
    pulse = step_pulse(duration="1us", amplitude="150mV")

Digital Trigger Pulse
~~~~~~~~~~~~~~~~~~~~~

Sets a digital trigger line high for a duration, then returns it low:

.. code-block:: python

    trigger_pulse(*, duration)

Unlike the step pulse above, nothing persists past the pulse. It carries no amplitude: it is
played on a digital output channel, which the target's hardware configuration -- not this model --
identifies as digital. Pair it with ``wait_for_trigger()`` (see "Wait for Trigger" above) on the
receiving end.

Example:

.. code-block:: python

    from eq1_pulse.builder import *

    # Tell external instrumentation to start.
    pulse = trigger_pulse(duration="100ns")

Measurements
------------

Basic Measurement
~~~~~~~~~~~~~~~~~

The ``measure()`` function performs a measurement operation (simultaneous play + record):

.. code-block:: python

    measure(
        channel,
        *,
        result_var,
        duration,
        amplitude,
        integration
    )

The ``integration`` parameter must be created using ``full_integration()`` or ``demod_integration()``.

Example:

.. code-block:: python

    var_decl("result", "complex", unit="mV")

    # Full integration
    measure(
        "readout",
        result_var="result",
        duration="1us",
        amplitude="30mV",
        integration=full_integration(),
    )

    # Demodulation integration with phase
    measure(
        "readout",
        result_var="result",
        duration="1us",
        amplitude="30mV",
        integration=demod_integration(phase="0deg"),
    )

Discriminate
~~~~~~~~~~~~

Discriminates a measurement result to a binary outcome:

.. code-block:: python

    discriminate(
        target,
        source,
        threshold,
        rotation=0,
        compare=">=",
        project="real"
    )

Example:

.. code-block:: python

    var_decl("raw", "complex", unit="mV")
    var_decl("state", "bool")

    # Measure
    measure(
        "readout",
        result_var="raw",
        duration="1us",
        amplitude="30mV",
        integration=demod_integration(phase="0deg"),
    )

    # Discriminate
    discriminate(
        target="state",
        source="raw",
        threshold="0.5mV",
        rotation="0deg"
    )

The ``state`` variable will be :obj:`True` if the measurement exceeds the threshold.

Trace Acquisition
~~~~~~~~~~~~~~~~~

``record()`` accumulates a whole acquisition window down to one scalar value. ``trace()`` is its
array-valued counterpart -- a repeated, continuous ``record()`` that keeps one entry per sample:

.. code-block:: python

    trace(channel, var, *, duration, integration=None, time_of_flight=None)

Because the result is array-valued, ``var`` must be declared with a ``shape`` sized to hold it
(``var_decl(name, dtype, shape=(n_samples,))``, see `Declaring Variables`_ below), rather than the
plain scalar declaration ``record()`` uses.

With no ``integration`` (the default), every sample is kept as-is -- the **raw ADC trace**. This is
the mode used to inspect the unprocessed readout signal, most commonly to calibrate
``time_of_flight`` (the delay between playing a readout pulse and the reflected signal arriving
back at the ADC): capture a raw trace once, read the delay to the first real signal off of it, and
pass that duration as ``time_of_flight`` to subsequent ``record()``/``trace()`` calls. It is also
useful for other debug measurements where the demodulation reference is not yet known.

Passing ``full_integration()`` or ``demod_integration()`` applies that integration per-sample
instead, same as ``record()`` would over each sample individually.

Example:

.. code-block:: python

    # Raw ADC trace, e.g. to calibrate time_of_flight
    var_decl("raw_trace", "complex", shape=(1000,), unit="mV")
    with build_sequence():
        trace("readout", "raw_trace", duration="1us")

    # Once time_of_flight is known, apply it (and per-sample demod) on later acquisitions
    var_decl("iq_trace", "complex", shape=(1000,), unit="mV")
    with build_sequence():
        trace(
            "readout",
            "iq_trace",
            duration="1us",
            integration=demod_integration(),
            time_of_flight="148ns",
        )

Variables
---------

Declaring Variables
~~~~~~~~~~~~~~~~~~~

Use ``var_decl()`` to declare a variable before using it:

.. code-block:: python

    var_decl(name, dtype, *, shape=None, unit=None)

Data types (``dtype``) can be:

* ``"bool"`` - boolean value
* ``"int"`` - integer
* ``"float"`` - floating point number
* ``"complex"`` - complex number

Example:

.. code-block:: python

    var_decl("result", "complex", unit="mV")
    var_decl("state", "bool")
    var_decl("amplitude", "float", unit="mV")
    var_decl("iq_data", "complex", shape=(100,))  # Array variable

Using Variables
~~~~~~~~~~~~~~~

Reference variables with ``var()``:

.. code-block:: python

    var(name)

Example:

.. code-block:: python

    # Use in conditional
    with if_("state"):
        play("qubit", pulse)

    # Use in pulse parameters
    play("qubit", square_pulse(duration="100ns", amplitude=var("amp")))

Assigning Values
~~~~~~~~~~~~~~~~

``for_``'s loop variable, ``record()``'s ``var`` and ``discriminate()``'s ``target`` each write a
variable as a side effect of doing something else. Use ``assign()`` to write one directly -- to
initialize it, or to store the result of a computation:

.. code-block:: python

    assign(target, value)

Example:

.. code-block:: python

    var_decl("count", "int")
    assign("count", 0)

    var_decl("doubled", "int")
    assign("doubled", expr(var("count")) * 2)

Late-bound values
-----------------

A variable's value is computed *inside* the program (e.g. by a loop or a discrimination). Two
further kinds of value are resolved *outside* it, at submission time, so the same serialized
program can be resubmitted as those values change without rebuilding the IR:

* A **parameter** (:func:`~eq1_pulse.builder.param_decl`) is supplied by the caller when the
  program is submitted -- a shot count, a sweep range endpoint. It is declared with
  ``param_decl()`` and referenced with the ordinary ``var()``, since a parameter shares the
  variable namespace and is otherwise an ordinary variable.
* An **external constant** (:func:`~eq1_pulse.builder.extern_decl`) is looked up by name in a
  calibration store when the program is submitted -- a qubit's drive frequency, a readout
  threshold. It is declared with ``extern_decl()`` and referenced with :func:`~eq1_pulse.builder.ext`,
  never with ``var()``. Names follow ``identifier[index].attribute``, e.g. ``"q0.f01"``,
  ``"q0[1].amp"``, ``"readout.threshold"`` -- only the leading identifier is mandatory.

Both declarations accept an optional ``unit``, an optional ``default`` (used if no value is
supplied or resolved at submission time), and optional ``min=``/``max=``/``allowed=`` limits.
**eq1_pulse declares these but never enforces them** -- unit conversion and range checking are
the responsibility of whatever submits the program.

.. code-block:: python

    from eq1_pulse.builder import *

    with build_sequence():
        # Supplied at submission time, with a fallback.
        param_decl("n_shots", "int", default=1000, min=1, max=100_000)

        # Resolved from the calibration store at submission time.
        extern_decl("q0.f01", "float", unit="GHz")
        extern_decl("q0.pi_amp", "float", unit="mV")

        set_frequency("q0_drive", ext("q0.f01"))

        with repeat(var("n_shots")):
            play("q0_drive", square_pulse(duration="25ns", amplitude=ext("q0.pi_amp")))

See ``examples/calibrated_rabi.py`` for a full sequence built from both kinds of late-bound value.

Expressions
-----------

**Building computed values with expressions**

Expressions allow you to compute values dynamically within a sequence using Python operators.
Unlike plain values, expressions are recorded and executed at runtime, not evaluated by the
builder. They are particularly useful for:

* Combining variables and external constants (e.g., detuning relative to a calibrated frequency)
* Scaling amplitude or duration based on a parameter
* Encoding conditional logic in predicates

**Why ``expr()`` is required**

The builder reads authoring forms like ``"10us"`` and ``"80mV"`` in function parameters and
resolves them to canonical unit objects before constructing models. Expressions work differently:
operators like ``+``, ``*``, and ``<`` are not available on plain values or references because
they would be evaluated immediately by Python.

Use ``expr()`` to wrap values into an ``Expr`` wrapper, which overloads operators to build an
expression tree:

.. code-block:: python

    from eq1_pulse.builder import *
    from eq1_pulse.models import Amplitude

    var_decl("scale", "float", unit="mV")
    param_decl("detuning", "float", unit="MHz")
    extern_decl("q0.f01", "float", unit="GHz")

    # Use expr() to build expressions
    scaled_amplitude = expr(var("scale")) * Amplitude("80mV")
    detuned_frequency = expr(ext("q0.f01")) + expr(var("detuning"))

    # Use expressions in operations
    play("drive", square_pulse(duration="25ns", amplitude=scaled_amplitude))
    set_frequency("drive", detuned_frequency)

**Supported operators**

Arithmetic:

* ``+``, ``-``, ``*``, ``/``, ``%`` — standard arithmetic operations
* ``abs(expr)`` — absolute value via ``CallExpr(function="abs")``
* Reflected forms: ``2 * expr(var("a"))`` works as well as ``expr(var("a")) * 2``

Comparison:

* ``<``, ``<=``, ``>``, ``>=`` — produce predicates for use in conditionals
* ``.eq()``, ``.ne()`` — use these methods instead of ``==`` and ``!=``, which return
  boolean values (not expressions)

Logical:

* ``.and_()``, ``.or_()``, ``.not_()`` — logical operations; Python keywords ``and``, ``or``,
  ``not`` cannot be overloaded

Functions:

* ``abs(expr)`` — the one function with its own operator sugar, via Python's own ``abs()``
* ``call_expr_(function, *operands)`` — every
  :data:`~eq1_pulse.models.expressions.ExpressionFunction`, including ``abs``, is reachable
  through this one free function. A free function rather than an ``Expr`` method: a function
  call has no operand that reads naturally as "self" the way ``+``/``-``/... prefer their left
  one, so ``call_expr_("min", a, b, c)`` treats its operands symmetrically instead of forcing one
  of them into a receiver position for no benefit. Not a free ``min()``/``max()``, to avoid
  shadowing the Python builtins wherever the builder is imported with ``import *``.

.. code-block:: python

    from eq1_pulse.builder import call_expr_, var

    fastest = call_expr_("min", var("a"), var("b"), 0)
    scaled = call_expr_("sqrt", var("power")) * 2

``CallExpr`` validates the argument count against *function*'s arity -- ``"min"``/``"max"`` need
at least 2, every other function exactly 1 -- and raises a validation error if it doesn't match.

Example:

.. code-block:: python

    from eq1_pulse.builder import *
    from eq1_pulse.models import Amplitude

    with build_sequence() as seq:
        var_decl("amplitude", "float", unit="mV")
        var_decl("state", "bool")

        # Arithmetic expression
        pulse = square_pulse(
            duration="25ns",
            amplitude=expr(var("amplitude")) * Amplitude("1mV")
        )
        play("drive", pulse)

        # Comparison expression in conditional
        with if_(expr(var("amplitude")) > 50):
            # amplitude > 50 mV
            play("readout", square_pulse(duration="1us", amplitude="30mV"))

**What expressions do and don't do**

Expressions are **recorded, never evaluated** by eq1_pulse:

* No type or unit checking — an expression like ``ext("q0.f01") + var("state")`` (adding a
  frequency and a boolean) is syntactically valid and serializes normally
* No simplification — ``x + 0`` serializes as a full binary expression, not as ``x``
* No evaluation — the result of ``expr(var("a")) + 1`` is never computed by the builder

These are the responsibility of the backend that executes the program. The builder's job is to
record what the user wrote, in a form the backend can consume and evaluate as it chooses
(eagerly, lazily, symbolically, etc.).

**Authoring forms in expressions**

Like the rest of the builder, expressions read the same authoring forms for quantities. This
means you can write:

.. code-block:: python

    # String forms work in expressions
    set_frequency("drive", expr(var("f")) + expr("100MHz"))

    # Amplitude as a literal (enabled by the SymbolValue fix in task 1)
    play("drive", square_pulse(
        duration="25ns",
        amplitude=expr(var("scale")) * Amplitude("80mV")
    ))

However, bare strings and identifiers like ``"10us"`` and ``"my_var"`` are not wire forms and
are rejected by models if they escape the builder. They survive as builder conveniences only.
Expressions route them through the same ``_coerce.py`` grammar the builder does, so ``expr("10us")``
works, but a deserialized expression will not contain a string — it contains the resolved quantity.

See :doc:`/examples/expression_examples` for worked examples of every operator and function, the
full wire-format reference, and ``examples/expression_ramsey.py``, a complete Ramsey experiment
using expressions.

What an expression looks like on the wire
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

On the wire, each expression node carries exactly one key naming what it is, and that key's value
holds the node's data. For the five operator nodes (``unary_op``, ``binary_op``, ``compare_op``,
``not_op``, ``logical_op``), the key names the node's arity/result kind, and the operator symbol
itself is nested inside under ``op`` -- the same nesting the "Wire format" section above
introduces for expression operator nodes:

.. code-block:: json

    {
      "binary_op": {
        "op": "*",
        "lhs": {
          "symbol": {
            "var": "scale"
          }
        },
        "rhs": {
          "value": {
            "mV": 80
          }
        }
      }
    }

This is the wire form of ``expr(var("scale")) * Amplitude("80mV")``: a binary multiplication of a
symbol and a voltage literal. ``LiteralExpr`` and ``SymbolExpr`` stay flat (``{"value": ...}``,
``{"symbol": ...}``); ``CallExpr`` nests the same way as the operator nodes but under
``function``/``name`` instead of an ``op`` field, e.g. ``{"function": {"name": "sqrt", "args": [...]}}``.
No discriminator field is needed -- the presence of ``binary_op``, ``compare_op``, ``logical_op``,
``not_op``, ``unary_op``, ``symbol``, ``value``, or ``function`` is itself the discriminator.

Control Flow
------------

Repetition (repeat)
~~~~~~~~~~~~~~~~~~~

Execute a block a fixed number of times:

.. code-block:: python

    with repeat(count):
        # operations

Example:

.. code-block:: python

    with build_sequence() as seq:
        with repeat(100):
            play("qubit", square_pulse(duration="50ns", amplitude="50mV"))
            wait("qubit", duration="50ns")

Iteration (``for_``)
~~~~~~~~~~~~~~~~~~~~

Loop over a sequence of values:

.. code-block:: python

    with for_(variable_name, values):
        # operations

Values can be:

* Python ``range()`` objects
* Lists of numbers
* ``LinSpace`` objects for linear sweeps

Example:

.. code-block:: python

    from eq1_pulse.models.basic_types import LinSpace

    with build_sequence() as seq:
        var_decl("freq", "float", unit="MHz")

        # Frequency sweep
        sweep = LinSpace(start=4000.0, stop=6000.0, num=100)
        with for_("freq", sweep):
            set_frequency("qubit", var("freq"))
            play("qubit", pulse)
            measure(
                "readout",
                result_var="result",
                duration="1us",
                amplitude="30mV",
                integration=demod_integration(),
            )

Conditionals (``if_``)
~~~~~~~~~~~~~~~~~~~~~~

Execute operations based on a condition:

.. code-block:: python

    with if_(condition):
        # operations if True

    with if_(condition):
        # operations if True
    with else_():
        # operations if False

Example:

.. code-block:: python

    var_decl("raw", "complex", unit="mV")
    var_decl("state", "bool")

    measure(
        "readout",
        result_var="raw",
        duration="1us",
        amplitude="30mV",
        integration=demod_integration(),
    )

    discriminate(
        target="state",
        source="raw",
        threshold="0.5mV"
    )

    with if_("state"):
        # Qubit was in |1>, apply correction
        play("qubit", square_pulse(duration="100ns", amplitude="50mV"))
    with else_():
        # Qubit was in |0>, do nothing
        pass

Storing Results
---------------

The ``store()`` function saves measurement results:

.. code-block:: python

    store(key, source, *, mode="last")

Modes:

* ``"last"`` - store the last value (default)
* ``"average"`` - accumulate average
* ``"count"`` - count occurrences
* ``"trace"`` - store all values

Example:

.. code-block:: python

    var_decl("result", "complex", unit="mV")

    with for_("amp", range(0, 100, 5)):
        play("qubit", square_pulse(duration="100ns", amplitude=var("amp")))
        measure(
            "readout",
            result_var="result",
            duration="1us",
            amplitude="30mV",
            integration=full_integration(),
        )
        store("rabi_data", "result", mode="average")

Advanced Patterns
-----------------

Nested Subsequences
~~~~~~~~~~~~~~~~~~~

Create reusable subsequences:

.. code-block:: python

    with build_sequence() as x_gate:
        play("qubit", square_pulse(duration="100ns", amplitude="50mV"))

    with build_sequence() as main_seq:
        # Use subsequence multiple times
        subsequence(x_gate)
        wait("qubit", duration="100ns")
        subsequence(x_gate)

Multi-Channel Synchronization
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Coordinate operations across channels:

.. code-block:: python

    with build_sequence() as seq:
        # Prepare both qubits
        play("qubit1", prep_pulse)
        play("qubit2", prep_pulse)

        # Ensure both are ready before entangling
        barrier("qubit1", "qubit2")

        # Two-qubit gate (simultaneous pulses)
        play("qubit1", entangling_pulse_q1)
        play("qubit2", entangling_pulse_q2)

        # Synchronize before measurement
        barrier("qubit1", "qubit2")

        # Simultaneous readout
        measure(
            "qubit1",
            result_var="result1",
            duration="1us",
            amplitude="30mV",
            integration=demod_integration(),
        )
        measure(
            "qubit2",
            result_var="result2",
            duration="1us",
            amplitude="30mV",
            integration=demod_integration(),
        )

Complete Example
----------------

Here's a complete Rabi oscillation experiment:

.. code-block:: python

    from eq1_pulse.builder import *
    from eq1_pulse.models.basic_types import LinSpace

    # Build amplitude Rabi sequence
    with build_sequence() as rabi_seq:
        # Declare variables
        var_decl("amp", "float", unit="mV")
        var_decl("raw", "complex", unit="mV")
        var_decl("state", "bool")

        # Sweep amplitude from 0 to 100 mV
        amplitude_sweep = LinSpace(start=0.0, stop=100.0, num=50)

        with for_("amp", amplitude_sweep):
            # Apply variable-amplitude pulse
            play("qubit", square_pulse(duration="100ns", amplitude=var("amp")))

            # Measure
            measure(
                "readout",
                result_var="raw",
                duration="1us",
                amplitude="30mV",
                integration=demod_integration(),
            )

            # Discriminate
            discriminate(
                target="state",
                source="raw",
                threshold="0.5mV"
            )

            # Store result
            store("rabi_amplitude", "state", mode="average")

            # Wait for qubit to relax
            wait("qubit", duration="10us")

    # Export to JSON
    print(rabi_seq.model_dump_json(indent=2))

This creates a complete experiment that sweeps the drive amplitude and measures the excited state population at each amplitude value.

JSON Output
~~~~~~~~~~~

.. code-block:: json

    [
      {
        "var_decl": {
          "dtype": "float",
          "unit": "mV",
          "name": "amp"
        }
      },
      {
        "var_decl": {
          "dtype": "complex",
          "unit": "mV",
          "name": "raw"
        }
      },
      {
        "var_decl": {
          "dtype": "bool",
          "name": "state"
        }
      },
      {
        "for": {
          "var": "amp",
          "items": {
            "start": 0.0,
            "stop": 100.0,
            "num": 50
          },
          "body": [
            {
              "play": {
                "channel": "qubit",
                "pulse": {
                  "pulse_type": "square",
                  "duration": {
                    "ns": 100
                  },
                  "amplitude": {
                    "var": "amp"
                  }
                }
              }
            },
            {
              "play": {
                "channel": "readout",
                "pulse": {
                  "pulse_type": "square",
                  "duration": {
                    "us": 1
                  },
                  "amplitude": {
                    "mV": 30
                  }
                }
              }
            },
            {
              "record": {
                "channel": "readout",
                "var": "raw",
                "duration": {
                  "us": 1
                },
                "integration": {
                  "integration_type": "demod"
                }
              }
            },
            {
              "discriminate": {
                "target": "state",
                "source": "raw",
                "threshold": {
                  "mV": 0.5
                }
              }
            },
            {
              "store": {
                "key": "rabi_amplitude",
                "source": "state",
                "mode": "average"
              }
            },
            {
              "wait": {
                "channels": [
                  "qubit"
                ],
                "duration": {
                  "us": 10
                }
              }
            }
          ]
        }
      }
    ]

The JSON structure shows:

1. **Variable declarations** (lines 2-14): Three variables for amplitude sweep, raw measurement, and discriminated state
2. **For loop** (lines 15-93): Sweeps amplitude from 0 to 100 mV in 50 steps
3. **Loop body** contains:

   - **Play operation** (lines 19-29): Variable-amplitude square pulse on qubit channel
   - **Measurement** (lines 30-50): Readout pulse and recording with integration
   - **Discrimination** (lines 51-57): Threshold comparison to classify qubit state
   - **Data storage** (lines 58-63): Store averaged results
   - **Wait operation** (lines 64-70): Allow qubit to relax between measurements

This JSON can be exported to control hardware or used for simulation and analysis.

Pulse Sequence Visualization
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The diagram below shows how the JSON structure translates into a concrete pulse sequence timeline:

.. plot::
   :align: center
   :caption: Pulse sequence timing diagram showing three iterations.

   from pulse_sequence_diagram import create_pulse_sequence_diagram
   create_pulse_sequence_diagram()

The visualization shows three iterations of the 50-iteration loop, displaying the temporal structure:

- **Drive pulses** (purple): Applied on the qubit channel with increasing amplitude (25 mV, 50 mV, 75 mV shown). Pulse duration is 100 ns.
- **Readout pulses** (orange): Applied on the readout channel immediately after each drive pulse. Fixed at 30 mV amplitude and 1 μs duration.
- **Wait periods** (gray dashed): 10 μs relaxation time on both channels to allow the qubit to return to ground state before the next iteration.

Each iteration follows the same temporal pattern: drive → readout → wait. The amplitude sweep from 0 to 100 mV across all 50 iterations enables calibration of the π pulse amplitude for this qubit.

Creating Reusable Building Blocks
----------------------------------

For complex pulse programs, you'll often want to create reusable, modular building blocks that encapsulate common operations. The builder provides the ``@nested_sequence`` decorator for this purpose.

The ``@nested_sequence`` Decorator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use ``@nested_sequence`` to create reusable operation blocks in sequence contexts. Functions decorated with ``@nested_sequence`` automatically create a :func:`sub_sequence` when called.

**Basic Usage:**

.. code-block:: python

    from eq1_pulse.builder import *

    @nested_sequence
    def hadamard_gate(qubit: str):
        """Apply a Hadamard gate."""
        play(qubit, square_pulse(duration="20ns", amplitude="100mV"))
        shift_phase(qubit, "90deg")
        play(qubit, square_pulse(duration="20ns", amplitude="100mV"))
        shift_phase(qubit, "-90deg")

    @nested_sequence
    def x_gate(qubit: str):
        """Apply an X gate."""
        play(qubit, square_pulse(duration="20ns", amplitude="150mV"))

    @nested_sequence
    def readout_sequence(drive_ch: str, readout_ch: str, result_var: str):
        """Perform readout measurement."""
        play(drive_ch, square_pulse(duration="1us", amplitude="50mV"))
        record(readout_ch, result_var, duration="1us", integration=full_integration())

    # Use the building blocks in a sequence
    with build_sequence() as seq:
        var_decl("readout", "complex", unit="mV")

        hadamard_gate("qubit0")
        x_gate("qubit0")
        hadamard_gate("qubit0")

        readout_sequence("drive0", "readout0", "readout")

**Key Points:**

- The decorated function is called normally with its parameters
- It automatically creates a ``sub_sequence`` in the current context
- The function returns :obj:`None` (operations are added to the context)
- Can only be used in sequence contexts (raises error otherwise)
- Decorated functions can call other ``@nested_sequence`` decorated functions

**Visual Explanation:**

The diagram below illustrates how ``@nested_sequence`` eliminates manual context management:

.. plot::
   :align: center
   :caption: @nested_sequence decorator usage comparison.

   from nested_sequence_diagram import create_nested_sequence_diagram
   create_nested_sequence_diagram()

Without the decorator, you must manually create ``sub_sequence()`` contexts. With ``@nested_sequence``, simply calling the function automatically creates the sub-sequence, making code cleaner and more reusable.

**Composing Building Blocks:**

You can compose building blocks together:

.. code-block:: python

    @nested_sequence
    def bell_state_prep(qubit1: str, qubit2: str):
        """Prepare a Bell state between two qubits."""
        hadamard_gate(qubit1)  # Call another decorated function
        # Simplified CNOT implementation
        play(qubit1, square_pulse(duration="30ns", amplitude="120mV"))
        play(qubit2, square_pulse(duration="30ns", amplitude="120mV"))

    with build_sequence() as seq:
        bell_state_prep("qubit0", "qubit1")
        # Multiple readouts
        var_decl("result0", "complex", unit="mV")
        var_decl("result1", "complex", unit="mV")
        readout_sequence("drive0", "readout0", "result0")
        readout_sequence("drive1", "readout1", "result1")

.. note::

    A ``@nested_schedule`` decorator also exists for the unused, experimental schedule builder
    (:mod:`eq1_pulse.builder.experimental`), together with a side-by-side comparison against
    ``@nested_sequence`` -- see :doc:`/experimental/schedule`.

Best Practices
~~~~~~~~~~~~~~

1. **Descriptive names**: Use clear function names that describe the operation:

   .. code-block:: python

       @nested_sequence
       def pi_pulse(qubit: str):  # Good
           """Apply a π pulse."""
           ...

       @nested_sequence
       def do_stuff(ch: str):  # Avoid
           ...

2. **Add docstrings**: Document what your building blocks do:

   .. code-block:: python

       @nested_sequence
       def ramsey_sequence(qubit: str, delay: str):
           """Ramsey sequence with variable delay.

           Applies π/2 - delay - π/2 sequence for T2* measurement.

           :param qubit: Target qubit channel
           :param delay: Free evolution time between π/2 pulses
           """
           ...

3. **Use type hints**: Help users understand parameter types:

   .. code-block:: python

       @nested_sequence
       def readout_sequence(
           drive_ch: str,
           readout_ch: str,
           result_var: str
       ) -> None:
           ...

4. **Parameterize building blocks**: Make them flexible and reusable:

   .. code-block:: python

       @nested_sequence
       def variable_amplitude_pulse(
           channel: str,
           duration: str,
           amplitude: str,
           shape: str = "square"
       ):
           """Pulse with configurable parameters."""
           if shape == "square":
               play(channel, square_pulse(duration=duration, amplitude=amplitude))
           elif shape == "sine":
               play(channel, sine_pulse(
                   duration=duration,
                   amplitude=amplitude,
                   frequency="5GHz"
               ))

Complete Example
~~~~~~~~~~~~~~~~

Here's a complete example combining both decorators for a multi-qubit experiment:

.. code-block:: python

    from eq1_pulse.builder import *

    # ========== Gate library (sequences) ==========

    @nested_sequence
    def x90_gate(qubit: str):
        """π/2 rotation around X axis."""
        play(qubit, square_pulse(duration="10ns", amplitude="100mV"))

    @nested_sequence
    def x_gate(qubit: str):
        """π rotation around X axis."""
        play(qubit, square_pulse(duration="20ns", amplitude="100mV"))

    @nested_sequence
    def y_gate(qubit: str):
        """π rotation around Y axis."""
        shift_phase(qubit, "90deg")
        play(qubit, square_pulse(duration="20ns", amplitude="100mV"))
        shift_phase(qubit, "-90deg")

    # ========== Readout ==========

    def dispersive_readout(drive: str, readout: str, result: str):
        """Standard dispersive readout."""
        play(drive, square_pulse(duration="2us", amplitude="40mV"))
        record(readout, result, duration="2us", integration=full_integration())

    # ========== Use in sequence context ==========

    with build_sequence() as seq:
        var_decl("state", "complex", unit="mV")

        # Build up gates using sequence blocks
        x90_gate("q0")
        x_gate("q0")
        y_gate("q0")
        x90_gate("q0")

        # Readout
        dispersive_readout("drive0", "readout0", "state")

This example demonstrates:

- Simple gate operations as ``@nested_sequence`` blocks
- Reusing plain building-block functions alongside decorated ones
- Composing a complete experiment from small, named pieces
