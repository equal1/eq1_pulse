# Raw Perplexity result — 03: Can box/delay/barrier/stretch subsume a reference-point Schedule?

> Model: `sonar-deep-research`. Query: whether `box` + `delay` + `barrier` + `stretch` +
> nested blocks can fully subsume a quantify-style reference-point schedule; minimal portable
> timing vocabulary; builder-DSL idioms; deprecation strategy; zero-duration ordering;
> multi-channel atomic operations.
>
> Citation URL list truncated to primary sources at the end.

---

# Recommendation

**Yes at the lowered-timeline level, but no at the authoring-language level.** Any *feasible, statically resolvable* reference-point schedule can be lowered to nested blocks plus per-channel `delay`, `barrier`, and optionally `stretch`. However, an append-only sequence cannot directly preserve arbitrary backward references, negative offsets, or unresolved center/right-alignment constraints without first buffering a block and solving its timing constraints.

The best design is therefore:

> **One public sequence/block IR**, with `delay`, `barrier`, optional-duration `box`, and serializable alignment policies (`left`, `right`, `sequential`, `equispaced`, and explicit positions). Treat `stretch`/duration expressions as symbolic timing values. Lower this IR to an internal absolute timing table or per-channel delayed sequence. Do not retain a parallel public `Sched*` control-flow hierarchy.

This follows the historical Qiskit `ScheduleBlock → block_to_schedule() → Schedule` design and LabOne Q's nested, aligned sections, while mapping naturally to OpenQASM 3/OpenPulse.

---

## 1. Can OpenQASM-style primitives subsume reference-point scheduling?

Let operation $X$ have start $t_X$, duration $D_X$, and reference-point fraction

$$p(\text{start})=0,\quad p(\text{center})=\tfrac12,\quad p(\text{end})=1.$$

A Quantify-style constraint $\operatorname{pt}_{new}(B) = \operatorname{pt}(A)+d$ becomes

$$t_B=t_A+p_A D_A+d-p_B D_B.$$

Quantify's timing model performs essentially this calculation in
`determine_absolute_timing`/`_determine_absolute_timing`: `ref_pt` defaults to `"end"`,
`ref_pt_new` defaults to `"start"`, and absolute starts are derived from the reference time,
relative time, and operation duration.

### Constructive lowering proof

For every feasible schedule:

1. Solve the reference constraints for each operation's absolute start $t_i$.
2. Shift all starts by $-\min_i t_i$, making the schedule origin non-negative.
3. For each channel $c$, sort operations by `(start_time, stable_source_order)`.
4. Maintain a channel cursor $C_c$.
5. Before operation $i$, emit `delay[t_i-C_c] c`; then emit $i$, setting $C_c=t_i+D_i$.
6. Reject the schedule if `t_i < C_c` on the same exclusive channel — this represents an illegal overlap.
7. Use `barrier` at synchronization boundaries and `box` to preserve nesting/optimization boundaries.

OpenPulse frames are already independent clocks. `play`, `capture`, and `delay` advance the
relevant frame clock; `barrier f1, f2` advances both to their latest current time. Operations
on separate frames may therefore overlap.

That proves **extensional equivalence after timing resolution**. It does *not* prove that an
append-only sequence has equivalent authoring power: deferred alignment and backward
constraints require a block-local solver or another buffered lowering pass.

In the following encodings, `a = durationof({ A; })`, `b = durationof({ B; })`, and `fA`/`fB`
are their frames.

| Case                                                                  | OpenQASM 3 / OpenPulse encoding                                                                                                                                                                                                     | Extra machinery or limitation                                                                                                                                                                                    |
| --------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **(a) `start(B) = end(A) + d`**                                       | Same frame: `A; delay[d] f; B;`. Different frames, if `fB` has not passed `end(A)`: `A; barrier fA, fB; delay[d] fB; B;`. General lowering emits `delay[tA + a + d - cursor(fB)] fB; B;`.                                             | A barrier may overconstrain unrelated work and is exact only if `cursor(fB) <= end(A)`. The general case needs absolute-time calculation plus per-channel delay insertion.                                            |
| **(b) `start(B) = start(A) + d`**                                     | At a common epoch: `barrier fA, fB; A; delay[d] fB; B;`. For the same frame and `d >= a`, use `A; delay[d-a] f; B;`.                                                                                                                 | If `0 < d < a` on the same exclusive frame, the requested overlap is illegal. On different frames it is straightforward.                                                                                             |
| **(c) `center(B) = center(A)`**                                       | Choose block span `T >= max(a,b)`: `box[T] { barrier fA,fB; delay[(T-a)/2] fA; A; delay[(T-a)/2] fA; delay[(T-b)/2] fB; B; delay[(T-b)/2] fB; barrier fA,fB; }`.                                                                     | Requires known or symbolically solvable durations. If `T` is not known, use stretches or an explicit `center`/position alignment policy lowered to these delays. OpenQASM's DD example uses `durationof` and negative half-duration terms to align pulse centers. |
| **(d) `end(B) = end(A)`**                                             | Right-align inside span `T`: `box[T] { barrier fA,fB; delay[T-a] fA; A; delay[T-b] fB; B; barrier fA,fB; }`. The leading delays can be stretches constrained by the box.                                                             | This is exactly an ALAP/right-alignment context. A right-alignment policy is much more ergonomic than asking users to write the padding expressions. OpenQASM explicitly shows a leading stretchy delay inside a fixed-duration box to schedule contents as late as possible. |
| **(e) B overlaps A on a different channel at arbitrary offset $\delta=t_B-t_A$** | If `δ >= 0`: `barrier fA,fB; A; delay[δ] fB; B;`. If `δ < 0`: `barrier fA,fB; delay[-δ] fA; A; B;` — `B` starts at the block origin even though it appears textually later, because `fB` has an independent clock. | Legal only on distinct non-conflicting resources. The lowering pass should normalize the earliest start to zero and insert per-frame delays.                                                                          |
| **(f) B references an operation many statements earlier / out of order** | After solving, emit B against its own frame cursor: `delay[tB-cursor(fB)] fB; B;`. Textual order across disjoint frames need not equal temporal order.                                                                              | If `cursor(fB) > tB`, an append-only builder cannot backtrack. Buffer the enclosing block, build a dependency graph, solve, then emit channel timelines. OpenQASM has no general source-level `startof(label)` event-reference expression. |
| **(g) Negative `rel_time`**                                           | Compute `tB = tA + pA*a + rel_time - pB*b`, shift the whole block so its minimum time is zero, then insert non-negative per-channel delays. For `start(B)=start(A)-δ`: `delay[δ] fA; A; B;` on distinct frames.                       | A negative *offset* is representable; a negative emitted `delay` is not. Stretch values are non-negative, although duration expressions may contain negative terms if the final instruction duration resolves non-negative. Same-channel overlaps remain illegal. |

### Concrete counterexample to direct append-only equivalence

Suppose an append-only builder has already advanced `fB` to `30 ns`, then receives:

```text
A starts at 10 ns
B references A with start(B) = start(A) - 5 ns
```

Thus `B` must start at `5 ns`, but `cursor(fB)=30 ns`. No combination of newly appended
non-negative `delay`, `barrier`, `box`, or `stretch` can move `fB` backward to `5 ns`.

A deferred block can solve and reorder the timeline; a strictly streaming append-only builder
cannot. Therefore:

> **The primitive set subsumes the completed schedule, not arbitrary online construction of that schedule.**

---

## 2. Minimal portable timing vocabulary

| Candidate vocabulary                                       | OpenPulse round-trip                                                                                    | Ramsey / echo / DD ergonomics                                                                                     | JSON serialization                                     | Assessment                                                                     |
| ------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| **(i) `delay + barrier`**                                  | Good only after all timing has been concretized. Both correspond directly to OpenPulse frame-clock ops. | Ramsey natural; center/right alignment and DD spacing require manual duration arithmetic and padding.              | Excellent.                                             | Too low-level as the sole authoring model. Keep as the lowered core.           |
| **(ii) `delay + barrier + box(duration)`**                 | Strong. OpenQASM boxes preserve timing/optimization boundaries and may impose a total duration.         | Fixed-window Ramsey/echo and right alignment become expressible, but users still calculate padding manually.       | Excellent: `{kind:"box", duration, body}`.             | A viable minimal portable interchange form.                                    |
| **(iii) `delay + barrier + box + stretch`**                | Closest match to OpenQASM timing design. `stretch` is a non-negative symbolic duration resolved at compile time. | Naturally expresses calibration-independent DD spacing, equalized ends, and deferred ALAP padding.                | Good if expressions are an AST rather than Python objects. | **Best portable core vocabulary.**                                             |
| **(iv) Alignment contexts: left/right/sequential/equispaced/func** | Must be lowered to boxes, delays, barriers, and stretches; OpenPulse does not spell these as context names. | Best authoring ergonomics. Qiskit described `AlignEquispaced` as useful for periodic DD and `AlignFunc` for Uhrig-type DD. | Good except raw Python callbacks. Serialize `func` as a named strategy, expression AST, or explicit fractional-position array. | **Best public builder layer over (iii).**                                      |
| **(v) Full `rel_time/ref_op/ref_pt/ref_pt_new` constraints** | Requires solving before OpenPulse export; does not round-trip through standard OpenQASM syntax without vendor annotations. | Maximally expressive, but verbose and easy to misuse for ordinary pulse patterns.                                 | Technically easy — IDs and enums are JSON-friendly — but graph validation and dangling-reference migration are harder. | Retain only as an optional advanced/internal constraint form, not the default. |

### Sweet spot

```text
Block {
    alignment: left | right | sequential |
               equispaced(duration) |
               positions(duration, fractions),
    duration: DurationExpr | null,
    children: [Operation | Block | Delay | Barrier]
}
```

with:

- per-channel ASAP sequencing as the default;
- `Delay(DurationExpr, resources)`;
- `Barrier(resources)`;
- optional-duration `Box`/`Block`;
- `Stretch` and `durationof`-style expression nodes;
- nested blocks;
- stable source-order IDs;
- optional advanced constraints only inside a buffered `constraints(...)` block.

Avoid serializing `align_func(callable)`. Instead serialize, for example:

```json
{
  "alignment": {
    "kind": "positions",
    "duration": {"value": 300, "unit": "ns"},
    "fractions": [0.0203, 0.0794, 0.1726]
  }
}
```

That preserves Qiskit-like ergonomics without embedding Python execution into the IR.

---

## 3. Shipping Python builder idioms

**OQPy** — does have a box context manager: `oqpy.timing.Box(program, duration=None)`.
Timing methods are `oqpy.Program.delay(...)` and `oqpy.Program.barrier(...)`; symbolic timing
uses `oqpy.classical_types.StretchVar` and `DurationVar`.

```python
import oqpy
from oqpy.timing import Box

prog = oqpy.Program()
s = oqpy.StretchVar(name="s")

with Box(prog, duration=200e-9):
    prog.delay(s, frame)
    prog.play(frame, waveform)

prog.barrier(frame1, frame2)
```

**Zurich Instruments LabOne Q** — `Experiment.section(..., alignment=SectionAlignment.RIGHT, length=...)`
right-aligns contents in a fixed window. `play_after` creates an end-before-start dependency
between sections. Sections sharing a signal serialize; disjoint sections otherwise run in parallel.

```python
with exp.section(uid="excitation", alignment=SectionAlignment.RIGHT, length=1e-6):
    exp.play(signal="drive", pulse=x90)
    exp.delay(signal="drive", time=100e-9)
    exp.play(signal="drive", pulse=x90)

with exp.section(uid="readout", play_after="excitation"):
    exp.measure(...)
```

**Historical Qiskit Pulse builder** — exact builder symbols were `qiskit.pulse.builder.align_left`,
`align_right`, `align_sequential`, `align_equispaced`, and `align_func`. `pulse.build()` produced
a `ScheduleBlock`; `qiskit.pulse.transforms.block_to_schedule()` resolved alignment to a concrete `Schedule`.

```python
from qiskit import pulse

with pulse.build() as block:
    with pulse.align_left():
        pulse.play(p0, d0)
        pulse.play(p1, d1)

    with pulse.align_right():
        pulse.play(p2, d0)
        pulse.play(p3, d1)

    with pulse.align_sequential():
        pulse.play(p4, d0)
        pulse.play(p5, d1)

    with pulse.align_equispaced(duration=100):
        pulse.play(x90, d0)
        pulse.play(x180, d0)
        pulse.play(x90, d0)

    with pulse.align_func(duration=300, func=udd_pos):
        for _ in range(10):
            pulse.play(x180, d0)

schedule = pulse.transforms.block_to_schedule(block)
```

**Quantum Machines QUA** — `qm.qua.align(*elements)` waits each named element until all have
finished their currently running statement. With no arguments it aligns every element used in
the program. Same-element operations follow source order; different elements run independently
until constrained.

```python
from qm.qua import *

with program() as prog:
    play("x90", "qubit")
    align("qubit", "resonator")
    play("readout", "resonator")
```

**Pulser** — `pulser.sequence.Sequence.align(*channels, at_rest=True)` inserts delays so the next
action on every listed channel starts after the latest channel has finished. `at_rest=True`
includes output-modulation tails.

```python
seq.add(pulse_a, "rydberg")
seq.add(pulse_b, "raman")
seq.align("rydberg", "raman")
seq.add(next_pulse, "rydberg")
```

LabOne Q is especially close to the recommended model: nested serializable sections, independent
alignment per section, explicit `length`, and `play_after` only when an exceptional cross-section
dependency is needed. Its alignment is deliberately not inherited into nested sections.

---

## 4. Deprecation and migration

Yes — **"public structured authoring form, internal lowered timed form" is a well-established
compiler and quantum-framework pattern.**

| Example / phase                             | Shipping precedent                                                                                                                                                                                                                          | Recommended action                                                                                                              |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| **Qiskit `Schedule` → `ScheduleBlock`**     | Qiskit introduced `ScheduleBlock` as a relatively scheduled representation using `alignment_context` instead of explicit `t0`; it was described as best suited to the builder. `pulse.build()` built a `ScheduleBlock`, while `qiskit.pulse.transforms.block_to_schedule(block)` produced the exact-time `Schedule`. | Make `build_sequence()` the sole documented builder, add block/alignment constructs, and expose `lower_to_timing_table()` / `compile_timing()` rather than a second builder universe. |
| **Qiskit's eventual package removal**       | Both representations coexisted for years. Later `qiskit.pulse.Schedule` was deprecated as of Qiskit 1.3, and the entire pulse package — including `ScheduleBlock` — was removed in Qiskit 2.0. This final removal was broader than a `Schedule → ScheduleBlock` migration. | Do not claim Qiskit ultimately retained `Schedule` internally; use its earlier dual-representation/lowering architecture as the precedent. |
| **Quantify absolute timing**                | `determine_absolute_timing` modifies a schedule so every operation has absolute timing; `Schedule.timing_table` is then an inspection/output view containing fields such as `abs_time` and `duration`.                                       | Recast your old `Schedule` as `CompiledSchedule` / `TimingTable`: immutable, produced by compilation, inspectable/exportable, but not directly authored. |
| **PennyLane capture vs internal repr**      | PennyLane recommends capturing a quantum function through `AnnotatedQueue` and converting to `QuantumScript`; ordinary users likely do not need the tape classes directly.                                                                   | Separate ergonomic capture/building from canonical immutable representation.                                                    |
| **CUDA-Q compiler pipeline**                | CUDA-Q captures Python kernel ASTs, converts them to Quake MLIR, then lowers through passes to QIR/LLVM.                                                                                                                                     | Treat explicit timing as a lowering product, just as executable IR is a product of kernel authoring rather than a parallel user DSL. |

### Concrete migration sequence

| Release stage | Public behavior                                                                                                                                                     |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **N**         | Add `box`, alignment contexts, `delay`, `barrier`, symbolic durations, and nested unified control flow to `build_sequence()`. Add `compile_timing(sequence) -> CompiledSchedule`. |
| **N+1**       | Make `build_schedule()` call the unified builder internally and return a compatibility wrapper after lowering. Emit one deprecation warning at builder entry, not one per operation. |
| **N+2**       | Remove `SchedRepetition`, `SchedIteration`, and `SchedConditional` from documentation and examples. Keep deserialization adapters for old JSON schemas.               |
| **N+3 major** | Remove `build_schedule()` from the normal public namespace. Keep `CompiledSchedule`/`TimingTable` as an output type and perhaps a legacy import shim.                |
| **Long term** | Maintain `legacy_schedule_to_sequence()` and versioned JSON migration. Preserve old operation IDs where possible so stored `ref_op` links can be translated.         |

A useful compatibility façade:

```python
@deprecated("Use build_sequence() and compile_timing().")
@contextmanager
def build_schedule(...):
    with build_sequence(...) as seq:
        yield seq
    return compile_timing(seq)
```

Internally it should use exactly the same operation and control-flow classes, never construct
`Sched*` variants.

---

## 5. Zero-duration operations and deterministic ordering

| Framework/model     | Rule for zero-duration operations                                                                                                                                                                                                                            | Consequence for your IR                                                                     |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------- |
| **OpenPulse**       | `set_phase`, `shift_phase`, `set_frequency`, `shift_frequency` are instantaneous operations at the frame's current time. A following `play(frame, ...)` uses that frame's current phase/frequency, so same-frame source order determines state even though time does not advance. Frame time advances only through `delay`, `play`, `capture`, `barrier`. | Zero-duration state mutations must participate in the per-resource instruction order. Do not sort solely by timestamp. |
| **QUA**             | Operations on the same element depend on each other in source order; operations on different elements are independent unless connected by `align()`. `wait()` introduces time, while frame/frequency transformations create dependencies on their element.     | Give each resource an ordered command stream. A phase update followed by a play must survive lowering in that order. |
| **Quantify**        | `schedulables` is ordered, and when several schedulables have the same absolute time that dictionary order determines precedence. Nevertheless, Quantify explicitly warns that the time order of zero-duration assembly instructions with identical timing may be incorrect and recommends checking generated assembly. | Timestamp plus insertion order is necessary but not sufficient if later passes reorder equal-time nodes. |
| **Recommended**     | Represent event order as `(time, resource-order-token)` rather than time alone. Add explicit dependencies for stateful zero-duration operations.                                                                                                              | Use a stable sequence number and resource-local predecessor edge. A barrier is an ordering/synchronization directive, not just a zero-duration display item. |

Recommended invariant:

```text
For each resource:
    operation[i] happens-before operation[i+1]
even when both durations are zero and both absolute timestamps are equal.
```

For cross-resource zero-duration declarations or classical assignments, distinguish:

- **compile-time declarations**: lexical scope only, no pulse timestamp;
- **runtime classical assignments**: explicit dependency nodes;
- **frame mutations**: resource-local ordered nodes;
- **barriers**: many-resource happens-before edges.

Do not canonicalize equal-time operations by operation type or UUID. Preserve stable source
order unless explicit dependencies require otherwise.

---

## 6. Multi-channel atomic operations and measurement

The premise needs one qualification: OpenPulse does **not** automatically make every `play` and
`capture` in a `defcal measure` simultaneous merely because they are in that `defcal`.

Every entering frame is implicitly barrier-aligned at `defcal` entry. Thus this starts both at
the same entry time:

```openqasm
defcal measure $0 -> bit {
    // implicit entry barrier on participating frames
    play(stimulus_frame, meas_wf);
    bit result = capture_v2(capture_frame, kernel);
    return result;
}
```

Because the frames are independent, the first operation on each starts at its frame's aligned
current time. By contrast, the specification's measurement example does:

```openqasm
play(stimulus_frame, meas_wf);
barrier stimulus_frame, capture_frame;
waveform raw_output = capture_v1(capture_frame, 16000dt);
```

which deliberately starts capture **after** the stimulus play has completed, not simultaneously.

| Framework       | How co-timing/atomicity is represented                                                                                                                                 | Lesson                                                                                     |
| --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| **OpenPulse**   | Independent `play` and `capture` statements; defcal-entry frame alignment establishes a common epoch. An explicit barrier before both can establish the same epoch in a larger block. A barrier after `play` delays capture until play ends. | Co-timing comes from frame clocks and entry synchronization; atomicity comes from treating the `defcal` invocation as a composite operation boundary. |
| **LabOne Q**    | `Experiment.measure(...)` unifies optional readout playback, acquisition, and optional post-acquisition delay. Measurement sections have extra compiler rules: acquire operations on one AWG must start together, as must play operations. | A fused high-level measurement operation is a practical shipping design.                   |
| **Qiskit Pulse**| `qiskit.pulse.builder.measure(qubits, registers=None)` was a macro because pulse-level measurement consists of both stimulus and acquisition; users could alternatively emit `play()` and `acquire()` themselves. | Offer a composite macro/operation, while retaining low-level primitives for advanced use.  |
| **Quantify**    | High-level measurements are decomposed during compilation into pulse and acquisition operations.                                                                        | Keep the semantic measurement intact until the backend-aware decomposition pass.           |

### Recommended representation

```json
{
  "kind": "Measure",
  "atomic": true,
  "resources": ["readout:q0", "acquire:q0"],
  "children": [
    {"kind": "Play",    "resource": "readout:q0", "start_offset": {"value": 0, "unit": "ns"}},
    {"kind": "Capture", "resource": "acquire:q0", "start_offset": {"value": 0, "unit": "ns"}}
  ]
}
```

Semantics:

1. The parent reserves the union of all child resources.
2. Child offsets are relative to one atomic entry epoch.
3. No outside operation may be inserted between or overlap conflicting resources inside the parent.
4. The parent duration is the maximum child end time.
5. Lowering to OpenPulse emits a `defcal` or a timing-preserving `box` with entry `barrier`
   followed by the independent `play` and `capture`.
6. Backend-specific acquisition latency should be an explicit child offset, not an accidental
   source-order effect.

This is preferable to representing measurement as two ordinary siblings plus a barrier: a
barrier expresses synchronization, but it does not by itself express **indivisibility**,
resource reservation, or the semantic identity of the measurement.

---

## Final architecture

```text
Authoring:
    Sequence / Block
      ├── normal operations
      ├── compound atomic operations
      ├── nested control flow
      ├── delay / barrier
      └── alignment policy + optional duration/stretch

                ↓ solve_alignment_and_timing()

Canonical compiled output:
    CompiledSchedule / TimingTable
      ├── absolute starts
      ├── durations
      ├── stable equal-time ordering
      └── per-resource timelines

                ↓ emit_openpulse()

OpenQASM 3 / OpenPulse:
    box + delay + barrier + stretch + defcal
```

That removes the duplicated `Repetition`/`SchedRepetition`, `Iteration`/`SchedIteration`, and
`Conditional`/`SchedConditional` worlds while retaining every feasible schedule as a compiler
output. The old reference-point representation remains useful as a temporary constraint graph
or diagnostic timing table — not as a second public builder language.

---

## Primary citations

- https://arxiv.org/pdf/2104.14722 — OpenQASM 3 paper
- https://openqasm.com/language/delays.html — duration/stretch/delay/box
- https://openqasm.com/versions/3.0/language/openpulse.html — OpenPulse grammar
- https://oqpy.readthedocs.io/en/stable/apidocs/oqpy.html — `oqpy.timing.Box`, `StretchVar`
- https://github.com/openqasm/oqpy
- https://github.com/Qiskit/qiskit-terra/issues/5679 — "Implementation of a pulse schedule block"
- https://quantum.cloud.ibm.com/docs/en/api/qiskit/release-notes/0.25 — ScheduleBlock introduction
- https://quantum.cloud.ibm.com/docs/en/api/qiskit/1.0/pulse — builder `align_*` symbols
- https://quantum.cloud.ibm.com/docs/en/guides/qiskit-2.0 — pulse removal
- https://quantify-os.org/docs/quantify-scheduler/v0.28.1/autoapi/quantify_scheduler/compilation/index.html — `determine_absolute_timing`
- https://quantify-os.org/docs/quantify-scheduler/dev/reference/control_flow.html
- https://docs.zhinst.com/labone_q_user_manual/core/functionality_and_concepts/03_sections_pulses/concepts/01_timing_rules.html
- https://docs.zhinst.com/labone_q_user_manual/core/reference/dsl/experiment.html
- https://docs.quantum-machines.co/1.2.2/docs/Guides/timing_in_qua/
- https://pulser.readthedocs.io/en/stable/apidoc/_autosummary/pulser.sequence.Sequence.html
- https://docs.quantum.ibm.com/api/qiskit/qiskit.pulse.transforms.AlignEquispaced
