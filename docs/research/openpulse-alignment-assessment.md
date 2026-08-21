# eq1_pulse vs. OpenPulse / OpenQASM 3 — alignment assessment

**Date:** 2026-08-20
**Branch context:** `hp-peti/builder-interface`
**Question asked:** how well do the builder API and the representation (models) API align with
OpenPulse and the relevant parts of OpenQASM 3, and can the `Schedule` representation be pushed
into the background or eliminated entirely?

Raw research dumps backing every claim here are in [`raw/`](raw/). See [README.md](README.md)
for the index.

---

## 0. Decisions taken since this assessment was written

The findings below stand, but the project has since fixed several parameters that change how
they should be read. The resulting work is
[PR #7](https://github.com/equal1/eq1_pulse/pull/7); remaining follow-on work is tracked in
[#8](https://github.com/equal1/eq1_pulse/issues/8).

| Decision                                                              | Effect on this document                                                                                |
| --------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| **Direction is to *consume* OpenPulse, not produce it.**              | Constructs with no OpenPulse counterpart (`Store`, `CompensateDC`, `Record.time_of_flight`, physical amplitude units) are fine as supersets — see §3.4 and §3.6, now non-blocking. What matters is that we can *represent everything OpenPulse can say*. |
| **`Schedule` is isolated, not deleted.**                              | Moves to an experimental module, dropped from the public `models`/`builder` namespaces, warned on, retagged `experimental` in the generated schema, moved to a separate docs page. §6's staged migration is superseded by the plan. |
| **Schedule and sequence models must not mix.**                        | Enforced by import-direction and mixing-rejection tests, not by convention.                            |
| **A `Channel` is a `(port, clock)` pair carrying its own frame implicitly; all clocks are NCOs on one global clock.** | Resolves §3.3 — see the assumptions block added there. The frame gaps are answered by declaring more channels; a channel-mapping representation is future work. |
| **A timed/flex opaque `ExternalBlock` is added to the sequence model.** | Partially closes the `box` gap in §3.1 and §5, in the form needed for consumption. Carries a `FullyQualifiedIdentifier` program reference, role-keyed channels it reserves, input `params`, and output `results`. The parameter-passing design is eq1_pulse-specific — OpenQASM's `box` takes no arguments (only `defcal` does), so this is a deliberate superset. |

The single most consequential re-read: **because we consume rather than produce, the absence of
`box` in eq1_pulse changes from an ergonomics gap into a blocking one.** A `Schedule` cannot
consume an OpenPulse program at all; `OpSequence` can already consume `play`/`capture`/`delay`/
`barrier`, and `box` is the first construct it cannot represent.

---

## 1. Verdict

**Yes — eliminate `Schedule` as an authoring format. Keep it, at most, as a compiled output.**

The reasoning is not a matter of taste:

1. **OpenPulse has no absolute-time and no reference-point representation at all.** The OpenQASM 3
   paper is explicit: *"Within a program, there is no explicit reference to a global clock, but
   instead, only relative references to the starting time of a `defcal`/`cal` or the current
   relative time of other frames through the `barrier` instruction."* All OpenPulse timing is a
   per-frame time cursor advanced by `play`, `capture`, `delay`, and joined by `barrier`.

2. **`eq1_pulse.models.OpSequence` is already that model.** Implicit per-channel earliest-start
   sequencing, with `Wait` and `Barrier`, is structurally the same thing as OpenPulse's per-frame
   cursor with `delay` and `barrier`. The sequence half of the IR is the aligned half.

3. **`eq1_pulse.models.Schedule` is a verbatim reimplementation of quantify-scheduler's timing
   model** — `rel_time`, `ref_op`, `ref_pt`, `ref_pt_new`, with reference points
   `start`/`center`/`end`. Quantify is the *only* framework in the surveyed set that still uses
   this as an authoring representation. Every other live pulse framework — OpenPulse itself, AWS
   Braket Pulse, QUA, Pulser, Qibolab, oqpy — uses per-resource cursors; Qiskit `ScheduleBlock`
   and Zurich LabOne Q use nested alignment sections. Nobody else is where `Schedule` is.

4. **The industry precedent is exactly this migration.** Qiskit introduced `ScheduleBlock` (relative,
   alignment-context based) in Terra 0.17 / Qiskit 0.25 (April 2021) precisely to stop forcing
   absolute `t0` at construction time, kept the absolute `Schedule` as the *lowered* form produced
   by `block_to_schedule()`, and pointed the builder at the block representation. That is the
   template to copy.

5. **The cost is bounded and known.** Any *feasible, statically resolvable* reference-point schedule
   can be lowered to per-channel `delay` + `barrier` inside nested blocks. What is genuinely lost
   is not expressivity of the finished schedule, but the ability to construct one *online* with
   backward references — and eq1_pulse's builder already buffers a whole context before returning
   a model, so a block-local solver is feasible.

**But**: the sequence side is not automatically OpenPulse-conformant either. Section 3 lists the
remaining divergences. The one that actually blocks consumption is the absence of `box`; the rest
are documentation, additive supersets, or deferred to the channel-mapping work.

---

## 2. What OpenQASM 3 / OpenPulse actually offers for timing

The complete portable timing vocabulary is small:

| Construct                                     | Meaning                                                                                                  |
| --------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| implicit program order                        | An operation may not start before its resource and data predecessors finish. Absent explicit timing the compiler may still commute/reschedule. |
| `delay[d] q;` / `delay[d] frame;`             | Explicit, *timed identity*. Occupies the resource, and **prevents commutation** that would otherwise be legal. |
| `delay[d] q0, q1;` (multi-resource)           | **A synchronisation point.** Begins at `max(cursor(q0), cursor(q1))` and ends simultaneously on both.     |
| `barrier q0, q1;`                             | Zero nominal duration; sets all listed cursors to their maximum. Ordering constraint without committing to a duration. |
| `box { ... }` / `box[500ns] { ... }`          | Timing/optimisation scope. Operations may not move into or out of it. Optional bracketed designator is a **hard total-duration constraint**. |
| `stretch s;`                                  | Subtype of `duration`. Non-negative symbolic slack, minimised by the compiler subject to constraints, resolved at compile time by a lexicographic LP. |
| `durationof({ ... })`                         | Compile-time duration of a statically analysable scope.                                                  |
| frame ops (`set_phase`/`shift_phase`/`set_frequency`/`shift_frequency`) | Instantaneous at the frame's current time; do **not** advance the cursor. |

And, equally important, what it **does not** offer:

- No `align_left` / `align_right` / `align_center` keyword.
- No reference-point / anchor operand — nothing like `ref_op=X, ref_pt="center"`.
- No absolute start timestamp; no `play B at 250ns`.
- No `startof(label)` expression. `durationof` asks for a *duration*, not a *time*.
- `boxas` / `boxto` — **confirmed never to have existed** in 3.0, 3.1, or the reference ANTLR
  grammar. The only production is `boxStatement : BOX designator? scope;`. Treat those spellings
  as abandoned design-discussion terminology, not deprecated syntax.
- No standard `repeat N` statement — you write `for int i in [0:n-1] { ... }` with an unused index.
- No physical-unit system beyond `duration` (ns/µs/us/ms/s/dt) and `angle`. No volts, no MHz, no dBm.
- No result-stream / shot-accumulation concept whatsoever.

Alignment is therefore expressed as *timing equations* built from `box`, `delay`, `barrier`,
`stretch`, and known/referential durations. Left alignment = put the stretch **after** the
operation. Right alignment (ALAP) = put it **before**. Fractional placement = relative stretch
coefficients (`delay[s]` … `delay[2*s]` puts the operation at the ⅓ point).

Centring two pulses on distinct frames, idiomatically:

```qasm
barrier fA, fB;
play(fA, A);
delay[(dA - dB) / 2] fB;
play(fB, B);
barrier fA, fB;
```

or target-independently with a stretch, where the solver derives `2s + dB = dA`:

```qasm
stretch s;
barrier fA, fB;
play(fA, A);
delay[s] fB; play(fB, B); delay[s] fB;
barrier fA, fB;
```

**Status caveat:** the OpenPulse chapter still carries the banner *"The OpenPulse grammar is still
in active development and is liable to change."* `stretch` is normative in 3.1 but only
experimentally supported in Qiskit Runtime (at most one stretch variable per mutually exclusive
qubit set per barrier region; expressions limited to `X*stretch + Y`).

---

## 3. Gap analysis: eq1_pulse today

### 3.1 Timing and scheduling

| eq1_pulse construct                             | OpenQASM 3 / OpenPulse counterpart          | Status                                                                                       |
| ----------------------------------------------- | ------------------------------------------- | -------------------------------------------------------------------------------------------- |
| `OpSequence` (implicit ASAP per channel)        | implicit program order + per-frame cursor   | **Aligned.** This is the right base model.                                                   |
| `Barrier(*channels)`                            | `barrier f0, f1;`                           | **Aligned.** Both mean "set all listed cursors to their maximum."                            |
| `Wait(*channels, duration=...)`                 | `delay[d] f0;` (one per channel)            | **Aligned.** Multi-resource `delay[d] f0, f1;` == `barrier` + `Wait`; see 3.2.               |
| `Schedule` / `ScheduledOperation`               | —                                           | **No counterpart.** Must be solved and erased before emission.                               |
| `RefPt` (start/center/end), `RelTime`, `ref_op` | —                                           | **No counterpart.**                                                                          |
| `SchedRepetition` / `SchedIteration` / `SchedConditional` | —                                  | **No counterpart.** Duplicated control flow exists only to serve `Schedule`.                 |
| —                                               | `box` / `box[duration]`                     | **Missing from eq1_pulse.** No timing scope, no hard-duration region.                        |
| —                                               | `stretch`                                   | **Missing.** No symbolic slack, so DD/echo spacing must be computed by hand.                 |
| —                                               | `durationof({...})`                         | **Missing.** No way to refer to a calibrated block's duration.                               |
| —                                               | alignment policies (left/right/equispaced)  | **Missing.** `Schedule` is the current substitute, and it is the wrong substitute.           |

### 3.2 `Wait` vs `delay`: different granularity, clean mapping both ways

[`sequence.py`](../../src/eq1_pulse/models/sequence.py) and
[`channel_ops.py:Wait`](../../src/eq1_pulse/models/channel_ops.py) document:

> *"The wait operations are scheduled to start as soon as possible on each channel. The relative
> timing between channels is not guaranteed."*

OpenQASM 3 says of the corresponding construct:

> *"A multi-qubit `delay` instruction is **not** equivalent to multiple single-qubit `delay`
> instructions. Instead a multi-qubit delay acts as a synchronization point on the qubits, where
> the delay begins from the latest non-idle time across all qubits, and ends simultaneously across
> all qubits."*

These differ, but **not in a way that loses anything.** eq1_pulse's `Wait` is the *more primitive*
operation; OpenQASM's multi-resource `delay` conflates a barrier with a delay. The composite
decomposes exactly:

```text
delay[d] a, b;            ≡   barrier(a, b) ; wait(a, b, d)
```

because after the barrier `cursor(a) == cursor(b) == max(...)`, so an independent per-channel wait
lands both ends at `max(...) + d` — precisely the OpenQASM semantics. And in the other direction:

```text
wait(a, b, d)             ⇒   delay[d] a;  delay[d] b;      (two single-resource delays)
```

Each single-resource delay advances only its own cursor, which is exactly the independent
semantics.

So the import rule is `delay[d] a, b;` → `barrier(a, b); wait(a, b, d)`, and the export rule is
one `delay` statement per channel. **No model or behaviour change is needed.** What is needed is
a docstring note recording both rules, so the difference in granularity is not rediscovered as a
bug later.

There is a separate, related note: OpenQASM 3 distinguishes an **explicit** `delay` (which blocks
commutation) from **implicit** idle time (which does not). eq1_pulse has no way to express that
distinction, because idle time is never explicit. Adding `box` gives it one.

### 3.3 Resources: flat `ChannelRef` vs `port` + `frame`

> **Resolved — the eq1_pulse channel model.** The following assumptions are now explicit project
> decisions, and they answer most of this section:
>
> 1. **A `Channel` *is* a `(port, clock)` combination.** It therefore carries its own frame
>    implicitly. This is the same decomposition quantify-scheduler uses, collapsed into one
>    identifier.
> 2. **Every clock is an NCO synchronised to a single global clock.** All channels are therefore
>    mutually phase-coherent, and phase relationships never need explicit modelling.
> 3. **Multiple channels may resolve onto one physical port.** The cases below —
>    frequency-multiplexed readout, independent `01`/`12` phase on a shared drive line — are
>    handled by *declaring separate channels*, not by adding a frame object to the IR.
> 4. **Virtual channels absorb baseband operation and gate-virtualisation mappings.** Primary use
>    case: capacitive-coupling compensation, where a logical channel fans out to several physical
>    outputs through a mixing matrix.
> 5. **The channel → (port, clock, virtual-channel mapping) representation is future work.** It
>    does not exist yet, which is why amplitude-unit conversion on import (§3.6) is currently
>    blocked.
>
> The analysis below is retained because it documents *what* that mapping representation will
> have to carry, and *why* the assumptions above are the ones that make a flat channel sound.

`ChannelRef` bundles physical I/O, carrier frequency, phase, and clock into a single name. That is
the old Qiskit Pulse `DriveChannel(0)` model. OpenPulse splits them: a `frame` has
`(port, frequency, phase, time)`, and **many frames may share one port**.

Concrete things a flat channel cannot express:

- **Frequency-multiplexed readout** — three resonator frames on one ADC port, each with its own
  carrier and its own capture timing. Inventing `q0_ro`, `q1_ro`, `q2_ro` channels hides the fact
  that they share hardware.
- **Independent `01` / `12` phase tracking on a shared drive line** — `shift_phase(channel, θ)` has
  ambiguous scope: it either wrongly shifts both transitions, or you invent separate channels and
  lose the shared-line relation.
- **Frame persistence across `defcal` invocations** — a flat channel name does not identify a
  persistent mutable phase accumulator; re-creating it per export risks resetting phase.
- **Two carriers on one port that hardware must sum** — nothing distinguishes "two producers of one
  output" from "two conflicting users of one serialised resource."

The closest shipping analogue to an OpenPulse frame is quantify-scheduler's `(port, clock)` pair:
`port` is a string identifying *where* (`"q0:mw"`), `clock` is a string naming a `ClockResource(name, freq, phase)`
identifying *at what carrier* (`"q0.ge"`), with `ShiftClockPhase` / `ResetClockPhase` /
`SetClockFrequency` mutating clock state. AWS Braket models `Frame(frame_id, port, frequency, phase)`
and `Port(name, dt)` directly.

**Original recommendation** (superseded by the decision block above, retained for the reasoning):
a middle ground — keep the ergonomic single-target operation signature, but let the target be
`(port, optional clock/frame)` rather than one opaque name, with frames/clocks declared as
first-class resources carrying frequency, phase, and a persistence flag.

**Adopted instead:** keep the single opaque `ChannelRef` in the *program* IR, and push the
`(port, clock)` decomposition entirely into a separate channel-mapping representation. This is
defensible precisely because of assumption 2 above — with all clocks phase-coherent on one global
NCO reference, the frame state that OpenPulse tracks per-frame is recoverable from the channel
identity plus the mapping. The cost is that the program IR alone does not tell you which channels
share hardware; the mapping is required for any collision analysis. **That mapping must exist
before the JSON schema is treated as stable**, because amplitude-unit conversion (§3.6), port
collision detection, and virtual-channel fan-out all depend on it.

### 3.4 Operation-by-operation mapping

| eq1_pulse                                   | OpenPulse                                                     | Status                                                                                |
| ------------------------------------------- | ------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| `Play(channel, pulse)`                      | `play(frame, waveform)`                                       | **Aligned.**                                                                          |
| `Play.scale_amp`                            | `scale(wf, k)`                                                | **Aligned** for real scalar `k`. Complex → `scale(phase_shift(wf, θ), r)`.            |
| `Play.cond`                                 | `if (b) { play(...); }`                                       | **Partial.** Legal only where both branches have equal, statically known duration — so a conditional play needs a compensating `else { delay[...]; }`. |
| `Record(..., integration=full)`             | `capture_v1(frame, filter) -> complex[float[32]]`             | **Partial.** No standard `full`/`demod` keyword; the kernel waveform is the mechanism. |
| `Record(..., integration=demod)`            | `capture_v1(frame, kernel)`                                   | **Partial.** The spec does *not* say capture auto-demodulates from the frame's own frequency/phase; that is vendor-defined. |
| `Record.time_of_flight`                     | —                                                             | **No counterpart.** Must lower to an explicit `delay` on the capture frame or vendor config. |
| `Trace(channel, array_var, duration)`       | `capture_v3(frame, len) -> waveform`                          | **Aligned** (closest direct match).                                                   |
| `Wait`                                      | `delay[d]` (one statement per channel)                        | **Aligned.** Multi-resource `delay` == `barrier` + `Wait`; see 3.2.                   |
| `Barrier`                                   | `barrier`                                                     | **Aligned.**                                                                          |
| `SetFrequency` / `ShiftFrequency`           | `set_frequency` / `shift_frequency`                           | **Aligned** (frame-scoped, not channel-scoped).                                       |
| `SetPhase` / `ShiftPhase`                   | `set_phase` / `shift_phase`                                   | **Aligned** (frame-scoped).                                                           |
| `Discriminate`                              | `extern discriminate(complex[float[64]]) -> bit`, or `capture_v2` | **Partial.** `threshold`, `rotation`, `project` are **not** in the language — vendor config. |
| `Store(key, source, mode)`                  | —                                                             | **No counterpart at all.** OpenQASM 3 has no result-stream, shot index, named result key, or accumulation mode. Closest analogues are QUA `declare_stream`/`save`/`stream_processing` and Qblox/quantify `BinMode` (`APPEND`/`AVERAGE`/`SUM`/`DISTRIBUTION`). This belongs to the job/experiment layer. |
| `CompensateDC`                              | —                                                             | **No counterpart.** Automatic net-zero compensation is necessarily a vendor extension (cf. Qblox `create_dc_compensation_pulse` / `PulseCompensation`, QM `set_dc_offset`, ZI precompensation filters). Portable fallback: compute the waveform and emit a plain `play`. |
| `VariableDecl` / `PulseDecl`                | classical declarations / `waveform` in `cal`                  | **Partial** — see 3.6.                                                                |

### 3.5 Pulse types

| eq1_pulse                          | OpenPulse                                                    | Status                                                                                 |
| ---------------------------------- | ------------------------------------------------------------ | ---------------------------------------------------------------------------------------- |
| `ArbitrarySampledPulse`            | `waveform wf = [complex samples];`                           | **Aligned.** Direct semantic match.                                                    |
| `ExternalPulse(function, params)`  | `extern name(...) -> waveform`                               | **Right model, but not automatically portable.** An `extern` declaration states what is *expected*; portability requires the target to agree on symbol name, parameter order, types, units, duration/sample-rate rules, and clipping behaviour. Treat it as a *target capability requirement*. |
| `SquarePulse` (no ramps)           | `constant(amp, d)`                                           | **Aligned.**                                                                           |
| `SquarePulse` with `rise_time`/`fall_time` | —                                                    | **No standard template.** `gaussian_square` is flat-top with *Gaussian* edges. Linear-ramp flat-top must lower to explicit samples or a vendor `extern`. |
| `SinePulse` (fixed frequency)      | `sine(amp, d, frequency, phase)`                             | **Aligned.**                                                                           |
| `SinePulse.to_frequency` (chirp)   | —                                                            | **No standard template.** Standard `sine` takes a single scalar frequency. A linear chirp needs explicit samples or a vendor `extern chirp(...)`. |

The eq1_pulse union is well-chosen for a *source* IR, but two of its four shapes (ramped square,
chirped sine) have no portable OpenPulse realisation and will need an explicit lowering policy:
sample them, or require a named target extern.

### 3.6 Units, amplitudes, and classical types

- **Durations:** eq1_pulse `Duration` with ns/us/ms/s maps cleanly onto OpenQASM `duration`. `dt`
  (one backend sample period) has no eq1_pulse equivalent and should be added — it is the only unit
  in which exact sample realisation is expressible.
- **Amplitudes:** this is a real mismatch. eq1_pulse `Amplitude`/`Magnitude` carry **physical units**
  (`"100mV"`). OpenPulse amplitudes are **dimensionless complex envelope values**; there is no `V`,
  `mV`, `dBm`, or `W` in the language, and the conventions differ per vendor (old Qiskit Pulse
  required max unit norm; Braket documents amplitude `0.1` as "arbitrary units"). Lowering volts to
  OpenPulse requires a target calibration profile (full-scale voltage, port gain, attenuation,
  impedance convention, max sample magnitude, frequency-dependent gain). eq1_pulse's physical units
  are arguably *better* for an authoring IR — but the conversion must be explicit and the program
  must be rejected when no target profile exists.
- **Phase:** `Phase` (deg/rad/turns) → `angle[n]`. Aligned. Note quantify uses degrees, OpenPulse
  uses `angle` modulo 2π.
- **`VariableDecl.dtype`** (`bool`/`int`/`float`/`complex`) maps to `bool`, `int[n]`/`uint[n]`,
  `float[n]`, `complex[float[n]]`. Caveats: the spec explicitly warns hardware may not support
  runtime manipulation of `complex`; `float` real-time support is implementation-dependent.
- **`VariableDecl.shape`** → `array[base, dims...]`, but: `bit`, `bit[n]`, and `stretch` are not
  valid array base types, arrays cannot be resized, at most 7 dimensions, **and arrays must be
  declared at global program scope** — not inside a function or gate body. An IR that allows array
  declarations in nested scopes must hoist or unroll them.
- **`VariableDecl.unit`** (e.g. `"MHz"`) has **no OpenQASM 3 counterpart**. There is no
  physical-unit system beyond `duration` and `angle`. It survives only as IR metadata or a
  target-profile convention.

Recommendation: annotate each variable with an execution class —
`compile_time` / `controller_runtime` / `measurement_feedback_runtime` / `pulse_parameter_runtime` —
rather than assuming a syntactically valid declaration is executable.

### 3.7 Control flow

| eq1_pulse       | OpenQASM 3                                    | Status                                                              |
| --------------- | --------------------------------------------- | --------------------------------------------------------------------- |
| `Repetition`    | `for int i in [0:count-1] { ... }`            | **Aligned by lowering.** OpenQASM 3 has **no `repeat` statement**; the index is simply unused. Handle `count == 0` explicitly. |
| `Iteration`     | `for int i in [a:s:b]`, `for float f in {…}`  | **Aligned by lowering.** But whether a real-valued sweep is unrolled at compile time or executed on the controller is *not* determined by the syntax — annotate intent. |
| `Conditional`   | `if (var) { ... }`                            | **Aligned**, with the `defcal` equal-duration-branch rule.          |
| —               | `while`, `switch`, `else`                     | Missing from eq1_pulse; probably fine to omit for now.              |
| —               | `box`                                         | Missing, and this one matters — see §5.                             |

Inside `cal`/`defcal`, every body must have a **compile-time-resolvable definite duration**;
branches must have equal duration; loops must have statically resolvable trip counts. A `while` on
a runtime condition is not a portable calibration body. eq1_pulse should be able to *check* this,
since it is the rule that makes `durationof` and stretch resolution work at all.

---

## 4. Can `Schedule` actually be eliminated? Case by case

Every reference-point constraint reduces to a start-time equation. With reference-point fraction
`p(start)=0`, `p(center)=½`, `p(end)=1`:

```text
t_B = t_A + p_A·D_A + rel_time − p_B·D_B
```

Given solved starts, the lowering is mechanical: normalise so `min_i t_i = 0`, sort each channel's
operations by `(start, stable source order)`, and emit `delay[t_i − cursor(c)]` before each.

| Case                                       | Encoding without `Schedule`                                                                     | Needs                                       |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------ | --------------------------------------------- |
| `start(B) = end(A) + d`                    | same channel: `A; delay[d]; B;`. Different channels: `barrier fA,fB; A; delay[d] fB; B;`         | nothing new                                 |
| `start(B) = start(A) + d`                  | `barrier fA,fB; A; delay[d] fB; B;`                                                             | nothing new (illegal if same channel and `0<d<D_A`) |
| `center(B) = center(A)`                    | `box[T] { barrier; delay[(T−a)/2] fA; A; …; delay[(T−b)/2] fB; B; …; barrier; }`                 | **`box` + known/stretchy `T`**              |
| `end(B) = end(A)` (right align)            | `box[T] { delay[T−a] fA; A; delay[T−b] fB; B; }`, leading delays may be stretches                | **`box` (+ `stretch`)**                     |
| B overlaps A on another channel, offset δ≥0 | `barrier fA,fB; A; delay[δ] fB; B;`                                                             | nothing new                                 |
| B overlaps A, offset δ<0                   | `barrier fA,fB; delay[−δ] fA; A; B;`                                                            | **block-level normalisation**               |
| B references an op many statements earlier | emit against B's own cursor after solving: `delay[t_B − cursor(fB)] fB; B;`                      | **buffered block + solver**                 |
| negative `rel_time`                        | solve, shift the block so `min t = 0`, then emit non-negative delays                            | **block-level normalisation**               |

**The one genuine limitation** is online construction, not expressivity. If a streaming builder has
already advanced channel `fB` to 30 ns and then receives "B starts at 5 ns," no combination of
appended non-negative `delay`/`barrier`/`box`/`stretch` can move the cursor backwards. A *buffered*
block can reorder; a strictly append-only emitter cannot.

This is fine for eq1_pulse: `build_sequence()` / `build_schedule()` already accumulate the whole
context and hand back a model at exit. The solver runs at context exit, not per operation.

**Conclusion:** the primitive set subsumes any *completed, feasible* schedule. `Schedule`'s residual
value is as a **compiled timing table**, not as a second authoring language.

---

## 5. Recommended target vocabulary

Five candidate vocabularies, evaluated against (a) OpenPulse round-trip, (b) natural expression of
Ramsey/echo/DD, (c) JSON serialisability:

| Vocabulary                                          | Round-trip | Ergonomics | JSON | Verdict                                     |
| --------------------------------------------------- | ---------- | ---------- | ---- | --------------------------------------------- |
| `delay` + `barrier`                                 | good       | poor       | ✅   | too low-level alone; keep as the lowered core |
| `+ box(duration)`                                   | strong     | fair       | ✅   | viable minimal interchange form               |
| `+ stretch`                                         | best       | good       | ✅   | **best portable core**                        |
| alignment contexts (left/right/sequential/equispaced/positions) | must lower | best | ✅ (avoid callables) | **best public builder layer over the above** |
| reference-point constraints (`ref_op`/`ref_pt`/…)   | poor       | verbose    | ✅   | optional advanced form only; not the default  |

Concretely:

```text
Block {
    alignment: left | right | sequential
             | equispaced(duration)
             | positions(duration, fractions),
    duration: DurationExpr | null,        # the box[...] designator
    children: [Operation | Block | Wait | Barrier]
}
```

Serialise `positions` as an explicit fraction array rather than a Python callable — that keeps
Qiskit-`AlignFunc`-level expressivity (Uhrig DD, non-uniform sequences) without embedding
executable code in the IR:

```json
{"alignment": {"kind": "positions",
               "duration": {"ns": 300},
               "fractions": [0.0203, 0.0794, 0.1726]}}
```

Builder ergonomics have well-established precedents to copy — Qiskit's
`with pulse.align_right():`, LabOne Q's `with exp.section(alignment=SectionAlignment.RIGHT, length=...)`,
and oqpy's `with Box(prog, duration=200e-9):`.

---

## 6. Proposed migration path

> **Superseded** by [PR #7](https://github.com/equal1/eq1_pulse/pull/7).
> The adopted approach is simpler in one respect and larger in another: `Schedule` is *isolated*
> rather than reimplemented as a lowering target (there is no `compile_timing()` — nothing needs
> to be lowered, because we consume rather than produce), but the isolation is stricter, with
> separate model *and* builder modules and enforced import direction. The staging below is kept
> because the ordering logic still holds.

Modelled on Qiskit's `ScheduleBlock` → `block_to_schedule()` architecture.

| Stage      | Action                                                                                                                                                                             |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **N**      | Add to the sequence world: `Box` (nestable, optional hard duration), alignment policies, symbolic `Stretch` duration expressions, and `durationof`. Add `compile_timing(seq) -> CompiledSchedule`. |
| **N+1**    | Reimplement `build_schedule()` on top of the unified builder: it constructs a sequence/block, lowers it, and returns a compatibility wrapper. One deprecation warning at context entry — not per operation. |
| **N+2**    | Delete `SchedRepetition` / `SchedIteration` / `SchedConditional` from the models and the docs; the builder's control-flow context managers stop branching on context kind. Keep deserialisation adapters for existing JSON. |
| **N+3**    | Remove `build_schedule()` from the public namespace. Rename `Schedule` → `CompiledSchedule` (or `TimingTable`): immutable, produced by compilation, inspectable and exportable, never authored. |
| long term  | Keep `legacy_schedule_to_sequence()` and versioned JSON migration; preserve operation ids so stored `ref_op` links can be translated.                                               |

The immediate structural win: today every builder operation must branch on whether it is inside a
sequence or a schedule context (`_in_schedule` / `_in_sequence` / `_add_to_sequence` /
`_add_to_schedule` / `_reject_schedule_params`), and `ScheduleParams` threads through nearly every
public function signature in [`builder/core.py`](../../src/eq1_pulse/builder/core.py). Collapsing to
one world removes that entire axis — roughly the `OperationToken`, `ScheduleParams`,
`resolve_schedule_params`, and `_reject_schedule_params` machinery, plus the three duplicated
control-flow model classes.

---

## 7. Things that genuinely get harder, and the mitigations

| Concern                                          | Mitigation                                                                                                          |
| ------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------- |
| Centring is currently one line (`ref_pt="center"`) | Provide an `equispaced` / `positions` alignment policy and a `box` with a duration. Do not make users write `(T−a)/2` by hand. |
| Negative offsets / backward references           | Solve at block exit and normalise `min t = 0`. Reject only when the block boundary is externally fixed.              |
| Zero-duration op ordering                        | Order events by `(time, stable resource-local sequence number)`, never by time alone. `set_phase` before `play` on the same frame must survive lowering — OpenPulse relies on source order for this, and quantify documents a real hazard where equal-time zero-duration instructions come out reordered. |
| Measurement atomicity                            | eq1_pulse already carves out "a `Play` and its corresponding `Record`" as an atomic exception in the sequence model. Make it a **first-class compound operation** with a resource reservation and per-child offsets, rather than two siblings plus a barrier. A barrier expresses synchronisation but not indivisibility. Note that OpenPulse's `defcal` entry barrier gives a *common epoch*, not automatic simultaneity — the spec's own measure example deliberately puts a `barrier` *between* play and capture so capture starts after the stimulus. |
| Loss of scheduling intent in the compiled output | Keep `ref_op`-style provenance as optional metadata on `CompiledSchedule` for debugging/plots. Once lowered, a 10 ns delay no longer says whether it meant centring, latency, or padding. |
| `stretch` support is thin in the wild            | Ship `stretch` in the IR but make the compiler resolve it eagerly by default; emit concrete delays unless the target advertises stretch support. |

---

## 8. Open questions for the team

### Resolved

| Question                        | Resolution                                                                                                                    |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| **Frames** (§3.3)               | Flat `ChannelRef` stays. A channel *is* a `(port, clock)` pair with an implicit frame; all clocks are NCOs on one global clock, so channels are mutually phase-coherent. Multiplexing and per-transition phase are handled by declaring more channels. The channel-mapping representation is future work. |
| **`Store`** (§3.4)              | Deliberately outside the pulse language — a job/experiment-layer concern. Non-blocking, since we consume rather than produce. Whether it should stay in the `DataOp` union is a separate tidiness question. |
| **Ramped square / chirped sine** (§3.5) | Non-blocking in the consume direction. The real question inverts: confirm we can *absorb* `gaussian`, `drag`, `sech`, `gaussian_square` — `ExternalPulse(function=..., params=...)` is exactly that shape. |
| **`Wait` semantics** (§3.2)     | No change needed. `delay[d] a, b;` imports as `barrier(a, b); wait(a, b, d)` — exactly equivalent — and `wait(a, b, d)` exports as one `delay` statement per channel. `Wait` is the more primitive operation; OpenQASM's multi-resource `delay` is the composite. Documentation task only. |
| **Amplitude units** (§3.6)      | Physical units are a staple of the representation and stay. A hardware profile is an assumed precondition, not a missing artefact — importing normalised OpenPulse amplitudes requires one, which is expected. |
| **How aggressive?** (§6)        | Isolate, do not delete. Separate experimental model and builder modules, dropped from public namespaces, one `FutureWarning` at `build_schedule()` entry, retagged in the generated schema, moved out of the main docs tree. Delete after one release cycle. |
| **`Box` shape**                 | Named `ExternalBlock`, with `program: FullyQualifiedIdentifier`, pairing with `ExternalPulse`/`external_pulse()`. |
| **Generated OpenAPI**           | Schedule schemas *move* to an `experimental` tag rather than being dropped, so wire compatibility is preserved while visibility is not. |

### Still open

Nothing blocking. See the plan's §9 for two implementation-time choices
(`unconsumed_blocks` handling, and whether `ExternalBlock` is worth adding to the frozen
schedule unions during the deprecation window).

---

## 9. One-line summary

`OpSequence` is already the OpenPulse model and becomes the only representation; `Schedule` is
quantify's model, which OpenPulse cannot express and which every other live framework has moved
away from — isolate it into an unused experimental module, and spend the effort instead on the
opaque `ExternalBlock` and the channel-mapping representation.
