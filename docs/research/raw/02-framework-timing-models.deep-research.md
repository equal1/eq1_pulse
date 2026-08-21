# Executive conclusion

The broad timing trend is real, but it has two distinct forms:

1. **Per-resource time cursors:** program order advances a channel/frame/element clock; `delay` advances it without output; `barrier`/`align` synchronizes several clocks. OpenPulse, AWS Braket Pulse, Quantum Machines QUA, Pulser, and largely Qibolab follow this model.
2. **Hierarchical alignment regions:** nested blocks or sections are scheduled ASAP/ALAP/sequentially inside a window. Qiskit `ScheduleBlock` and Zurich Instruments LabOne Q are the clearest examples.

**Quantify-scheduler is the main exception in this comparison.** It retains an explicit graph of relative constraints—“place the start/center/end of operation B at an offset from the start/center/end of operation A”—which is resolved into absolute times during compilation. That model is richer as a source IR but requires more lowering work for OpenPulse, whose native semantics are independent per-frame clocks advanced by `play`, `capture`, and `delay`, with `barrier` joining clocks at their maximum. [web:153][web:155]

Qiskit itself is no longer continuing this evolution: `qiskit.pulse` was deprecated in Qiskit 1.3.0 and removed in 2.0.0. IBM’s hardware-facing migration target is fractional ISA gates, while Qiskit Dynamics covers modeling and simulation use cases; neither is a drop-in public hardware pulse-programming replacement. [web:16][web:215]

---

# 1. Qiskit Pulse: `Schedule` versus `ScheduleBlock`

## 1.1 Core representation

| Representation | API and data model | Timing semantics | Parameter/lowering behavior |
|---|---|---|---|
| `qiskit.pulse.Schedule` | `Schedule(*schedules, name=None, metadata=None)`, where children can be `ScheduleComponent` objects or `(start_time: int, component)` pairs. Important methods include `insert(start_time, schedule, name=None, inplace=False)`, `shift(time, ...)`, and `append(schedule, ...)`. [web:330][web:335] | An explicit timeline: effectively a list/tree of `(t0, instruction)` pairs in integer backend samples. Each instruction has a determined start time and duration. Same-channel overlap is checked immediately and raises `PulseError`. [web:165][web:170] | Because timeslots must be constructed immediately, an instruction whose **duration** is an unbound `Parameter`/`ParameterExpression` cannot be inserted. Other non-duration pulse parameters could be symbolic, but not a duration needed for collision detection. [web:169][web:180] |
| `qiskit.pulse.ScheduleBlock` | `ScheduleBlock(name=None, metadata=None, alignment_context=None)`. It stores an ordered list of `Instruction`/nested `ScheduleBlock` children plus an `AlignmentKind`; it does not store each child’s `t0`. [web:325][web:333] | Relative and hierarchical. Start times are allocated only when `qiskit.pulse.transforms.block_to_schedule(block)` recursively applies alignment contexts. `AlignLeft` is the default. [web:166][web:315] | Supports lazy timeslot construction and therefore unbound, parameterized instruction durations. All required durations must be bound before final conversion; otherwise `block_to_schedule` raises `UnassignedDurationError`. [web:190][web:315] |

A `Schedule` is thus best understood as an already scheduled, resource-checked machine timeline. A `ScheduleBlock` is a **scheduling-intent IR**.

`ScheduleBlock` deliberately lacks operations such as `insert(t0, ...)` and `shift(t, ...)`, because those require absolute start times that the representation does not yet have. [web:333]

## 1.2 Why `ScheduleBlock` was introduced

`ScheduleBlock` was introduced in **Qiskit Terra 0.17.0**, shipped in the **Qiskit 0.25.0 metapackage**, at the beginning of April 2021. Terra 0.17.0 was published April 1, 2021; Qiskit 0.25.0 followed on April 2. [web:180][web:183][web:185]

The design record was **Qiskit Terra issue #5679, “Implementation of a pulse schedule block,” opened January 22, 2021**. It was not a numbered Qiskit RFC. The issue explicitly said:

- `Schedule` immediately evaluates channel timeslot overlap.
- Therefore, it cannot accept unbound parameterized durations.
- `ScheduleBlock` would omit explicit timeslots.
- Durations would be assigned just before conversion to `Schedule`.
- This constituted “lazy timeslot evaluation.”
- The pulse builder would be changed to produce `ScheduleBlock`.
- `Schedule` was not to be deprecated; the two representations were originally intended to coexist. [web:169][web:182]

The Terra 0.17/Qiskit 0.25 release notes described the same motivation: relative instruction ordering, implicit allocation of `t0`, arbitrary duration parameters, and lazy scheduling. They specifically warned that an instruction with an unbound duration could only be added to the newly introduced `ScheduleBlock`, not to `Schedule`. [web:180]

### The specific limitations of `Schedule`

The motivating limitation was narrower and more concrete than “absolute time is bad”:

1. A `Schedule` owns concrete channel timeslots.
2. Inserting an instruction immediately checks whether `[t0, t0 + duration)` intersects an existing interval on any of its channels.
3. That check cannot be performed if `duration` is symbolic.
4. Consequently, a calibration with a duration determined later—such as a parameterized Rabi pulse—could not naturally remain unbound in a `Schedule`.

`ScheduleBlock` postpones this check until parameter assignment and `block_to_schedule()`.

It also enabled forms of **late binding** beyond duration parameters. For example, `Reference` instructions could name a subroutine stored later in `ScheduleBlock.references`, and `ScheduleBlock.assign_references()` could supply the actual implementation after constructing the main program. [web:45]

That said, “late binding” and references were additional benefits; the original issue’s stated blocker was specifically immediate timeslot evaluation for parameterized durations.

---

# 2. Qiskit alignment contexts

All five classes derive from `qiskit.pulse.transforms.AlignmentKind`. They apply to the **direct children** of a block; a nested child block retains and applies its own context rather than inheriting the parent’s policy recursively. [web:197]

| Alignment context | Signature | Exact scheduling behavior |
|---|---|---|
| `AlignLeft` | `AlignLeft()` | ASAP/resource-compacting placement. Children are considered in block order. Each child is inserted at the earliest nonconflicting time allowed by channels shared with previously placed children. Disjoint-channel children can start together at time zero. This is parallel per channel, not globally sequential. |
| `AlignRight` | `AlignRight()` | ALAP placement. Children are traversed in reverse order and inserted as late as possible without conflict. When needed, already placed content is shifted right to make room. Disjoint-channel children are aligned against the block’s current end, so the result tends to synchronize final completion rather than initial start. |
| `AlignSequential` | `AlignSequential()` | Strict serialization across all channels: each direct child is inserted at the current total block duration. No inter-child buffer is added. Thus a pulse on `d1` waits for an earlier pulse on `d0`, even though the channels are independent. |
| `AlignEquispaced` | `AlignEquispaced(duration: int \| ParameterExpression)` | Serializes the direct children inside a specified window. Let `D = duration`, `S = Σ duration(child)`, and `N` be the number of children. The available idle time is `D-S`; for `N>1`, the principal gap is `(D-S) // (N-1)`. Integer remainder is split between the beginning and end. If `D<S`, the transform does not have room; older API documentation described returning the original schedule, while `block_to_schedule` documentation states that invalid context duration can raise `PulseError`. It is intended for uniformly spaced DD/PDD sequences. [web:196][web:197] |
| `AlignFunc` | `AlignFunc(duration: int \| ParameterExpression, func: Callable[[int], float])` | Places child `j` by **center**, not by start: `center_j = duration * func(j)`, with one-based `j`, and `t0_j = int(center_j - duration_j/2)`. `func(j)` must denote a fractional coordinate in `[0,1]`. It supports nonuniform DD patterns such as UDD. Invalid starts raise `PulseError`. Because the Python callback is not serializable, `AlignFunc` cannot be stored in QPY. [web:195][web:196][web:7] |

### Important details

- `AlignLeft` and `AlignRight` are resource-aware: they compact only against channels shared by two children.
- `AlignSequential`, `AlignEquispaced`, and nominally `AlignFunc` are classified as sequential alignment kinds; however, `AlignFunc` computes explicit callback-selected centers, and final legality still depends on resource overlap.
- `AlignEquispaced` and `AlignFunc` use integer conversion for resulting sample times, so fractional-sample positions are truncated/quantized.
- Explicit `Delay(duration, channel)` instructions remain the basic way to create intentional gaps inside any context. The `ScheduleBlock` documentation explicitly recommends `Delay` for intervals between instructions. [web:166]
- `block_to_schedule()` can insert barriers between nested contexts to preserve context boundaries. [web:315]

---

# 3. Expressivity: what `Schedule` could say that `ScheduleBlock` could not

## 3.1 Direct source-level expressivity

| Case | `Schedule` | Native `ScheduleBlock` | Practical handling |
|---|---|---|---|
| Exact arbitrary start time | Direct: `schedule.insert(t0, instruction)` or constructor pair `(t0, instruction)`. | No direct `insert(t0, ...)` or `shift(t, ...)`. [web:333] | Encode channel-local gaps with `Delay`; use nested alignment blocks; use `AlignFunc` inside a fixed window; or retain the old `Schedule` as an opaque `Call`. |
| Arbitrary relative reference such as `start(B) = end(A) + δ` | Compute `t0(B)` and insert it. | Usually straightforward with `AlignSequential` plus `Delay(δ, channel)`, but only if the intended resource ordering matches sequential/block structure. | Introduce a nested block or explicit delays. |
| `center(B) = center(A) + δ` | Compute both starts from known durations and insert them. | No general `ref_op/ref_pt/ref_pt_new` primitive. `AlignFunc` can place children by center within a known window, including equal centers on disjoint channels, but the relation must be encoded as callback coordinates and normally requires bound durations/window size. | Resolve the center equation at compile time; use `AlignFunc`, delays/nesting, or an opaque `Schedule`. |
| Same-channel overlap | **Not legal.** `Schedule` immediately rejects it. [web:165][web:170] | Can temporarily exist as unresolved intent, but conversion to a legal `Schedule` cannot produce overlapping instructions on one Qiskit pulse channel. | Split/sum waveforms into one pulse, use separate hardware channels/frames where supported, or reject. |
| Preserve a pre-existing absolute schedule verbatim | Native representation. | Not reconstructible through a direct `schedule_to_block()` API. | Wrap the `Schedule` in a `Call`; adding a `Schedule` through the pulse builder performed this wrapping implicitly. [web:325][web:327] |

## 3.2 Was there loss of executable expressivity?

**At the execution level, generally no—provided the original `Schedule` was legal and concrete.** Qiskit retained `Schedule`, and a `ScheduleBlock` could invoke an existing `Schedule` through `Call`. Thus an exactly timed schedule could be treated as an opaque leaf without translating its absolute timing into alignment contexts. The original implementation issue explicitly claimed compatibility and “no usability impact,” while retaining both representations. [web:169]

There was nevertheless a real **loss of direct declarative vocabulary** in a pure `ScheduleBlock`:

- no arbitrary `t0`;
- no `insert(t0, ...)`;
- no global `shift(t)`;
- no direct “reference the center/end of sibling X” relation;
- no general constraint graph.

Known concrete nonoverlapping timelines can usually be reconstructed using delays and nested channel lanes, but that translation is not always compact or canonical. If an arbitrary absolute-time pattern did not fit the alignment vocabulary, the intended escape hatch was an opaque `Schedule`/`Call`, not an ever-expanding set of alignment policies.

### Centering one instruction on another

`AlignFunc` is the closest native mechanism. For two disjoint-channel children, a callback can return the same fractional coordinate for both, causing their centers to coincide:

```python
AlignFunc(duration=D, func=lambda j: 0.5)
```

Each child gets:

```text
t0_j = int(D/2 - duration_j/2)
```

This is not equivalent to Quantify’s general `ref_pt="center", ref_pt_new="center"` relation:

- it refers to a containing window, not a named sibling;
- it needs a suitable known `D`;
- it does not preserve a symbolic reference edge;
- same-channel overlap remains illegal;
- callback-based `AlignFunc` cannot be QPY serialized. [web:196][web:7]

---

# 4. Deprecation and removal of Qiskit Pulse

| Event | Version/date | Stated action and rationale |
|---|---|---|
| Deprecation | **Qiskit 1.3.0, November 28, 2024** [web:286][web:288] | The entire Pulse package and related backend/calibration APIs were deprecated for removal in 2.0. Issue #13063 said Pulse and related functionality were “not in scope for the direction of the project anymore.” IBM described a focus on utility-scale experiments and applications leading toward quantum advantage. [web:21][web:215] |
| IBM hardware pulse-access removal | **February 3, 2025** | Pulse-level access was removed from IBM Quantum QPUs. IBM said the predominant pulse-control use case was continuously parameterized rotations, now supplied by fractional ISA gates. [web:222][web:307] |
| SDK removal | **Qiskit 2.0.0, March 31, 2025 tag; public release announcement April 3, 2025** | `qiskit.pulse`, pulse visualization, pulse scheduling/calibration machinery, pulse fake backends, and pulse QPY support were removed. [web:20][web:22][web:288] |

## 4.1 What is IBM’s replacement?

The most precise answer is:

- **Inside Qiskit SDK 2.x: no direct replacement.** The 2.0 migration guide says `qiskit.pulse` was removed “without replacement.” `QuantumCircuit.add_calibration()`, `QuantumCircuit.calibrations`, and related `Target` calibration APIs were also removed. [web:16][web:276][web:280]
- **For execution on IBM Heron and later QPUs:** use fractional native gates, principally continuously parameterized `RX(θ)` and `RZZ(θ)`, exposed by opting into fractional gates in the backend `Target`. [web:215][web:222]
- **For pulse-level physics modeling/simulation:** IBM points users to Qiskit Dynamics and its `qiskit_dynamics.signals` model. [web:215]

These are replacements for common **use cases**, not a full replacement for sample-level public pulse programming.

## 4.2 The “pulse gates” era

Before removal, a user could attach a custom pulse implementation to a circuit instruction:

```python
QuantumCircuit.add_calibration(
    gate,
    qubits,
    schedule,
    params=None,
)
```

The resulting calibration mapped a logical gate and parameter tuple to a `Schedule` or `ScheduleBlock`; the `PulseGates` transpiler pass could pull calibrations from an `InstructionScheduleMap`. [web:274][web:276][web:279]

Fractional gates reverse the ownership:

- With pulse gates, the **user supplied the pulse calibration**.
- With fractional gates, IBM supplies a continuously parameterized native ISA instruction and its hidden device calibration.
- Users gain efficient arbitrary-angle rotations but lose public waveform, envelope, acquisition, and frame-level control.

## 4.3 Qiskit Dynamics and possible `qiskit-pulse` successors

Deprecation warnings said the package would be “moved to the Qiskit Dynamics repository,” and migration work was tracked separately. [web:300][web:304] But the effective status by August 2026 is more nuanced:

- Qiskit Dynamics 0.6 documentation still describes conversion of Qiskit Pulse `Schedule` objects into `Signal` objects.
- Its `InstructionsToSignals` converter accepts `Schedule`; a `ScheduleBlock` must first be lowered using Qiskit Pulse’s `block_to_schedule`. [web:210][web:218]
- Qiskit Experiments noted in 2026 that Dynamics planned to pin to Qiskit 1, which underscores that this was not yet a transparent Qiskit-2 replacement package. [web:302]
- There is no IBM hardware path in which a standalone `qiskit-pulse` package restores the former public pulse-gate service.

Thus Qiskit Dynamics is principally the **simulation/modeling successor**, while fractional gates are the **IBM execution successor**.

## 4.4 Relation to OpenPulse

Qiskit Pulse was not simply replaced by OpenPulse:

- OpenPulse remains an OpenQASM 3 pulse-language specification used by platforms such as AWS Braket.
- IBM’s Qiskit 2.x migration did not replace `ScheduleBlock` with an OpenPulse builder or OpenPulse submission path.
- The architectural resemblance remains important: `ScheduleBlock` moved toward relative scheduling, while OpenPulse uses frame-local cursors and barriers rather than a global `(t0, instruction)` list. [web:153][web:155]

---

# 5. Other frameworks, side by side

| Framework | Core classes and representative APIs | Timing model | Direction, limitations, and OpenPulse relation |
|---|---|---|---|
| **Quantify-scheduler** | `Schedule`; `Schedule.add(operation, rel_time=0, ref_op/ref_schedulable=..., ref_pt=..., ref_pt_new=...)`; current `Schedulable.add_timing_constraint(rel_time=0, ref_schedulable=None, ref_pt=None, ref_pt_new=None)`. Reference points are `"start"`, `"center"`, or `"end"`. [web:61][web:257] | **Explicit relative-reference graph.** A constraint means `point(new) = point(reference) + rel_time`. Defaults are reference `"end"` and new `"start"`, giving back-to-back program order. Compilation calls `determine_absolute_timing` and writes concrete operation start times. [web:66][web:233] | Still retains this model in v0.28.1; it has not migrated to a Qiskit-style alignment-block IR. Pain points include named-reference bookkeeping, dependence on known durations, inability to reference an operation inside a nested subschedule from outside, and non-obvious multiple-constraint semantics: multiple constraints delay the operation until all are met, while exact equality is recommended to use one constraint. [web:229][web:240][web:244] |
| **Pasqal Pulser** | `Sequence(register, device)`; `declare_channel`, `target(qubits, channel)`, `add(pulse, channel, protocol=...)`, `delay(duration, channel, at_rest=False)`, `align(*channels, at_rest=True)`. [web:76][web:79] | Per-channel sequential schedules. Operations append to a channel’s local timeline. `delay` advances one channel; `align` inserts delays so selected channels’ next actions start after the latest channel has finished. `target` is itself a timed retargeting operation for local channels. | Strongly cursor/sequential. It is not a named relative-reference graph and has no general nested ASAP/ALAP block abstraction. Hardware output-modulation tails complicate “finished”; `at_rest=True` includes these tails, and too-short separation can merge consecutive outputs. [web:77] |
| **AWS Braket Pulse** | `PulseSequence().play(frame, waveform)`, `.delay(qubits_or_frames, duration)`, `.barrier(qubits_or_frames)`, captures and frame frequency/phase operations. [web:345][web:346] | OpenPulse per-frame clocks. `play` advances the selected frame by waveform duration; `delay` advances specified frames/qubits; `barrier` raises all selected frame clocks to their latest current time. | Directly convergent with the OpenPulse cursor model because it emits OpenQASM 3/OpenPulse. A `Frame` is a clock plus carrier frequency and phase; a `Port` represents physical I/O and exposes timing granularity. [web:46][web:51][web:57] |
| **Quantum Machines QUA** | `play(operation, element)`, `wait(duration, *elements)`, `align(*elements) -> None`, `frame_rotation(angle, *elements)`. `wait` uses controller clock cycles, traditionally 4 ns. [web:92][web:96] | **Implicit per-element sequential order.** Pulses on the same element depend on source order; different elements run independently until `align`. `wait` behaves like a zero-amplitude play. | One of the purest examples of sequential program order plus explicit synchronization. Deterministic `align` can compile to static waits; if duration is not compile-time-known, hardware synchronization is required and may add gaps. Control-flow and cross-core data dependencies may insert implicit aligns. [web:91][web:95] |
| **Zurich Instruments LabOne Q** | `Experiment`; `section(uid=..., alignment=SectionAlignment.LEFT, length=None, play_after=None, ...)`; sections contain pulses, delays, and nested sections. [web:122][web:124] | **Hierarchical section/alignment model.** `LEFT` schedules direct children ASAP from the section start; `RIGHT` schedules them ALAP against the end. `length` fixes the timing window; otherwise content determines it. `play_after` adds an inter-section ordering constraint. | Very close to the `ScheduleBlock` idea, with explicit section windows and nesting. Alignment applies to direct children and does not automatically propagate into nested sections. Sections may also have offsets, so it is not purely sequential. [web:120][web:125] |
| **Qibo/Qibolab** | `PulseSequence([(channel, Pulse/Delay/Readout/Align), ...])`; `append`, `concatenate`; `Align`; `align(channels)`; `align_to_delays()`. [web:105][web:108][web:109] | Channel-associated instruction sequence. `Delay` advances a lane; `Align` is a synchronization marker that can be compiled into channel delays. Parallelism arises from independent channels and sequence composition rather than global absolute `t0` entries. | Moving toward a compact lane-sequence-plus-alignment representation. The existence of `align_to_delays()` makes the intended lowering explicit. Composition/concatenation semantics require care when sequences have disjoint or partially overlapping channel sets. [web:105][web:114] |
| **OQpy** | `oqpy.Program`, with methods such as `delay(time, qubits_or_frames=())` and `barrier(qubits_or_frames)` plus pulse declarations and play/capture builders. [web:151][web:152] | It is a Python construction API for OpenQASM 3/OpenPulse ASTs, so timing is the target language’s frame-cursor model rather than a separate scheduler IR. | OQpy’s purpose is to emit OpenQASM 3 + OpenPulse using the `openqasm3` and `openpulse` reference AST packages. It does not provide Quantify-style arbitrary operation-reference constraints or Qiskit-style alignment transformations by itself. [web:150] |

---

# 6. Quantify’s relative-reference model in detail

For an operation \(i\) with start \(s_i\), duration \(d_i\), and reference-point coefficient

\[
\alpha(\text{start})=0,\qquad
\alpha(\text{center})=\tfrac12,\qquad
\alpha(\text{end})=1,
\]

a Quantify constraint from operation \(j\) to operation \(i\) is:

\[
s_i + \alpha_i d_i
=
s_j + \alpha_j d_j + \Delta,
\]

where \(\Delta=\texttt{rel\_time}\).

For example:

```python
b = schedule.add(
    operation_b,
    ref_op=a,           # current APIs may call this ref_schedulable
    ref_pt="center",
    ref_pt_new="start",
    rel_time=20e-9,
)
```

means:

\[
s_B = s_A + d_A/2 + 20\text{ ns}.
\]

If no explicit reference is provided under the normal ASAP strategy, the preceding schedulable is used; with omitted points, reference `"end"` and new `"start"` yield ordinary sequential append. [web:263][web:264]

### Known pain points

These are largely consequences visible in the documented API, rather than an official declaration that the model is defective:

1. **Durations must eventually be known.** Center/end constraints cannot become starts until operation durations are available.
2. **References are identity/name-sensitive.** Renaming, cloning, or rewriting operations requires repairing reference edges.
3. **Hierarchy is not transparent.** A nested schedule is treated as one continuous operation; an external operation cannot directly reference an inner operation. [web:259]
4. **Multiple constraints are not pure equalities.** Current documentation says they are resolved by delaying until all constraints are met; exact timing should use exactly one constraint. [web:260]
5. **Cycles and backward references complicate resolution.** ALAP examples directly mutate stored timing constraints, which illustrates that changing scheduling direction is a graph rewrite rather than merely changing a block policy. [web:255]
6. **Equal-time zero-duration operations may need explicit ordering.** Quantify warns that assembly order for zero-duration instructions with identical timing can be wrong and recommends inspecting generated assembly. [web:228]
7. **Hardware grids appear late.** Absolute results may then require quantization or produce errors when NCO operations and latency corrections do not lie on the appropriate timing grid. [web:261]

### Has Quantify moved toward or away from it?

As of **Quantify Scheduler 0.28.1**, it has **not moved away** from the reference-point model. The current `Schedulable` still stores one or more `TimingConstraint` objects with `ref_schedulable`, `ref_pt`, `ref_pt_new`, and `rel_time`; compilation still determines absolute timing from them. [web:225][web:227]

What has changed is ergonomic/default behavior:

- ordinary additions default to back-to-back scheduling;
- explicit constraints are optional;
- newer APIs increasingly use `ref_schedulable` rather than older `ref_op`;
- ASAP/ALAP strategies can provide default reference choices.

That makes simple programs look sequential, but the underlying IR remains a relative constraint graph.

---

# 7. Convergence classification

| Category | Frameworks | Assessment |
|---|---|---|
| **Sequential program order + per-resource delay/barrier/align** | OpenPulse, AWS Braket Pulse, QUA, Pulser, Qibolab, OQpy output | Strong convergence. Each resource has a cursor; ordinary operations advance it; synchronization joins several cursors. |
| **Nestable alignment blocks/sections** | Qiskit `ScheduleBlock`, LabOne Q | Strong convergence on hierarchical scheduling intent. Qiskit adds ASAP, ALAP, serial, equispaced, and callback policies; LabOne Q principally uses left/right-aligned sections with fixed or inferred windows. |
| **Explicit relative-reference-point schedule** | Quantify-scheduler | Retained. References may name arbitrary operations and independently select start/center/end on both sides. |
| **Explicit absolute timeline** | Qiskit `Schedule`; compiled Quantify timing tables; many backend machine schedules | Still important as a lowered/backend IR, even where it is no longer preferred as the authoring representation. |
| **No longer participating as a live hardware pulse framework** | Qiskit Pulse on IBM hardware | Qiskit’s internal move to `ScheduleBlock` was overtaken by Pulse’s complete SDK and hardware removal. |

The trend therefore is **not the disappearance of absolute schedules**. Absolute times remain necessary near hardware. The trend is to stop requiring users and high-level compiler passes to construct them prematurely.

---

# 8. Is Quantify’s reference-point model a portability liability for OpenPulse?

**It is an impedance mismatch, not an inherent loss of portability.**

No primary Quantify or OpenPulse source found here labels the model a “liability.” Technically, however:

- OpenPulse cannot say “place B’s center 10 ns after A’s end” as an unresolved named relation.
- It can only manipulate each frame’s current clock using `play`, `capture`, `delay`, and `barrier`. [web:153]
- Therefore, a Quantify reference graph must be solved before—or during—OpenPulse generation.
- Operation durations, center calculations, negative offsets, resource conflicts, and hardware-grid quantization must all be resolved at that stage.
- The resulting OpenPulse program generally loses the original named-reference and scheduling-intent graph.

That increases compiler complexity and makes late schedule transformations harder, but any finite, static, legal resource schedule can usually be serialized into frame-local delays and plays.

OpenPulse itself was designed to avoid a global absolute clock: the OpenQASM 3 paper says its timing model is relative, with a local zero for each `cal`/`defcal` and relative synchronization through barriers. This was intended to make pulse definitions position-independent. [web:155]

---

# 9. Standard lowering algorithm: reference constraints → OpenPulse

There is no single mandated library routine, but the standard compiler construction is as follows.

## 9.1 Normalize the source graph

For each operation \(i\), determine:

- duration \(d_i\);
- resource set \(R_i\): frames, ports, acquisition paths, or mutually exclusive hardware channels;
- reference constraints;
- phase/frequency state changes;
- hardware time grid and minimum instruction sizes.

Translate every point relation into a start-time equation:

\[
s_i
=
s_j + \alpha_jd_j - \alpha_id_i + \Delta.
\]

For precedence rather than equality constraints, use:

\[
s_i \ge s_j + \alpha_jd_j-\alpha_id_i+\Delta.
\]

## 9.2 Solve timing

1. Topologically order the reference graph where possible.
2. Propagate exact equalities.
3. Treat resource exclusion as disjunctive/precedence constraints:
   \[
   s_i+d_i \le s_j
   \quad\text{or}\quad
   s_j+d_j \le s_i.
   \]
4. For ASAP semantics or multiple lower-bound constraints, compute longest paths/maximal predecessor finish.
5. Detect contradictory equalities, positive cycles, illegal resource overlaps, and unresolved durations.
6. If any start is negative, translate the whole connected schedule:
   \[
   s'_i=s_i-\min_k s_k.
   \]
7. Quantize starts and durations to each port’s hardware grid; then recheck constraints and overlap.

This is essentially the phase performed by Quantify’s `determine_absolute_timing()`. [web:66][web:233]

## 9.3 Convert absolute events into frame-local cursors

Maintain a compile-time cursor \(c_f\) for every OpenPulse frame \(f\), initially zero.

For each frame, sort its events by:

1. start time;
2. required same-time ordering for zero-duration frame/frequency/phase commands;
3. original source order as a deterministic tie-breaker.

For an event on frame \(f\) at absolute time \(s\):

```text
gap = s - c[f]
if gap < 0:
    reject overlap, combine waveforms, or remap resources
if gap > 0:
    emit delay[gap] f
    c[f] += gap

emit play(f, waveform) / capture(...)
c[f] += event_duration
```

OpenPulse defines exactly these cursor effects:

- `delay[d] f` advances \(f\)’s clock by \(d\);
- `play(f, waveform)` advances it by waveform duration;
- `capture` likewise advances the frame;
- `barrier f1, ..., fn` sets all listed clocks to their maximum current clock. [web:135][web:138]

## 9.4 Insert synchronization

For a multi-frame logical boundary at time \(T\):

1. Advance each participating frame to \(T\) with explicit delays, or ensure one has naturally reached \(T\).
2. Emit:

```openqasm
barrier f0, f1, f2;
```

This records the join and ensures all selected clocks equal the latest one.

If the desired next start is strictly later than the maximum cursor, either:

```openqasm
delay[delta] f0, f1, f2;
```

or equivalent individual delays must be emitted before/after the barrier.

A barrier alone cannot represent an arbitrary future offset; it only joins at the current maximum.

## 9.5 Example

Suppose:

- pulse `A` on `f0`: duration 20 ns, starts at 10 ns;
- pulse `B` on `f1`: duration 8 ns;
- `center(B) = end(A) + 4 ns`.

Then:

\[
s_B+4 = (10+20)+4,
\qquad
s_B=30\text{ ns}.
\]

A lowered OpenPulse-like body is:

```openqasm
delay[10ns] f0;
play(f0, A_wf);          // f0 clock = 30 ns

delay[30ns] f1;
play(f1, B_wf);          // f1 clock = 38 ns

barrier f0, f1;          // both clocks = 38 ns
```

The source center/end relationship is no longer present; only its solved consequence remains.

---

# 10. Information resolved or lost during lowering

| Information | Result during lowering |
|---|---|
| Unbound duration parameters used in center/end constraints | Must be bound or transformed into target-supported compile-time expressions. OpenPulse calibration bodies are generally required to have definite compile-time-resolvable duration, including equivalent-duration control-flow branches. [web:144] |
| Named `ref_op`/`ref_schedulable` edges | Lost after conversion to delays and cursor positions unless preserved separately as metadata/debug information. |
| Start/center/end intent | Reduced to numerical starts and gaps. A later optimizer cannot know whether a 10 ns delay represented centering, a minimum latency, or arbitrary padding. |
| ASAP versus ALAP/slack policy | Lost once one concrete placement is selected. |
| Global absolute origin | Usually discarded or normalized to the beginning of the `defcal`; OpenPulse is position-independent relative to that invocation. [web:155] |
| Negative offsets | Must be normalized by shifting the containing region, or rejected if they refer to time before a fixed external boundary. |
| Arbitrary same-frame overlap | Cannot be represented by ordinary sequential `play` statements. The compiler must reject it, sum/mix waveforms into one waveform, or use distinct frames/ports if the hardware permits. |
| Cross-frame simultaneous starts | Preserved with calculated delays and barriers, subject to time-grid quantization. |
| Exact fractional centers | Must be rounded to legal sample/grid positions; the compiler needs a declared rounding and conflict-resolution policy. |
| Runtime-variable control-flow duration | Cannot in general be flattened into static delays. It requires target-side dynamic timing/synchronization support or equal-duration branches. |
| Zero-duration same-time state updates | Require an explicit deterministic source order; absolute timing alone is insufficient. |
| Resource aliasing | Must be resolved: two logical frames may share one physical port and therefore conflict even if the source IR treats them as independent. |

## Bottom line

The emerging portable pulse IR is not “no timing.” It is:

```text
ordered operations on independent resource clocks
+ explicit delay
+ explicit barrier/align
+ optional hierarchical timing windows
```

Absolute schedules remain the natural final machine representation. Quantify’s reference-point graph remains a useful, expressive source IR—especially for centering and experiment construction—but it is less directly isomorphic to OpenPulse than a frame-cursor program. Its portability cost is the need to solve and erase the constraint graph before emission, not an inability to represent the resulting static pulse sequence.

Citations:
[1] https://github.com/Qiskit/qiskit-terra/issues/5679
[2] https://github.com/Qiskit/qiskit/blob/stable/0.21/qiskit/pulse/schedule.py
[3] https://github.com/Qiskit/RFCs
[4] https://github.com/Qiskit/qiskit/issues/9488
[5] https://github.com/Qiskit/qiskit/issues/7004
[6] https://github.com/Qiskit/qiskit-ibm-provider/blob/main/qiskit_ibm_provider/transpiler/passes/scheduling/scheduler.py
[7] https://www.qiskit.org/documentation/locale/ko_KR/apidoc/qpy.html
[8] https://github.com/Qiskit/qiskit/blob/main/qiskit/transpiler/passes/__init__.py
[9] https://github.com/Qiskit/qiskit-terra/issues/7652
[10] https://github.com/Qiskit/qiskit/blob/stable/0.23/qiskit/compiler/assembler.py
[11] https://github.com/Qiskit/qiskit/blob/main/qiskit/providers/backend.py
[12] https://github.com/Qiskit/RFCs/blob/master/0006-rfc-generalized-unroller-and-equivalence-library.md
[13] https://github.com/Qiskit/qiskit/blob/stable/0.19/qiskit/transpiler/passmanager_config.py
[14] https://github.com/Qiskit/qiskit/blob/main/qiskit/compiler/scheduler.py
[15] https://github.com/Qiskit/qiskit/blob/stable/1.1/qiskit/providers/fake_provider/generic_backend_v2.py
[31] https://quantum.cloud.ibm.com/docs/en/api/qiskit/1.2/pulse
[32] https://quantum.cloud.ibm.com/docs/en/api/qiskit/1.1/pulse
[33] https://qiskit.qotlabs.org/docs/api/qiskit/qpy
[34] https://docs.quantum.ibm.com/api/qiskit/0.28/qiskit.pulse.ScheduleBlock
[35] https://quantum.cloud.ibm.com/docs/en/api/qiskit/1.0/pulse
[36] https://github.com/Qiskit/qiskit/blob/stable/0.21/qiskit/pulse/schedule.py
[37] https://qiskit.qotlabs.org/docs/guides/pulse
[38] https://qiskit.qotlabs.org/guides/pulse
[39] https://deepwiki.com/wikiw2025/Qiskitqiskit13552/4.2-pulse-system:-schedule-and-scheduleblock
[40] https://qiskit.qotlabs.org/docs/api/qiskit/release-notes/0.25
[41] https://docs.quantum.ibm.com/api/qiskit/qiskit.pulse.transforms.AlignEquispaced
[42] https://deepwiki.com/wikiw2025/Qiskitqiskit13552/4-circuit-execution-and-hardware-interaction
[43] https://github.com/Qiskit/qiskit-tutorials/blob/master/tutorials/circuits_advanced/06_building_pulse_schedules.ipynb
[44] https://github.com/Qiskit/qiskit
[45] https://docs.quantum.ibm.com/api/qiskit/qiskit.pulse.instructions.Reference
[16] https://quantum.cloud.ibm.com/docs/en/guides/qiskit-2.0
[17] https://qiskit.qotlabs.org/docs/guides/pulse
[18] https://docs.quantum.ibm.com/api/qiskit/1.3/pulse
[19] https://qiskit.qotlabs.org/guides/pulse
[20] https://www.ibm.com/quantum/blog/qiskit-2-0-release-summary
[21] https://github.com/Qiskit/qiskit/issues/13063
[22] https://qiskit.qotlabs.org/docs/api/qiskit/release-notes/2.0
[23] https://quantum.cloud.ibm.com/docs/en/api/qiskit/1.3/qiskit.pulse.instructions.Acquire
[24] https://docs.quantum.ibm.com/api/qiskit/pulse
[25] https://docs.quantum.ibm.com/announcements/product-updates/2024-11-07-fractional-gates
[26] https://github.com/Qiskit/qiskit-ibm-runtime/issues/2091
[27] https://github.com/Qiskit/qiskit/issues/13662
[28] https://qiskit.qotlabs.org/docs/guides/pulse-migration
[29] https://www.ibm.com/quantum/blog/qiskit-1-3-release-summary
[30] https://github.com/Qiskit/qiskit/wiki/Roadmap
[61] https://quantify-os.org/docs/quantify-scheduler/v0.28.1/autoapi/quantify_scheduler/schedules/index.html
[62] https://quantify-os.org/docs/quantify-scheduler/v0.28.0/autoapi/quantify_scheduler/schedules/index.html
[63] https://quantify-os.org/docs/quantify-scheduler/v0.24.0/autoapi/quantify_scheduler/schedules/schedule/index.html
[64] https://quantify-os.org/docs/quantify-scheduler/v0.26.0/autoapi/quantify_scheduler/schedules/index.html
[65] https://quantify-os.org/docs/quantify-scheduler/v0.21.2/autoapi/quantify_scheduler/schedules/schedule/index.html
[66] https://quantify-os.org/docs/quantify-scheduler/v0.28.1/autoapi/quantify_scheduler/compilation/index.html
[67] https://quantify-os.org/docs/quantify-scheduler/v0.26.0/_sources/autoapi/quantify_scheduler/schedules/index.rst.txt
[68] https://quantify-os.org/docs/quantify-scheduler/v0.28.1/autoapi/quantify_scheduler/index.html
[69] https://quantify-os.org/docs/quantify-scheduler/v0.26.0/user/release_notes.html
[70] https://quantify-os.org/docs/quantify-scheduler/dev/user/user_guide.html
[71] https://quantify-os.org/docs/quantify-scheduler/v0.14.0/user_guide.html
[72] https://quantify-os.org/docs/quantify-scheduler/dev/tutorials/Schedules%20and%20Pulses.html
[73] https://quantify-os.org/docs/quantify-scheduler/v0.26.0/_modules/quantify_scheduler/compilation.html
[74] https://quantify-os.org/docs/quantify-scheduler/dev/reference/control_flow.html
[75] https://quantify-os.org/docs/quantify-scheduler/v0.23.0/user/user_guide.html
[76] https://pulser.readthedocs.io/en/v1.0.0/apidoc/core.html
[77] https://pulser.readthedocs.io/en/stable/tutorials/output_mod_eom.html
[78] https://pulser.readthedocs.io/en/v1.2.2/tutorials/output_mod_eom.html
[79] https://pulser.readthedocs.io/en/v1.0.0/tutorials/creating.html
[80] https://pulser.readthedocs.io/en/latest/sequence.html
[81] https://pulser.readthedocs.io/en/stable/genindex.html
[82] https://github.com/pasqal-io/Pulser
[83] https://pulser.readthedocs.io/en/stable/hardware.html
[84] https://github.com/pasqal-io/Pulser/releases
[85] https://github.com/pasqal-io/Pulser/blob/develop/docs/source/index.rst
[86] https://pulser.readthedocs.io/en/v1.1.1/tutorials/creating.html
[87] https://github.com/pasqal-io/Pulser/issues/207
[88] https://pulser.readthedocs.io/en/v1.0.0/intro_rydberg_blockade.html
[89] https://github.com/pasqal-io/Pulser/blob/develop/README.md
[46] https://docs.aws.amazon.com/braket/latest/developerguide/braket-hello-pulse.html
[47] https://docs.aws.amazon.com/pdfs/braket/latest/developerguide/braket-developer-guide.pdf
[48] https://docs.aws.amazon.com/de_de/braket/latest/developerguide/braket-developer-guide.pdf
[49] https://github.com/amazon-braket/amazon-braket-sdk-python/blob/main/CHANGELOG.md
[50] https://docs.aws.amazon.com/zh_cn/braket/latest/developerguide/braket-hello-pulse.html
[51] https://docs.aws.amazon.com/braket/latest/developerguide/braket-pulse-control.html
[52] https://docs.aws.amazon.com/ja_jp/braket/latest/developerguide/braket-pulse-control.html
[53] https://manuals.plus/m/efd2c769950b19ba7353daae8dc76de1d40a856cf9bd1298b3dceb506e9e03ba.pdf
[54] https://docs.aws.amazon.com/zh_tw/braket/latest/developerguide/braket-hello-pulse.html
[55] https://github.com/amazon-braket
[56] https://docs.aws.amazon.com/ko_kr/braket/latest/developerguide/braket-hello-pulse-openpulse.html
[57] https://docs.aws.amazon.com/braket/latest/developerguide/braket-openqasm-device-support.html
[58] https://github.com/amazon-braket/amazon-braket-sdk-python/pulls
[59] https://docs.aws.amazon.com/pt_br/braket/latest/developerguide/braket-hello-pulse.html
[60] https://docs.aws.amazon.com/it_it/braket/latest/developerguide/braket-hello-pulse.html
[90] https://docs.quantum-machines.co/0.1/qm-qua-sdk/docs/API_references/qua/dsl_main/
[91] https://docs.quantum-machines.co/1.3.0/docs/Guides/timing_in_qua/
[92] https://docs.quantum-machines.co/1.2.3/docs/API_references/qua/dsl_main/
[93] https://docs.quantum-machines.co/0.1/qm-qua-sdk/docs/Guides/timing_in_qua/
[94] https://docs.quantum-machines.co/1.1.7/qm-qua-sdk/docs/Guides/timing_in_qua/
[95] https://docs.quantum-machines.co/1.3.1/docs/Guides/timing_in_qua/
[96] https://docs.quantum-machines.co/1.1.5/qm-qua-sdk/docs/API_references/qua/dsl_main/
[97] https://docs.quantum-machines.co/1.3.1/docs/Guides/phase_and_frame/
[98] https://docs.quantum-machines.co/1.3.0/docs/Guides/phase_and_frame/
[99] https://docs.quantum-machines.co/1.2.1/docs/Guides/timing_in_qua/
[100] https://docs.quantum-machines.co/1.1.7/qm-qua-sdk/docs/API_references/qua/dsl_main/
[101] https://docs.quantum-machines.co/1.1.5/qm-qua-sdk/docs/Guides/phase_and_frame/
[102] https://docs.quantum-machines.co/1.1.7/qm-qua-sdk/docs/Introduction/qua_overview/
[103] https://docs.quantum-machines.co/null/docs/Releases/qm_qua_releases/
[104] https://docs.quantum-machines.co/1.2.1/docs/Introduction/qua_overview/
[120] https://docs.zhinst.com/labone_q_user_manual/core/functionality_and_concepts/03_sections_pulses/concepts/index.html
[121] https://docs.zhinst.com/labone_q_user_manual/core/functionality_and_concepts/03_sections_pulses/concepts/01_timing_rules.html
[122] https://docs.zhinst.com/labone_q_user_manual/core/reference/dsl/experiment.html
[123] https://docs.zhinst.com/labone_q_user_manual/core/functionality_and_concepts/03_sections_pulses_and_quantum_operations/concepts/index.html
[124] https://docs.zhinst.com/labone_q_user_manual/core/reference/simple_dsl.html
[125] https://docs.zhinst.com/labone_q_user_manual/core/functionality_and_concepts/03_sections_pulses_and_quantum_operations/concepts/01_timing_rules.html
[126] https://docs.zhinst.com/labone_q_user_manual/core/functionality_and_concepts/04_experiment_sequence/tutorials/06_declarative_dsl.html
[127] https://docs.zhinst.com/labone_q_user_manual/core/functionality_and_concepts/10_advanced_topics/tutorials/05_declarative_dsl.html
[128] https://docs.zhinst.com/labone_q_user_manual/
[129] https://docs.zhinst.com/labone_q_user_manual/applications_library/tutorials/sources/writing_experiments.html
[130] https://docs.zhinst.com/labone_q_user_manual/core/functionality_and_concepts/10_advanced_topics/tutorials/06_context_based_dsl.html
[131] https://docs.zhinst.com/labone_q_user_manual/applications_library/how-to-guides/sources/01_superconducting_qubits/02_pulse_sequences/02_advanced_qubit_experiments/01_randomized_benchmarking.html
[132] https://docs.zhinst.com/labone_q_user_manual/core/getting_started/hello_world.html
[133] https://docs.zhinst.com/labone_q_user_manual/applications_library/how-to-guides/sources/01_superconducting_qubits/01_workflows/07_lifetime_measurement.html
[134] https://docs.zhinst.com/labone_q_user_manual/core/getting_started/introduction.html
[105] https://qibo.science/qibolab/stable/api-reference/qibolab.html
[106] https://qibo.science/qibolab/stable/main-documentation/qibolab.html
[107] https://qibo.science/qibolab/stable/main-documentation/experiment.html
[108] https://qibo.science/qibolab/stable/tutorials/pulses.html
[109] https://github.com/qiboteam/qibolab
[110] https://qibo.science/qibocal/stable/api-reference/qibocal.protocols.ramsey.html
[111] https://qibo.science/qibosoq/stable/getting-started/pulses.html
[112] https://qibo.science/qibocal/stable/_modules/qibocal/protocols/ramsey/acquisition.html
[113] https://github.com/qiboteam/qibolab/blob/main/README.md
[114] https://github.com/qiboteam/qibolab/issues/1042
[115] https://github.com/qiboteam/qibolab/releases
[116] https://qibo.science/qibocal/stable/_modules/qibocal/protocols/coherence/utils.html
[117] https://qibo.science/qibocal/stable/_modules/qibocal/protocols/readout_optimization/resonator_optimization.html
[118] https://qibo.science/qibolab/stable/tutorials/lab.html
[119] https://qibo.science/qibocal/latest/protocols/coherence/index.html
[150] https://github.com/openqasm/oqpy
[151] https://oqpy.readthedocs.io/en/stable/apidocs/oqpy.html
[152] https://oqpy.readthedocs.io/en/latest/apidocs/oqpy.html
[153] https://openqasm.com/versions/3.0/language/openpulse.html
[154] https://zenodo-rdm.web.cern.ch/records/7349266
[155] https://arxiv.org/pdf/2104.14722
[156] https://github.com/openqasm
[157] https://github.com/openqasm/oqpy/issues
[158] https://openqasm.com/language/openpulse.html
[159] https://openqasm.com/versions/3.1/language/openpulse.html
[160] https://openqasm.com/versions/3.0/intro.html
[161] https://docs.oqc.app/qasm3.html
[162] https://zachschoenfeld33.github.io/openqasm/
[163] https://www.linkedin.com/posts/pkaralekas_aws-open-sources-oqpy-to-make-it-easier-to-activity-6989336385237176320-MiMG
[164] https://docs.qbraid.com/v2/pyqasm/user-guide/openpulse
[135] https://openqasm.com/versions/3.0/language/openpulse.html
[136] https://openqasm.com/language/delays.html
[137] https://arxiv.org/pdf/2104.14722
[138] https://openqasm.com/language/openpulse.html
[139] https://openqasm.com/versions/3.0/language/delays.html
[140] https://openqasm.com/versions/3.1/language/openpulse.html
[141] https://openqasm.com/versions/3.1/language/delays.html
[142] https://docs.qbraid.com/v2/pyqasm/user-guide/openpulse
[143] https://docs.oqc.app/qasm3.html
[144] https://openqasm.com/language/pulses.html
[145] https://openqasm.com/language/
[146] https://openqasm.com/versions/3.0/language/pulses.html
[147] https://zachschoenfeld33.github.io/openqasm/
[148] https://arxiv.org/html/2605.30358v1
[149] https://pkg.go.dev/github.com/splch/goqu/pulse
[165] https://github.com/Qiskit/qiskit/blob/stable/0.21/qiskit/pulse/schedule.py
[166] https://docs.quantum.ibm.com/api/qiskit/0.28/qiskit.pulse.ScheduleBlock
[167] https://deepwiki.com/wikiw2025/Qiskitqiskit13552/4-circuit-execution-and-hardware-interaction
[168] https://github.com/Qiskit/qiskit/blob/main/qiskit/circuit/quantumcircuit.py
[169] https://github.com/Qiskit/qiskit-terra/issues/5679
[170] https://quantum.cloud.ibm.com/docs/en/api/qiskit/1.0/qiskit.pulse.Schedule
[171] https://deepwiki.com/wikiw2025/Qiskitqiskit13552/4.2-pulse-system:-schedule-and-scheduleblock
[172] https://quantum.cloud.ibm.com/docs/api/qiskit/1.0/pulse
[173] https://quantum.cloud.ibm.com/docs/en/api/qiskit/1.0/pulse
[174] https://github.com/Qiskit/qiskit
[175] https://quantum.cloud.ibm.com/docs/en/api/qiskit/1.2/pulse
[176] https://github.com/Qiskit/qiskit/blob/stable/0.23/qiskit/compiler/assembler.py
[177] https://github.com/Qiskit/qiskit/blob/main/qiskit/transpiler/passes/scheduling/padding/base_padding.py
[178] https://github.com/Qiskit/qiskit/releases/tag/0.46.0
[179] https://quantum.cloud.ibm.com/docs/en/api/qiskit/1.1/pulse
[180] https://quantum.cloud.ibm.com/docs/en/api/qiskit/release-notes/0.25
[181] https://quantum.cloud.ibm.com/docs/api/qiskit/release-notes/0.25
[182] https://github.com/Qiskit/qiskit-terra/issues/5679
[183] https://zenodo.org/records/4657528
[184] https://qiskit.qotlabs.org/docs/api/qiskit/release-notes/0.17
[185] https://www.wikidata.org/wiki/Q70490607
[186] https://quantum.cloud.ibm.com/docs/api/qiskit/release-notes/0.44
[187] https://github.com/wshanks/qiskit-terra
[188] https://github.com/Qiskit/RFCs
[189] https://quantum.cloud.ibm.com/docs/api/qiskit/release-notes/0.33
[190] https://quantum.cloud.ibm.com/docs/api/qiskit/1.1/qiskit.pulse.ScheduleBlock
[191] https://quantum.cloud.ibm.com/docs/en/api/qiskit/1.2/qiskit.pulse.ScheduleBlock
[192] https://qiskit-community.github.io/qiskit-dynamics/_modules/qiskit_dynamics/solvers/solver_classes.html
[193] https://pypi.org/org/qiskit/
[194] https://github.com/Qiskit/qiskit/releases
[195] https://github.com/Qiskit/qiskit/blob/stable/0.21/qiskit/pulse/schedule.py
[196] https://quantum.cloud.ibm.com/docs/api/qiskit/1.0/pulse
[197] https://docs.quantum.ibm.com/api/qiskit/qiskit.pulse.transforms.AlignEquispaced
[198] https://docs.quantum.ibm.com/api/qiskit/0.28/qiskit.pulse.ScheduleBlock
[199] https://github.com/Qiskit/qiskit/blob/main/qiskit/transpiler/passes/calibration/rzx_builder.py
[200] https://github.com/Qiskit/qiskit/blob/main/qiskit/circuit/parameterexpression.py
[201] https://github.com/Qiskit/qiskit
[202] https://github.com/Qiskit/qiskit/blob/main/qiskit/compiler/transpiler.py
[203] https://github.com/Qiskit/qiskit/blob/stable/0.23/qiskit/qobj/__init__.py
[204] https://github.com/Qiskit/qiskit/blob/stable/0.23/qiskit/compiler/assembler.py
[205] https://github.com/Qiskit/qiskit/blob/main/qiskit/circuit/library/pauli_evolution.py
[206] https://github.com/Qiskit/qiskit/blob/stable/0.24/qiskit/dagcircuit/dagcircuit.py
[207] https://qiskit.qotlabs.org/
[208] https://github.com/Qiskit/qiskit/blob/stable/0.21/qiskit/algorithms/optimizers/optimizer.py
[209] https://github.com/Qiskit/qiskit/blob/stable/1.2/qiskit/circuit/instruction.py
[210] https://qiskit-community.github.io/qiskit-dynamics/apidocs/pulse.html
[211] https://qiskit-community.github.io/qiskit-dynamics/_modules/qiskit_dynamics/backend/dynamics_backend.html
[212] https://qiskit-community.github.io/qiskit-dynamics/tutorials/qiskit_pulse.html
[213] https://qiskit-community.github.io/qiskit-dynamics/stable/0.4/_modules/qiskit_dynamics/solvers/solver_classes.html
[214] https://github.com/qiskit-community/qiskit-dynamics
[215] https://quantum.cloud.ibm.com/docs/guides/pulse-migration
[216] https://qiskit-community.github.io/qiskit-dynamics/stubs/qiskit_dynamics.solvers.Solver.html
[217] https://quantum.cloud.ibm.com/docs/en/guides/pulse-migration
[218] https://qiskit-community.github.io/qiskit-dynamics/_modules/qiskit_dynamics/pulse/pulse_to_signals.html
[219] https://qiskit-community.github.io/qiskit-dynamics/tutorials/
[220] https://qiskit-community.github.io/qiskit-dynamics/stable/tutorials/qiskit_pulse.html
[221] https://qiskit-community.github.io/qiskit-dynamics/stable/0.4/_modules/qiskit_dynamics/pulse/pulse_to_signals.html
[222] https://docs.quantum.ibm.com/announcements/product-updates/2024-11-07-fractional-gates
[223] https://qiskit-community.github.io/qiskit-dynamics/stubs/qiskit_dynamics.backend.DynamicsBackend.html
[224] https://github.com/qiskit-community/qiskit-dynamics/releases
[255] https://quantify-os.org/docs/quantify-scheduler/v0.26.0/user/release_notes.html
[256] https://quantify-os.org/docs/quantify-scheduler/v0.26.0/autoapi/quantify_scheduler/schedules/index.html
[257] https://quantify-os.org/docs/quantify-scheduler/v0.24.0/autoapi/quantify_scheduler/schedules/schedule/index.html
[258] https://quantify-os.org/docs/quantify-scheduler/v0.28.0/autoapi/quantify_scheduler/schedules/index.html
[259] https://quantify-os.org/docs/quantify-scheduler/dev/reference/control_flow.html
[260] https://quantify-os.org/docs/quantify-scheduler/v0.26.0/_sources/autoapi/quantify_scheduler/schedules/index.rst.txt
[261] https://quantify-os.org/docs/quantify-scheduler/dev/user/changelog.html
[262] https://quantify-os.org/docs/quantify-scheduler/v0.21.2/autoapi/quantify_scheduler/schedules/schedule/index.html
[263] https://quantify-os.org/docs/quantify-scheduler/v0.28.1/autoapi/quantify_scheduler/index.html
[264] https://quantify-os.org/docs/quantify-scheduler/v0.28.1/autoapi/quantify_scheduler/compilation/index.html
[265] https://quantify-os.org/docs/quantify-scheduler/v0.13.0/changelog.html
[266] https://quantify-os.org/docs/quantify-scheduler/v0.26.0/_modules/quantify_scheduler/compilation.html
[267] https://quantify-os.org/docs/quantify-scheduler/v0.14.0/user_guide.html
[268] https://quantify-os.org/docs/quantify-scheduler/v0.22.3/user/release_notes.html
[269] https://quantify-os.org/docs/quantify-scheduler/dev/tutorials/Schedules%20and%20Pulses.html
[225] https://quantify-os.org/docs/quantify-scheduler/v0.28.1/autoapi/quantify_scheduler/schedules/index.html
[226] https://quantify-os.org/docs/quantify-scheduler/v0.21.2/autoapi/quantify_scheduler/schedules/schedule/index.html
[227] https://quantify-os.org/docs/quantify-scheduler/v0.28.1/autoapi/quantify_scheduler/compilation/index.html
[228] https://quantify-os.org/docs/quantify-scheduler/dev/reference/control_flow.html
[229] https://quantify-os.org/docs/quantify-scheduler/v0.28.0/autoapi/quantify_scheduler/schedules/index.html
[230] https://quantify-os.org/docs/quantify-scheduler/v0.26.0/user/release_notes.html
[231] https://quantify-os.org/docs/quantify-scheduler/dev/user/user_guide.html
[232] https://quantify-os.org/docs/quantify-scheduler/v0.14.0/user_guide.html
[233] https://quantify-os.org/docs/quantify-scheduler/v0.26.0/_modules/quantify_scheduler/compilation.html
[234] https://quantify-os.org/docs/quantify-scheduler/v0.26.0/autoapi/quantify_scheduler/schedules/index.html
[235] https://quantify-os.org/docs/quantify-scheduler/v0.27.1/genindex.html
[236] https://quantify-os.org/docs/quantify-scheduler/v0.13.0/changelog.html
[237] https://quantify-os.org/docs/quantify-scheduler/v0.28.1/autoapi/quantify_scheduler/schedules/schedule/index.html
[238] https://quantify-os.org/docs/quantify-scheduler/v0.26.0/_sources/autoapi/quantify_scheduler/schedules/index.rst.txt
[239] https://quantify-os.org/docs/quantify-scheduler/v0.25.2/autoapi/quantify_scheduler/qblox/operations/index.html
[240] https://quantify-os.org/docs/quantify-scheduler/dev/reference/control_flow.html
[241] https://github.com/quantify-os/quantify-scheduler/blob/main/AUTHORS.md
[242] https://github.com/quantify-os/quantify-scheduler/actions
[243] https://github.com/quantify-os/quantify-scheduler/pulls
[244] https://quantify-os.org/docs/quantify-scheduler/v0.28.1/autoapi/quantify_scheduler/schedules/index.html
[245] https://quantify-os.org/docs/quantify-scheduler/v0.28.1/autoapi/quantify_scheduler/helpers/schedule/index.html
[246] https://quantify-os.org/docs/quantify-scheduler/dev/user/user_guide.html
[247] https://quantify-os.org/docs/quantify-scheduler/dev/_modules/quantify_scheduler/schedules/trace_schedules.html
[248] https://quantify-os.org/docs/quantify-scheduler/dev/_modules/quantify_scheduler/schedules/spectroscopy_schedules.html
[249] https://quantify-os.org/docs/quantify-scheduler/v0.28.1/autoapi/quantify_scheduler/schedules/trace_schedules/index.html
[250] https://quantify-os.org/docs/quantify-scheduler/dev/tutorials/Schedules%20and%20Pulses.html
[251] https://quantify-os.org/docs/quantify-scheduler/v0.14.0/user_guide.html
[252] https://quantify-os.gitlab.io/quantify-scheduler/_modules/quantify_scheduler/operations/pulse_library.html
[253] https://quantify-os.org/docs/quantify-scheduler/v0.24.0/autoapi/quantify_scheduler/schedules/schedule/index.html
[254] https://quantify-os.org/docs/quantify-scheduler/v0.27.1/user/about.html
[300] https://github.com/Qiskit/qiskit/issues/13063
[301] https://github.com/Qiskit/qiskit/blob/main/qiskit/scheduler/schedule_circuit.py
[302] https://qiskit-community.github.io/qiskit-experiments/release_notes.html
[303] https://qiskit.qotlabs.org/docs/migration-guides/pulse-migration
[304] https://qiskit.qotlabs.org/guides/pulse
[305] https://qiskit.qotlabs.org/docs/guides/pulse
[306] https://github.com/qiskit-community/qiskit-dynamics
[307] https://www.ibm.com/quantum/blog/qiskit-1-3-release-summary
[308] https://github.com/Qiskit/qiskit?files=1
[309] https://github.com/qiskit-community/Qiskit-Resources
[310] https://github.com/Qiskit/qiskit/issues/4074
[311] https://github.com/Qiskit/qiskit/blob/main/qiskit/providers/backend.py
[312] https://docs.quantum.ibm.com/api/qiskit/dev/scheduler
[313] https://github.com/Qiskit/qiskit/blob/main/qiskit/pulse/builder.py
[314] https://github.com/qiskit-community/awesome-qiskit
[285] https://github.com/Qiskit/qiskit
[286] https://zenodo.org/records/14237188
[287] https://www.wikidata.org/wiki/Q70490607
[288] https://github.com/qiskit/qiskit/releases
[289] https://github.com/Qiskit/qiskit/wiki/Roadmap
[290] https://github.com/Qiskit/qiskit/releases
[291] https://github.com/qiskit
[292] https://github.com/Qiskit/qiskit/milestones?state=closed
[293] https://github.com/qiskit-community/qiskit-experiments
[294] https://github.com/orgs/Qiskit/repositories
[295] https://pypi.org/org/qiskit/
[296] https://quantum.cloud.ibm.com/docs/en/api/qiskit/release-notes/index
[297] https://github.com/Qiskit/qiskit/blob/main/MAINTAINING.md
[298] https://qiskit.qotlabs.org/guides/latest-updates
[299] https://github.com/Qiskit/qiskit-serverless/releases
[270] https://quantum.cloud.ibm.com/docs/guides/pulse-migration
[271] https://qiskit.qotlabs.org/docs/api/qiskit/release-notes/2.0
[272] https://qiskit-community.github.io/qiskit-experiments/release_notes.html
[273] https://quantum.cloud.ibm.com/docs/en/guides/pulse-migration
[274] https://qiskit.qotlabs.org/docs/guides/pulse
[275] https://qiskit.qotlabs.org/guides/pulse
[276] https://quantum.cloud.ibm.com/docs/api/qiskit/1.4/qiskit.circuit.QuantumCircuit
[277] https://github.com/Qiskit/qiskit/issues/13662
[278] https://quantum.cloud.ibm.com/docs/en/api/qiskit/1.3/qiskit.circuit.library.WeightedAdder
[279] https://docs.quantum.ibm.com/api/qiskit/qiskit.transpiler.passes.PulseGates
[280] https://qiskit.qotlabs.org/docs/guides/qiskit-2.0
[281] https://quantum.cloud.ibm.com/docs/api/qiskit/1.4/qiskit.transpiler.Target
[282] https://arxiv.org/html/2605.15233v3
[283] https://github.com/Qiskit/qiskit-ibm-runtime/issues/2091
[284] https://www.ibm.com/quantum/blog/qiskit-1-3-release-summary
[315] https://quantum.cloud.ibm.com/docs/en/api/qiskit/1.0/pulse
[316] https://github.com/Qiskit/qiskit-terra/issues/5679
[317] https://quantum.cloud.ibm.com/docs/api/qiskit/1.0/pulse
[318] https://deepwiki.com/wikiw2025/Qiskitqiskit13552/4.2-pulse-system:-schedule-and-scheduleblock
[319] https://qiskit-community.github.io/qiskit-experiments/stable/0.5/_modules/qiskit_experiments/test/pulse_backend.html
[320] https://qiskit-community.github.io/qiskit-dynamics/_modules/qiskit_dynamics/backend/dynamics_backend.html
[321] https://qiskit-community.github.io/qiskit-dynamics/apidocs/pulse.html
[322] https://github.com/Qiskit/qiskit/blob/stable/0.21/qiskit/pulse/schedule.py
[323] https://deepwiki.com/wikiw2025/Qiskitqiskit13552/4.4-pulse-to-qobj-assembly
[324] https://qiskit.qotlabs.org/guides/pulse
[325] https://quantum.cloud.ibm.com/docs/en/api/qiskit/1.2/qiskit.pulse.ScheduleBlock
[326] https://qiskit.qotlabs.org/docs/guides/pulse
[327] https://quantum.cloud.ibm.com/docs/api/qiskit/1.1/qiskit.pulse.ScheduleBlock
[328] https://qiskit-community.github.io/qiskit-dynamics/userguide/how_to_use_pulse_schedule_for_jax_jit.html
[329] https://quantum.cloud.ibm.com/docs/guides/qiskit-runtime-circuit-timing
[330] https://quantum.cloud.ibm.com/docs/api/qiskit/1.4/qiskit.pulse.Schedule
[331] https://quantum.cloud.ibm.com/docs/en/api/qiskit/1.2/pulse
[332] https://quantum.cloud.ibm.com/docs/en/api/qiskit/1.2/compiler
[333] https://quantum.cloud.ibm.com/docs/en/api/qiskit/1.2/qiskit.pulse.ScheduleBlock
[334] https://quantum.cloud.ibm.com/docs/en/api/qiskit/1.2
[335] https://quantum.cloud.ibm.com/docs/en/api/qiskit/1.0/qiskit.pulse.Schedule
[336] https://quantum.cloud.ibm.com/docs/en/api/qiskit/1.2/qiskit.dagcircuit.DAGCircuit
[337] https://quantum.cloud.ibm.com/docs/en/api/qiskit/1.2/qiskit.circuit.QuantumCircuit
[338] https://quantum.cloud.ibm.com/docs/en/api/qiskit/1.2/qiskit.providers.fake_provider.GenericBackendV2
[339] https://quantum.cloud.ibm.com/docs/en/api/qiskit/1.2/qiskit.circuit.library.PhaseOracle
[340] https://quantum.cloud.ibm.com/docs/en/api/qiskit/1.2/qiskit.circuit.library.EfficientSU2
[341] https://quantum.cloud.ibm.com/docs/en/api/qiskit/1.2/qiskit.pulse.library.Drag
[342] https://quantum.cloud.ibm.com/docs/en/api/qiskit/1.1/qiskit.pulse.instructions.Play
[343] https://quantum.cloud.ibm.com/docs/en/api/qiskit/1.2/qiskit.circuit.library.VBERippleCarryAdder
[344] https://quantum.cloud.ibm.com/docs/en/api/qiskit/1.2/qiskit.pulse.library.gaussian_square_echo
[345] https://docs.aws.amazon.com/braket/latest/developerguide/braket-hello-pulse.html
[346] https://amazon-braket-sdk-python.readthedocs.io/en/stable/_apidoc/braket.pulse.pulse_sequence.html
[347] https://docs.aws.amazon.com/zh_cn/braket/latest/developerguide/braket-hello-pulse.html
[348] https://docs.aws.amazon.com/pdfs/braket/latest/developerguide/braket-developer-guide.pdf
[349] https://aws.amazon.com/blogs/quantum-computing/amazon-braket-launches-braket-pulse-to-develop-quantum-programs-at-the-pulse-level/
[350] https://docs.aws.amazon.com/it_it/braket/latest/developerguide/braket-hello-pulse.html
[351] https://docs.aws.amazon.com/ja_jp/braket/latest/developerguide/braket-hello-pulse.html
[352] https://docs.aws.amazon.com/braket/latest/developerguide/braket-pulse-control.html
[353] https://docs.aws.amazon.com/zh_tw/braket/latest/developerguide/braket-hello-pulse.html
[354] https://github.com/amazon-braket/amazon-braket-sdk-python/pulls
[355] https://raw.githubusercontent.com/amazon-braket/amazon-braket-sdk-python/gen_ai/doc/genai_cheat_sheet.md
[356] https://amazon-braket-sdk-python.readthedocs.io/en/latest/
[357] https://amazon-braket-sdk-python.readthedocs.io/en/stable/
[358] https://github.com/amazon-braket/amazon-braket-sdk-python/issues/974
[359] https://github.com/amazon-braket/amazon-braket-sdk-python/blob/main/CHANGELOG.md
