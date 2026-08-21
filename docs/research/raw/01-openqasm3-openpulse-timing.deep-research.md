# OpenQASM 3 / OpenPulse timing and scheduling reference

## Executive summary

OpenQASM 3 is **not an absolute-time event-list IR**. Its timing model is resource-relative:

- Operations are ordered on the qubits or frames they use.
- Idle time may be implicit and therefore movable by optimization.
- `delay[...]` makes idle time explicit.
- `barrier` creates an ordering/synchronization constraint without committing to a nonzero duration.
- `stretch` represents compile-time unknown, nonnegative timing slack that must be solved after calibrated instruction durations are known.
- `box` establishes a scheduling and optimization boundary and may impose an exact total duration.
- OpenPulse gives each `frame` an implicitly maintained time cursor. `play`, `capture`, `delay`, and `barrier` advance or synchronize those cursors; there is no standard `at 123 ns` instruction. The OpenQASM paper states: “Within a program, there is no explicit reference to a global clock.” [web:201]

OpenPulse remains explicitly marked: “**The OpenPulse grammar is still in active development and is liable to change.**” [web:125]

---

# 1. OpenQASM 3 timing

## 1.1 Core grammar

The reference ANTLR grammar contains:

```antlr
barrierStatement
    : BARRIER gateOperandList? SEMICOLON
    ;

boxStatement
    : BOX designator? scope
    ;

delayStatement
    : DELAY designator gateOperandList? SEMICOLON
    ;
```

and:

```antlr
scope
    : LBRACE statementOrScope* RBRACE
    ;
```

The `durationof` expression is:

```antlr
DURATIONOF LPAREN scope RPAREN
```

The repository describes this ANTLR grammar as the official reference grammar for syntactic validity. [web:11][web:263]

Typical concrete syntax is therefore:

```qasm
duration t = 100ns;
delay[t] q[0];
barrier q;
box {
    x q[0];
}
box[500ns] {
    x q[0];
}
duration tx = durationof({
    x q[0];
});
```

A bracketed timing argument is called a *designator* in the grammar. Timing arguments use square brackets so they are distinct from ordinary gate/function arguments. [web:55]

---

## 1.2 `duration`

The 3.1 specification says:

> “The `duration` type is used denote increments of time. Durations are real numbers that are manipulated at compile time.”

Supported literal units are:

| Unit | Meaning |
|---|---|
| `ns` | nanoseconds |
| `µs` | microseconds |
| `us` | ASCII spelling of microseconds |
| `ms` | milliseconds |
| `s` | seconds |
| `dt` | one backend waveform-sample period |

A unit may be attached or separated by spaces/tabs: `1000ms` and `1000 ms` are equivalent. `dt` is backend dependent and is “equivalent to the duration of one waveform sample on the backend.” [web:258][web:269]

Examples:

```qasm
duration a = 20ns;
duration b = 7dt;
duration c = a + 5ns;
duration d = 3 * a;
float ratio = c / a;
```

The allowed arithmetic is principally:

- `duration + duration -> duration`
- `duration - duration -> duration`
- scalar multiplication or division -> `duration`
- `duration / duration ->` machine-precision `float`

Duration expressions may be negative as intermediate compile-time values, but a negative operational duration is invalid. The live specification explicitly calls out negative durations used for timed gates or boxes as errors; an implementation must likewise reject a negative realized delay. All duration operations occur at compile time because all durations, including stretches, must ultimately become constants. [web:269]

There is no general cast to or from `duration`. [web:20]

---

## 1.3 `durationof(...)`

`durationof` takes a brace-enclosed scope:

```qasm
duration t = durationof({
    x q[0];
    cx q[0], q[1];
});
```

It returns the compiled duration of that scope. This is *referential timing*: the result depends on the selected calibrations, target, and compilation context rather than merely on source-level instruction count. The type documentation describes it as “an intrinsic function used to reference the duration of a calibrated gate.” [web:261]

For example:

```qasm
duration tx = durationof({
    x q[0];
});

delay[tx] q[1];
```

The body must have a statically resolvable duration. In particular, every `defcal` body must have a definite duration known at compile time; branches in a `defcal` must have definite and equivalent durations, and loops must have a statically resolvable total duration. This restriction exists in part so `durationof(...)` can be resolved. [web:259]

### Important limitation

`durationof` is not a run-time clock query. It does not return a current timestamp, and it does not read a frame’s current `time`. It asks the compiler for the duration of a statically analyzable block.

---

## 1.4 `delay[t] q;`

Canonical forms are:

```qasm
delay[20ns] q[0];
delay[t] q[0], q[1];
delay[stretch_value] q;
```

An explicit delay:

1. applies the identity operation ideally;
2. occupies the named resources for the stated duration;
3. makes that idle interval semantically significant; and
4. prevents otherwise legal commutation across it.

The specification says:

> “Even though a `delay` instruction implements the identity operator in the ideal case, it is intended to provide explicit timing. Therefore an explicit `delay` instruction will prevent commutation of gates that would otherwise commute.” [web:288]

By contrast, an **implicit** idle interval is not part of the circuit’s stated timing intent. The specification’s example explains that an `rz` may commute through an implicit idle interval, but not through the corresponding explicit delay. [web:288][web:289]

### Multi-resource delay

A multi-qubit delay is not shorthand for independent one-qubit delays:

> “A multi-qubit `delay` instruction is *not* equivalent to multiple single-qubit `delay` instructions. Instead a multi-qubit delay acts as a synchronization point on the qubits, where the delay begins from the latest non-idle time across all qubits, and ends simultaneously across all qubits.” [web:55]

Thus:

```qasm
delay[100ns] q[0], q[1];
```

means approximately:

```text
start = max(current_time(q[0]), current_time(q[1]))
end(q[0]) = end(q[1]) = start + 100 ns
```

It does **not** mean “advance each qubit independently by 100 ns from its own cursor.”

---

## 1.5 `barrier`

A barrier has zero nominal duration but establishes ordering and synchronization constraints:

```qasm
barrier q[0], q[1];
```

The OpenQASM paper characterizes it as similar to `delay[0]`, but with a critical intent distinction:

- `barrier` says operations must not be reordered across the boundary, while leaving a later scheduler freedom to insert timing;
- `delay[0]` belongs to an explicitly scheduled description, indicating that the user has committed to the corresponding timing relation. [web:289]

At pulse level, a frame barrier sets all listed frame clocks to their maximum current time:

```text
T = max(frame_i.time)
frame_i.time = T, for every listed frame
```

The OpenPulse specification states that frame clocks “are aligned to the latest time” of all listed frames. [web:198][web:200]

---

## 1.6 What happens when no delay is written?

There are two levels of answer.

### Dependency semantics

On a particular resource, an instruction cannot start before preceding operations on that resource and its classical dependencies have completed. A multi-resource operation starts no earlier than the latest availability of all resources it uses.

An ordinary scheduler normally materializes this as an **as-soon-as-possible**, or ASAP, schedule:

```text
start(I) = max(end(P) for all resource/data predecessors P of I)
```

### Language-design-intent semantics

OpenQASM source without explicit timing does not generally freeze every idle interval. The specification expressly distinguishes an implicit delay from an explicit one: an implicit idle interval is not part of the circuit description and does not itself prevent commutation. [web:288]

Therefore “the instruction starts immediately” should not be interpreted as an immutable source-level timestamp. The precise rule is:

- the operation must respect program/data/resource dependencies;
- absent explicit `delay`, `barrier`, `box`, or other constraints, the compiler may commute and reschedule it;
- once lowered to a concrete schedule, an ASAP scheduler commonly selects the earliest legal start.

OpenPulse is more concrete: `play(frame, waveform)` starts at the frame’s **current** `time`, and then advances that time. [web:393]

---

## 1.7 `box`

### Syntax

```qasm
box {
    // statements
}

box[500ns] {
    // statements
}
```

The specification says:

> “We introduce a `box` statement for scoping the timing of a particular part of the circuit.”

and:

> “A boxed subcircuit is different from a `gate` or `def` subroutine, in that it is merely an enclosure to a piece of code within the larger scope which constrains it.” [web:76]

### Optimization boundary

Within a box:

- operations may be optimized;
- operations outside the box may move from one side of the box to the other if otherwise legal;
- operations may **not** be moved into or out of the box.

The specification states:

> “optimizing operations within a `box` definition is permitted, and optimizations that move operations from one side to the other side of a box are permitted, but moving operations either into or out of the box as part of an optimization is forbidden.” [web:76]

This is not equivalent to a subroutine call. A box does not define a reusable operation, parameter-binding convention, or separate linkage object.

### Resource participation and synchronization

A box has common entry and exit boundaries for the resources it uses. A resource with no substantive operation may be made a participant with the explicit `nop` instruction; the spec notes that such a `nop` counts as a use, “causing the qubit to be synchronized with the rest of the box at entry and exit.” [web:49][web:80]

### Timed box

For:

```qasm
box[500ns] {
    // body
}
```

the bracketed designator is a hard total-duration constraint. The specification says it is used:

> “to put hard constraints on the execution of a particular sub-circuit by requiring it to have the assigned duration.” [web:258]

Let:

- \(D_\text{natural}\) be the body duration with all stretches hypothetically set to zero;
- \(D_\text{box}\) be the requested duration.

Then:

- if \(D_\text{natural} > D_\text{box}\), compilation fails;
- if stretches occur in the body, they can absorb \(D_\text{box}-D_\text{natural}\);
- if the body cannot satisfy the duration and alignment constraints, the program is unschedulable;
- a stretch-valued box duration can itself be constrained by an enclosing schedule.

The paper says the natural duration must not exceed the declared box duration and that stretches inside fill the difference. [web:221][web:468]

### A box does not itself mean ASAP or ALAP

A frequent misreading is:

```qasm
box[500ns] {
    x q[0];
}
```

means either “put `x` at the left edge” or “put `x` at the right edge.” The specification does not define that blanket placement rule. The box fixes boundaries and optionally duration; placement inside those boundaries comes from:

- dependencies,
- explicit delays,
- stretches,
- barriers,
- and target scheduling rules.

If the body leaves unconstrained slack, the language does not provide a universal left/right/center default that portable programs should rely on.

---

## 1.8 ASAP versus ALAP

The relevant OpenQASM mechanism is placement of stretch slack.

### ASAP / left alignment

Put stretch *after* the operation:

```qasm
stretch s;

barrier q[0], q[1];

x q[0];
delay[s] q[0];

long_gate q[1];

barrier q[0], q[1];
```

The compiler minimizes `s`, but must satisfy synchronization at the ending barrier. Consequently `x` remains at the earliest legal point and any required slack follows it.

The specification explicitly presents this pattern for left alignment. [web:273][web:468]

### ALAP / right alignment

Put stretch *before* the operation:

```qasm
stretch s;

box[500ns] {
    delay[s] q[0];
    x q[0];
}
```

The stretch expands to consume available leading slack, placing `x` as late as the constraints permit. The paper describes this as:

> “We use stretchy delays for this purpose, which enact a ‘as late as possible’ schedule.” [web:305]

That quotation refers to the appropriate stretchy-delay construction, not to every instruction in every box.

### Fractional placement

Relative stretch coefficients express proportional positioning:

```qasm
stretch s;

barrier q;
delay[s] q[2];
u(pi/4, 0, pi/2) q[2];
delay[2*s] q[2];
barrier q;
```

This positions the gate at the one-third point of the available slack: one share before and two shares after. The paper gives this exact design pattern. [web:274]

---

# 2. `stretch` in detail

## 2.1 Type and semantics

The 3.1 specification says:

> “`stretch` type … is a sub-type of `duration`.”

and:

> “Stretchable durations have variable non-negative duration that are permitted to grow as necessary to satisfy constraints.”

and:

> “Stretch variables are resolved at compile time into target-appropriate durations that satisfy a user’s specified design intent.” [web:63]

Declaration:

```qasm
stretch s;
stretch a, b, c;
```

Conceptually, every stretch has:

- lower bound zero;
- natural duration zero;
- an unknown value until instruction/calibration durations are known;
- a compiler objective to keep it as small as possible subject to all constraints.

An instruction whose duration contains stretch is itself “stretchy”:

```qasm
delay[s] q[0];
delay[2*s + 20ns] q[1];
```

A gate or enclosing box containing stretchy operations can expose a stretchy total duration to its enclosing context. [web:61]

---

## 2.2 Constraint system

After calibration selection and duration lowering, the compiler introduces variables for unresolved stretches and resource start/end times.

Typical constraints include:

### Nonnegativity

\[
s_i \ge 0
\]

### Sequential resource order

For operation \(B\) following \(A\) on a common resource:

\[
t_B \ge t_A + d_A
\]

### Delay duration

For:

```qasm
delay[a*s + d] q;
```

\[
d_\text{delay}=a s+d
\]

and its realized duration must be nonnegative and target representable.

### Barrier synchronization

For all resources participating in a barrier:

\[
t_\text{after} \ge t_{\text{before},i}
\]

with the synchronized cursor chosen at the latest incoming resource time.

### Fixed box duration

For a box beginning at \(T_0\) and ending at \(T_1\):

\[
T_1-T_0=D_\text{box}
\]

### Equal-end alignment

Where separate resource paths are explicitly constrained to fill a common span, their accumulated durations must satisfy equality at the synchronization boundary.

---

## 2.3 Solver objective

The OpenQASM paper formalizes stretch resolution as a **lexicographic multi-objective linear program**:

\[
\text{lexicographically minimize }
c_1^\mathsf{T}x,\,
c_2^\mathsf{T}x,\ldots,c_m^\mathsf{T}x
\]

subject to:

\[
Ax \le b,\qquad x\ge0.
\]

The paper calls this the “stretch problem” and says stretches are resolved in one late-stage pass into explicit delays, thereby producing a complete concrete schedule. [web:62]

Consequences for an IR/compiler:

1. Stretch expressions must remain linear.
2. Products of two stretches are not valid LP expressions.
3. Division by a stretch is not generally resolvable as a linear expression.
4. The solver runs only after gate/measurement calibrations and target durations are selected.
5. Failure of the LP means the timing program is unsatisfiable.
6. Quantization to `dt` may require an integer or mixed-integer post-processing step in a real backend, even though the language paper describes the abstract problem as linear programming.

The live specification defines the semantics but does not prescribe one implementation algorithm or a universal rounding/distribution policy.

---

## 2.4 Current specification and implementation status

| Environment | `stretch` status |
|---|---|
| OpenQASM 3.1 specification | Normatively present as a subtype of `duration`; compile-time resolved, nonnegative timing slack. [web:63] |
| OpenQASM live specification | Still present; the repository identifies the current language version as 3.1. [web:70] |
| Qiskit SDK 2.x IR | Initial support exists; `stretch` durations for `Delay` were added in Qiskit 2.0. [web:65][web:213] |
| Qiskit Runtime | Experimental and restricted: at most one stretch per mutually exclusive qubit set in a barrier region, no reuse across barrier regions, expressions limited to `X*stretch + Y`, and one stretch variable per expression. [web:65] |
| Qiskit OpenQASM importer | Incomplete: IBM’s feature table says the importer does not parse OpenQASM declarations of `duration` or `stretch` in the cited importer version. [web:69] |
| Qiskit Pulse | Unrelated to the Qiskit 2.x circuit-level stretch support; `qiskit.pulse` was completely removed in Qiskit 2.0. [web:214][web:215] |

Qiskit Runtime additionally documents that any quantization remainder is placed into the first delay using the stretch. That is a Qiskit policy, not a portable OpenQASM language rule. [web:65]

---

# 3. Alignment and reference points

## 3.1 Is there a built-in alignment construct?

No standard OpenQASM 3.1 syntax directly denotes:

- `align_left`
- `align_right`
- `align_center`
- `center_of(operation)`
- an operation anchor/reference point
- an absolute start timestamp

The accepted grammar has `box`, optional box duration, `delay`, `barrier`, `stretch`, and `durationof`, but no alignment keyword or anchor operand. [web:11][web:83]

OpenQASM alignment is expressed through timing equations encoded using delays, stretch coefficients, barriers, boxes, and known or referential durations.

This differs from historical Qiskit Pulse `ScheduleBlock` alignment transforms, which explicitly had `AlignLeft`, `AlignRight`, `AlignSequential`, `AlignEquispaced`, and `AlignFunc`. Those were framework constructs, not OpenQASM keywords. [web:445]

---

## 3.2 Center-aligning two pulses

Assume `A` and `B` are on distinct frames, their durations are known as `dA` and `dB`, and `dA >= dB`:

```qasm
barrier fA, fB;

play(fA, A);
delay[(dA - dB) / 2] fB;
play(fB, B);

barrier fA, fB;
```

Then:

\[
\operatorname{start}(B)
 = \operatorname{start}(A)+\frac{d_A-d_B}{2}
\]

and:

\[
\operatorname{center}(B)
 = \operatorname{center}(A).
\]

If `dB > dA`, delay `fA` instead.

A target-independent stretch formulation is:

```qasm
stretch s;

barrier fA, fB;

play(fA, A);

delay[s] fB;
play(fB, B);
delay[s] fB;

barrier fA, fB;
```

Subject to the equal-span constraints, the solver obtains:

\[
2s+d_B=d_A.
\]

This only has a nonnegative solution when \(d_A\ge d_B\). The same proportional-stretch technique is used by the specification’s one-third-alignment example. [web:274]

---

## 3.3 `boxas`, `boxto`, and alignment annotations

`boxas` and `boxto` are **not keywords or productions in OpenQASM 3.0, 3.1, or the current accepted grammar**. The only accepted production is:

```antlr
boxStatement: BOX designator? scope;
```

[web:11]

Likewise, there is no standardized `@...` annotation that assigns left/right/center alignment. OpenQASM has a generic annotation mechanism, but annotation meanings are namespace-defined extensions unless incorporated into the specification. [web:432]

I find no primary-source evidence in the accepted specification or reference grammar that the spellings `boxas` or `boxto` reached formal proposal/accepted status. They should be treated, at most, as abandoned design-discussion terminology—not as deprecated syntax with portable semantics. The standardized solution is explicit constraints using `box`, `durationof`, `delay`, `barrier`, and `stretch`.

---

# 4. `cal` / `defcal` and OpenPulse inventory

## 4.1 OpenQASM calibration grammar

The core grammar includes:

```antlr
calibrationGrammarStatement
    : DEFCALGRAMMAR StringLiteral SEMICOLON
    ;

calStatement
    : CAL LBRACE CalibrationBlock? RBRACE
    ;

defcalStatement
    : DEFCAL defcalTarget
      (LPAREN defcalArgumentDefinitionList? RPAREN)?
      defcalOperandList
      returnSignature?
      LBRACE CalibrationBlock? RBRACE
    ;

defcalTarget
    : MEASURE
    | RESET
    | DELAY
    | Identifier
    ;

defcalOperand
    : HardwareQubit
    | Identifier
    ;
```

[web:333][web:334]

Selection:

```qasm
defcalgrammar "openpulse";
```

Examples:

```qasm
defcal rz(angle theta) $0 {
    // OpenPulse body
}

defcal measure $0 -> bit {
    // OpenPulse body
}
```

A `cal` block injects configuration or inline calibration-grammar statements at its enclosing scope. Values declared in calibration scope may be visible to later `cal`/`defcal` blocks according to the selected grammar, but do not leak back into ordinary OpenQASM scope. [web:342]

---

## 4.2 OpenPulse types and operations

| Concept | Standard form | Semantics |
|---|---|---|
| Port | `extern port drive0;` | Vendor-linked physical input/output component. |
| Frame | `frame f = newframe(port, frequency, phase);` | Stateful carrier plus per-frame clock. |
| Waveform | `waveform w = ...;` | Complex baseband envelope with definite duration. |
| Play | `play(frame, waveform);` | Emit waveform at frame’s current time/frequency/phase. |
| Capture | Vendor-defined `extern capture_*` | Acquire input using frame timing and optional duration/filter. |
| Delay | `delay[d] frame-list;` | Advance listed frame clocks by `d`. |
| Barrier | `barrier frame-list;` | Set listed frame clocks to their maximum time. |
| Frame phase | `set_phase`, `shift_phase` | Set or increment NCO phase at the current frame time. |
| Frame frequency | `set_frequency`, `shift_frequency` | Set or increment NCO frequency at the current frame time. |

Ports are externally linked because they are uniquely defined by the target system. [web:319][web:320]

---

## 4.3 Frame initialization

Exact documented form:

```qasm
extern port drive0;

frame driveframe0 =
    newframe(drive0, 5e9, 0.0);
```

with the documented conceptual signature:

```qasm
newframe(port pr, float[size] frequency, angle[size] phase)
```

[web:318]

A frame has four components:

1. a `port`, fixed after initialization;
2. `frequency : float`;
3. `phase : angle`;
4. `time : duration`, implicitly maintained.

[web:319]

---

## 4.4 Phase/frequency operations

The specification documents:

```qasm
set_phase(frame fr, angle phase);
shift_phase(frame fr, angle phase);

set_frequency(frame fr, float freq);
shift_frequency(frame fr, float freq);
```

[web:153]

It also describes corresponding phase/frequency getters, but backend support varies. These operations occur at the frame’s current time; they do not themselves provide an absolute timestamp. The paper describes a frame as analogous to an NCO whose carrier is:

\[
e^{i(2\pi f t+\phi)}.
\]

[web:38]

---

## 4.5 Waveforms

A `waveform` is either:

1. an explicit array of complex samples; or
2. an abstract template materialized by the compiler or hardware.

Example sampled waveform:

```qasm
waveform arb_waveform =
    [1+0im, 0+1im, 1/sqrt(2)+1/sqrt(2)im];
```

Waveforms must have definite duration. The spec recommends expressing durations in `dt` when exact sample realization matters. [web:137]

### Standard documented template signatures

```qasm
extern gaussian(
    complex[float[size]] amp,
    duration d,
    duration sigma
) -> waveform;

extern sech(
    complex[float[size]] amp,
    duration d,
    duration sigma
) -> waveform;

extern gaussian_square(
    complex[float[size]] amp,
    duration d,
    duration square_width,
    duration sigma
) -> waveform;

extern drag(
    complex[float[size]] amp,
    duration d,
    duration sigma,
    float[size] beta
) -> waveform;

extern constant(
    complex[float[size]] amp,
    duration d
) -> waveform;

extern sine(
    complex[float[size]] amp,
    duration d,
    float[size] frequency,
    angle[size] phase
) -> waveform;
```

[web:136][web:137]

The parameter order is significant. Some vendor implementations, notably Amazon Braket, expose target-specific signatures with different argument order/types; those are dialect/backend APIs rather than portable replacements for the specification declarations.

### Waveform algebra

```qasm
mix(waveform wf1, waveform wf2) -> waveform;
sum(waveform wf1, waveform wf2) -> waveform;
scale(waveform wf, float factor) -> waveform;
phase_shift(waveform wf, angle ang) -> waveform;
```

Semantics:

\[
\operatorname{mix}(a,b)[i]=a[i]b[i]
\]

\[
\operatorname{sum}(a,b)[i]=a[i]+b[i]
\]

\[
\operatorname{scale}(a,k)[i]=k\,a[i]
\]

\[
\operatorname{phase\_shift}(a,\theta)[i]
=e^{i\theta}a[i].
\]

[web:348][web:363][web:169]

The 3.1 page presents these as standard waveform functions, but implementors should not assume every backend provides them; for example, OQC documents `scale` and `phase_shift` but not `mix` or `sum`. [web:176]

---

## 4.6 `play`

Conceptual signature:

```qasm
play(frame output, waveform wf);
```

The two required arguments are the frame and waveform. The frame supplies:

- start time: current `frame.time`;
- carrier frequency: current `frame.frequency`;
- phase offset: current `frame.phase`.

[web:393][web:395]

Operationally:

```text
start(play) = frame.time
frame.time += duration(waveform)
```

The specification says `play` belongs in calibration blocks; one page says only `defcal`, while the acquisition discussion and implementations allow pulse operations in `cal` as well. This is a genuine specification/editorial inconsistency, and implementations differ—for example, pyqasm exposes a `play_in_cal_block` option. [web:393][web:396]

---

## 4.7 Delay and barrier on frames

```qasm
delay[13ns] driveframe;
barrier driveframe, measureframe;
```

Frame delay advances the named clocks by the requested duration. If that duration cannot be represented at the underlying port’s sample rate, the compiler must raise a compile-time error. [web:293]

Barrier computes the maximum current time and advances earlier frames to it. [web:198]

A `defcal` also has implicit synchronization across participating frames at its boundaries, establishing a common entry and exit time. [web:201]

---

# 5. Absolute time and explicit schedules

## 5.1 Is there an absolute-time event representation?

**No.** Standard OpenPulse has no syntax equivalent to:

```text
play B at 250 ns
```

or:

```text
event(start_time=250ns, duration=40ns, channel=...)
```

The paper states:

> “Within a program, there is no explicit reference to a global clock, but instead, only relative references to the starting time of a `defcal`/`cal` or the current relative time of other frames through the `barrier` instruction.” [web:201]

Timing is represented by:

- the relative zero of the enclosing `cal`/`defcal`;
- each frame’s implicit cursor;
- sequential operations on each frame;
- `delay`;
- `barrier`;
- enclosing OpenQASM timing constraints such as boxes and stretches.

A compiler can certainly lower OpenPulse into an internal absolute event list, but that event list is not the standardized OpenPulse source representation.

---

## 5.2 Meaning of `frame.time`

`frame.time` is not a generally assignable user variable. It is a `duration`-typed clock maintained implicitly by:

- `delay`;
- `play`;
- `capture`;
- `barrier`.

The specification says it “cannot be modified other than through” those timing instructions. [web:155][web:156]

Initialization:

- a frame created inside a `defcal` begins at that `defcal`’s scheduled start;
- a frame created inside a global `cal` begins at global calibration time zero;
- frames entering a `defcal` are synchronized by the implicit entry barrier.

Thus it is internally an absolute execution time once the outer block has been scheduled, but source-level code normally treats it as a relative, implicit cursor.

---

## 5.3 “Start pulse B 50 ns after the center of pulse A”

Let `dA` be A’s duration. On distinct frames:

```qasm
duration dA = 200ns;

waveform A = gaussian(0.2, dA, 40ns);
waveform B = gaussian(0.1, 80ns, 20ns);

barrier fA, fB;

play(fA, A);
delay[dA / 2 + 50ns] fB;
play(fB, B);

barrier fA, fB;
```

Because both frames start at the same barrier:

```text
start(A) = t0
center(A) = t0 + dA/2
start(B) = t0 + dA/2 + 50ns
```

Textual appearance of `play(fA, A)` before the delay on `fB` does not advance `fB`; each frame has its own clock.

### Restrictions

- If A and B use the same frame, they cannot overlap: B starts no earlier than A’s end.
- If they use different frames on the same port, overlap/multiplexing is target dependent.
- The requested offset must be quantizable to the relevant port’s sample period.
- OpenPulse does not have a `center(A)` expression; retain `dA`, use a referential duration where legal, or construct the relation with stretch.

---

# 6. Frames and ports versus flat channels

## 6.1 Port

A `port` is a physical-I/O abstraction: an input or output component used to manipulate or observe qubits. It identifies the hardware resource on which output is emitted or from which input is acquired. Vendor translation units resolve `extern port` declarations. [web:319]

A port may map to DACs, ADCs, mixers, routing fabric, or a compound vendor resource. The exact mapping is intentionally outside the portable grammar.

## 6.2 Frame

A frame combines:

| Field | Role |
|---|---|
| `port` | Physical I/O attachment; immutable after initialization |
| `frequency` | Carrier/NCO frequency |
| `phase` | Carrier/NCO phase offset |
| `time` | Implicit scheduling cursor |

[web:319]

Multiple frames may attach to one port. This permits distinct logical carriers/NCO contexts and frequency-multiplexed signaling on a common physical I/O path. The OpenQASM paper explicitly says multiple frames per port allow multiplexing over a port’s I/O for multiple carrier signals. [web:38]

Whether simultaneous plays are legal, summed automatically, or rejected due to a port conflict is backend dependent; the current OpenPulse text does not fully standardize port-arbitration semantics.

## 6.3 Comparison with Qiskit Pulse channels

Historical Qiskit Pulse exposed flat typed resource identifiers such as:

- `DriveChannel`
- `MeasureChannel`
- `AcquireChannel`
- `ControlChannel`

These backend methods were deprecated and removed with Qiskit Pulse. [web:225]

OpenPulse’s frame/port split gains:

1. separation of physical I/O identity from carrier state;
2. multiple logical carrier frames on one port;
3. explicit, persistent frequency and phase tracking;
4. an implicit clock per frame;
5. calibration definitions that can modify NCO state without hard-coding a flat channel schedule;
6. a more hardware-independent representation suitable for externally linked ports/frames.

The cost is that aliasing and collision analysis become more sophisticated: a compiler must know when two frames share a port and whether the target can mix them concurrently.

---

# 7. Acquisition, kernels, discrimination, and feedback

## 7.1 Capture is vendor-defined

The specification describes `capture` as a special `extern` function supplied by the hardware vendor. At minimum it receives a frame, which supplies acquisition start time. Additional arguments may include:

- a `duration`;
- a `waveform` filter/kernel;
- vendor-specific acquisition configuration.

A waveform filter is dot-producted with measured IQ samples to reduce them to a single IQ value. [web:378][web:413]

## 7.2 Standard illustrative capture variants

```qasm
extern capture_v0(frame output);

extern capture_v1(
    frame output,
    waveform filter
) -> complex[float[32]];

extern capture_v2(
    frame output,
    waveform filter
) -> bit;

extern capture_v3(
    frame output,
    duration len
) -> waveform;

extern capture_v4(
    frame output,
    duration len
) -> int;
```

[web:138][web:139]

| Variant | Intended result |
|---|---|
| `capture_v0` | Minimum/vendor-defined acquisition; no standardized returned value |
| `capture_v1` | Integrated IQ value after applying a waveform filter/kernel |
| `capture_v2` | Discriminated classical bit |
| `capture_v3` | Raw acquired waveform |
| `capture_v4` | Integer count, e.g. detected photon count |

These are illustrative standard names, not a guarantee that every backend implements all five. OQC, for example, documents support for `capture_v1`, `v2`, and `v3`, but not `v0` or `v4`. [web:141]

## 7.3 Measurement levels

The historical OpenPulse model distinguishes:

- **level 0:** raw downconverted samples;
- **level 1:** kernel-integrated complex IQ;
- **level 2:** discriminator-produced state result.

It was designed to expose raw data for constructing kernels/discriminators and to support simple conditional pulse execution. [web:386]

OpenPulse 3-style code can perform kernel/discrimination explicitly:

```qasm
waveform raw = capture_v3(capture_frame, 16000dt);
complex[float[32]] iq = boxcar(raw);
bit result = discriminate(iq);
return result;
```

The spec gives `extern discriminate(complex[float[64]] iq) -> bit;` as an example of vendor/user-provided post-processing. [web:379]

The exact array widths and `boxcar` signature are not universally fixed; the page contains illustrative variants. Implementations must not assume every capture backend returns the same complex width.

## 7.4 Timing of capture

A capture starts at `frame.time` and advances the frame clock by its acquisition duration—either the duration of an associated waveform/filter or an explicitly supplied `len`, depending on the vendor signature. [web:194][web:200]

The current wording “advances by the duration of the associated waveform argument” does not completely cover every listed signature, especially `capture_v0` and count/raw captures. For those, the backend definition must establish a definite duration. This is one of the areas where OpenPulse remains underspecified.

## 7.5 Real-time variables and feedback

A measurement calibration can return a real-time value:

```qasm
defcal measure $0 -> bit {
    // play readout pulse
    // capture and discriminate
    return result;
}
```

Ordinary OpenQASM can consume it:

```qasm
bit result = measure q[0];

if (result) {
    x q[1];
}
```

OpenQASM explicitly supports “classical feed-forward flow control based on measurement outcomes” and concurrent real-time classical computation. [web:410]

The data dependency prevents the conditional operation from executing before the measurement result exists. However:

- OpenQASM does not specify a universal controller latency;
- classical expression evaluation and branch dispatch may have target-specific duration;
- if exact timing matters, calibrated durations, explicit delays, boxes, or target scheduling constraints are required;
- control flow inside a `defcal` must have equal statically known duration on all branches. [web:259]

---

# 8. History and ecosystem status, 2025–2026

## 8.1 History

OpenPulse originally appeared in 2018 as a Qiskit/Qobj-oriented pulse-level backend interface. The original paper describes a general-device pulse-control language and was submitted on 10 September 2018. [web:129]

The OpenQASM 3 effort subsequently recast OpenPulse as a textual calibration grammar selected with:

```qasm
defcalgrammar "openpulse";
```

The OpenQASM 3 paper describes this as a hardware-independent pulse representation embedded through `cal`/`defcal`. [web:38][web:135]

A repository issue to implement the OpenPulse grammar was opened in October 2021. [web:197] By the OpenQASM 3 specification era, a complete OpenPulse chapter and reference Python AST/parser existed, but the chapter remained explicitly “in active development.” [web:125][web:122]

Thus “OpenPulse RFC” can refer to several related artifacts:

1. the 2018 OpenPulse/Qobj specification;
2. the OpenQASM working-group design and grammar issues;
3. the OpenQASM 3 OpenPulse companion grammar;
4. vendor dialects derived from that grammar.

They are not all identical wire formats.

## 8.2 Adoption/status table

| System | 2025–2026 status |
|---|---|
| **AWS Braket** | Active OpenPulse user. Braket supports direct OpenPulse/OpenQASM pulse programs and uses OpenPulse as the underlying IR for native pulse instructions. Braket Pulse was launched for Rigetti and OQC hardware, and its Python pulse module is built on OQpy. [web:146][web:251] |
| **OQC** | Accepts OpenQASM 3 with low-level OpenPulse control, but supports a documented subset: `play`, frame delay/barrier, captures `v1–v3`, selected frame operations, and selected waveform functions. [web:141][web:159][web:176] |
| **Qiskit 2.x / IBM Quantum** | Circuit-level `duration`, boxes, delays, and experimental `stretch` support continue, but `qiskit.pulse` was completely removed in Qiskit 2.0 and IBM hardware pulse access was removed in February 2025. Consequently Qiskit 2.x is not an active OpenPulse execution frontend for IBM hardware. [web:214][web:215][web:225] |
| **LabOne Q** | Provides an `OpenQASMTranspiler` and aims to support OpenQASM 3.0 and the corresponding OpenPulse version, translating programs to LabOne Q experiments/pulses. Support is not complete and is documented feature by feature. [web:228][web:231] |
| **pyqasm** | Parses and semantically validates OpenPulse constructs, including `cal`, `defcal`, frames, timing, captures, and waveform functions. It has implementation options for disputed contexts such as `play` in `cal`; it currently documents lack of support for OpenPulse `extern` declarations. [web:230][web:321] |
| **OQpy** | Active Python generator for OpenQASM 3 plus OpenPulse, built on the reference `openqasm3` and `openpulse` AST packages. It was adopted as the foundation of Braket Pulse’s Python representation. [web:235][web:251] |
| **openpulse-python** | Reference AST/parser package for the bodies of OpenPulse `cal` and `defcal` blocks; it reuses OpenQASM classical statements and types. It is primarily a parser/AST reference, not a complete scheduler or hardware runtime. [web:122][web:242] |

---

# 9. Requirements for an implementing compiler/IR

A conforming or practically useful timing implementation should model at least:

1. **Resource identity**
   - qubits;
   - ports;
   - frames;
   - frame-to-port aliasing.

2. **Duration expressions**
   - physical units and backend `dt`;
   - compile-time arithmetic;
   - target quantization;
   - `durationof` after calibration selection.

3. **Partial order**
   - resource dependencies;
   - data/classical dependencies;
   - barriers;
   - box boundaries.

4. **Explicit versus implicit idle**
   - implicit idle remains schedulable/commutable;
   - explicit `delay` is a timed identity and optimization barrier on its operands.

5. **Stretch constraints**
   - affine expressions only;
   - nonnegativity;
   - lexicographic minimization;
   - infeasibility diagnostics;
   - deterministic `dt` rounding policy.

6. **Box constraints**
   - no movement into or out of a box;
   - participant-resource entry/exit synchronization;
   - optional exact total duration;
   - nested-box duration propagation.

7. **Frame state**
   - immutable port;
   - current frequency;
   - current phase;
   - implicit time cursor;
   - persistence/linkage rules.

8. **Pulse operations**
   - `play` consumes waveform duration;
   - `capture` has vendor-defined but statically definite duration;
   - frame delay and barriers;
   - same-port collision/multiplexing checks.

9. **Calibration duration**
   - every `defcal` has statically definite duration;
   - equal-duration branches;
   - statically bounded loops;
   - return-value readiness and classical feedback dependencies.

10. **Lowering**
    - source OpenQASM/OpenPulse partial order;
    - solved stretch schedule;
    - target-quantized frame schedule;
    - optional final absolute event list.

The cleanest IR design is therefore to preserve both a **constraint-level schedule**—durations, stretches, boxes, barriers, frame cursors—and a later **resolved event schedule**. Treating OpenPulse source directly as an absolute timestamp list would discard important design intent and would misrepresent the standardized model.

Citations:
[16] https://openqasm.com/language/delays.html
[17] https://openqasm.com/versions/3.0/language/delays.html
[18] https://openqasm.com/versions/3.1/language/delays.html
[19] https://openqasm.com/versions/3.1/language/openpulse.html
[20] https://openqasm.com/language/types.html
[21] https://openqasm.com/language/openpulse.html
[22] https://openqasm.com/language/
[23] https://openqasm.com/versions/3.1/index.html
[24] https://openqasm.com/versions/3.0/language/openpulse.html
[25] https://openqasm.com/versions/3.1/release_notes.html
[26] https://openqasm.com/intro.html
[27] https://openqasm.com/
[28] https://openqasm.com/versions/3.0/language/index.html
[29] https://openqasm.com/versions/3.0/language/pulses.html
[30] https://openqasm.com/versions/3.0/intro.html
[31] https://openqasm.com/language/openpulse.html
[32] https://openqasm.com/versions/3.0/language/openpulse.html
[33] https://openqasm.com/language/pulses.html
[34] https://openqasm.com/versions/3.1/language/openpulse.html
[35] https://openqasm.com/versions/3.0/language/pulses.html
[36] https://openqasm.com/grammar/index.html
[37] https://openqasm.com/language/
[38] https://arxiv.org/pdf/2104.14722
[39] https://github.com/openqasm
[40] https://openqasm.com/
[41] https://github.com/openqasm/oqpy
[42] https://openqasm.com/openqasm-pygments/
[43] https://openqasm.com/versions/3.0/grammar/index.html
[44] https://github.com/openqasm/openqasm
[45] https://github.com/openqasm/openpulse-python
[1] https://github.com/openqasm/openqasm/blob/main/README.md
[2] https://github.com/openqasm/openqasm/blob/main/examples/arrays.qasm
[3] https://github.com/openqasm/openqasm/pulls
[4] https://github.com/openqasm/openqasm
[5] https://github.com/openqasm/openqasm/tree/main
[6] https://github.com/openqasm
[7] https://github.com/openqasm/openqasm/releases
[8] https://github.com/openqasm/openqasm/blob/main/examples/scqec.qasm
[9] https://github.com/openqasm/openqasm/blob/main/examples/qec.qasm
[10] https://github.com/openqasm/openqasm/blob/main/examples/vqe.qasm
[11] https://github.com/openqasm/openqasm/blob/main/source/grammar/qasm3Parser.g4
[12] https://github.com/openqasm/openqasm/blob/main/examples/adder.qasm
[13] https://github.com/openqasm/openqasm/blob/main/examples/msd.qasm
[14] https://github.com/openqasm/openqasm/blob/main/examples/inverseqft1.qasm
[15] https://github.com/openqasm/oqpy
[46] https://openqasm.com/language/delays.html
[47] https://scispace.com/pdf/openqasm-3-a-broader-and-deeper-quantum-assembly-language-3ezxsn6t.pdf
[48] https://arxiv.org/html/2605.30358v1
[49] https://openqasm.com/language/insts.html
[50] https://zachschoenfeld33.github.io/openqasm/
[51] https://arxiv.org/pdf/2104.14722v1
[52] https://openqasm.com/versions/3.0/language/delays.html
[53] https://openqasm.com/language/classical.html
[54] https://openqasm.com/intro.html
[55] https://openqasm.com/versions/3.1/language/delays.html
[56] https://deepwiki.com/openqasm/openqasm/2-language-specification
[57] https://ocw.tudelft.nl/wp-content/uploads/DT05_scheduling.pdf
[58] https://openqasm.com/versions/3.0/language/classical.html
[59] https://qiskit.qotlabs.org/docs/guides/qasm-feature-table
[60] https://openqasm.com/versions/3.0/intro.html
[61] https://openqasm.com/language/delays.html
[62] https://arxiv.org/pdf/2104.14722
[63] https://openqasm.com/versions/3.1/language/delays.html
[64] https://openqasm.com/versions/3.0/language/delays.html
[65] https://qiskit.qotlabs.org/docs/guides/stretch
[66] https://www.scribd.com/document/570901540/open-quantum-assembly-language
[67] https://zachschoenfeld33.github.io/openqasm/
[68] https://openqasm.com/language/
[69] https://quantum.cloud.ibm.com/docs/guides/qasm-feature-table
[70] https://github.com/openqasm/openqasm/tree/main
[71] https://openqasm.com/language/directives.html
[72] https://github.com/openqasm/openqasm/blob/main/README.md
[73] https://openqasm.com/versions/3.1/release_notes.html
[74] https://github.com/openqasm/openqasm
[75] https://openqasm.com/versions/3.1/index.html
[76] https://openqasm.com/language/delays.html
[77] https://arxiv.org/pdf/2104.14722
[78] https://openqasm.com/language/directives.html
[79] https://zachschoenfeld33.github.io/openqasm/
[80] https://openqasm.com/language/insts.html
[81] https://github.com/comp-phys-marc/qasm-ts
[82] https://github.com/openqasm/openqasm
[83] https://openqasm.com/grammar/index.html
[84] https://github.com/openqasm/openqasm/tree/main
[85] https://openqasm.com/versions/3.0/grammar/index.html
[86] https://quantum.cloud.ibm.com/docs/guides/qasm-feature-table
[87] https://docs.aws.amazon.com/braket/latest/developerguide/braket-openqasm-supported-features.html
[88] https://dl.acm.org/doi/10.1145/3505636
[89] https://openqasm.com/language/
[90] https://deepwiki.com/openqasm/openqasm/2-language-specification
[91] https://quantum-journal.org/papers/q-2024-08-22-1443/
[92] https://scispace.com/pdf/openqasm-3-a-broader-and-deeper-quantum-assembly-language-3ezxsn6t.pdf
[93] https://pmc.ncbi.nlm.nih.gov/articles/PMC275464/
[94] https://www.reddit.com/r/QuantumFiber/comments/1leoccc/whats_the_difference_between_these_two_boxes_from/
[95] https://openqasm.com/language/
[96] https://openqasm.com/language/insts.html
[97] https://openqasm.com/language/delays.html
[98] https://www.academia.edu/120214709/Synthesis_and_fluorescence_characteristics_of_novel_asymmetric_cyanine_dyes_for_DNA_detection
[99] https://en.wikipedia.org/wiki/OpenQASM
[100] https://github.com/openqasm/openqasm/tree/main
[101] https://academic.oup.com/nar/article/31/21/6227/1042460
[102] https://openqasm.com/
[103] https://github.com/libingzheren/OpenQASM
[104] https://arxiv.org/abs/1707.03429
[105] https://github.com/openqasm/openqasm
[106] https://github.com/openqasm/openqasm
[107] https://github.com/openqasm/openqasm/blob/main/source/grammar/qasm3Parser.g4
[108] https://github.com/openqasm/openqasm/tree/main
[109] https://github.com/openqasm/openqasm/blob/main/examples/inverseqft1.qasm
[110] https://github.com/openqasm/openqasm/blob/main/examples/arrays.qasm
[111] https://github.com/openqasm/openqasm/blob/main/README.md
[112] https://github.com/openqasm/openqasm/pulls
[113] https://github.com/openqasm/openqasm/blob/main/CONTRIBUTING.md
[114] https://github.com/openqasm/openqasm/blob/main/examples/scqec.qasm
[115] https://github.com/openqasm/openqasm/blob/main/examples/msd.qasm
[116] https://github.com/openqasm/openqasm/blob/main/examples/qec.qasm
[117] https://github.com/openqasm/openqasm/blob/main/source/language/types.rst
[118] https://github.com/openqasm/openqasm/releases
[119] https://github.com/openqasm/openqasm/blob/main/examples/adder.qasm
[120] https://github.com/openqasm/openqasm/blob/main/examples/vqe.qasm
[121] https://github.com/openqasm/openqasm
[122] https://github.com/openqasm/openpulse-python
[123] https://github.com/openqasm/oqpy
[124] https://github.com/openqasm
[125] https://openqasm.com/language/openpulse.html
[126] https://github.com/openqasm/openqasm/blob/main/WG.md
[127] https://openqasm.com/versions/3.0/language/openpulse.html
[128] https://openqasm.com/versions/3.1/language/openpulse.html
[129] https://arxiv.org/abs/1809.03452
[130] https://github.com/openqasm/openpulse-python/actions/runs/12710922026
[131] https://github.com/openqasm/openqasm/pulls
[132] https://medium.com/qiskit/whats-in-the-latest-openqasm-specification-c0cdf4313a1a
[133] https://github.com/openqasm/openqasm/blob/main/LICENSE
[134] https://openqasm.com/openqasm-pygments/
[135] https://arxiv.org/pdf/2104.14722
[136] https://openqasm.com/versions/3.1/language/openpulse.html
[137] https://openqasm.com/language/openpulse.html
[138] https://openqasm.com/versions/3.1/language/openpulse.html
[139] https://openqasm.com/language/openpulse.html
[140] https://openqasm.com/versions/3.0/language/openpulse.html
[141] https://docs.oqc.app/qasm3.html
[142] https://qbraidco.mintlify.app/pyqasm/user-guide/openpulse
[143] https://github.com/open-pulse/OpenPulse/releases
[144] https://research.ibm.com/publications/qiskit-backend-specifications-for-openqasm-and-openpulse-experiments
[145] https://open-pulse.readthedocs.io/
[146] https://docs.aws.amazon.com/braket/latest/developerguide/braket-hello-pulse.html
[147] https://arxiv.org/pdf/2104.14722
[148] https://aws.amazon.com/blogs/quantum-computing/amazon-braket-launches-braket-pulse-to-develop-quantum-programs-at-the-pulse-level/
[149] https://pkg.go.dev/github.com/splch/goqu/pulse
[150] https://pypi.org/project/openpulse/
[151] https://libraries.io/conda/openpulse
[152] https://www.openpulse.eu/
[153] https://openqasm.com/versions/3.1/language/openpulse.html
[154] https://scispace.com/pdf/openqasm-3-a-broader-and-deeper-quantum-assembly-language-3ezxsn6t.pdf
[155] https://openqasm.com/versions/3.0/language/openpulse.html
[156] https://openqasm.com/language/openpulse.html
[157] https://docs.qbraid.com/v2/pyqasm/user-guide/openpulse
[158] https://deepwiki.com/openqasm/openqasm/2.3-openpulse-grammar
[159] https://docs.oqc.app/qasm3.html
[160] https://research.ibm.com/publications/openpulse-software-for-experimental-physicists-in-quantum-computing
[161] https://ar5iv.labs.arxiv.org/html/1809.03452
[162] https://www.scribd.com/document/570901540/open-quantum-assembly-language
[163] https://github.com/openqasm/oqpy
[164] https://openqasm.com/versions/3.0/language/pulses.html
[165] https://openqasm.com/language/pulses.html
[166] https://docs.aws.amazon.com/braket/latest/developerguide/braket-openqasm-supported-features.md
[167] https://docs.aws.amazon.com/ko_kr/braket/latest/developerguide/braket-hello-pulse-openpulse.html
[168] https://openqasm.com/language/openpulse.html
[169] https://openqasm.com/versions/3.0/language/openpulse.html
[170] https://openqasm.com/versions/3.1/language/openpulse.html
[171] https://docs.qbraid.com/v2/pyqasm/user-guide/openpulse
[172] https://pulser.readthedocs.io/en/latest/apidoc/_autosummary/pulser.pulse.Pulse.html
[173] https://deepwiki.com/openqasm/openqasm/2.3-openpulse-grammar
[174] https://openqasm.com/language/pulses.html
[175] https://docs.aws.amazon.com/ko_kr/braket/latest/developerguide/braket-hello-pulse-openpulse.html
[176] https://docs.oqc.app/qasm3.html
[177] https://docs.aws.amazon.com/braket/latest/developerguide/braket-hello-pulse.html
[178] https://research.ibm.com/publications/openpulse-software-for-experimental-physicists-in-quantum-computing
[179] https://arxiv.org/pdf/2104.14722
[180] https://dsp.stackexchange.com/questions/88933/how-can-i-apply-a-phase-shift-to-an-lfm-pulse
[181] https://pkg.go.dev/github.com/splch/goqu/pulse
[182] https://research.ibm.com/publications/qiskit-backend-specifications-for-openqasm-and-openpulse-experiments
[183] https://github.com/openqasm/openpulse-python
[184] https://github.com/openqasm/openpulse-python/actions/runs/12710922026
[185] https://github.com/openqasm/openpulse-python/actions
[186] https://github.com/openqasm/openpulse-python/pull/40/files
[187] https://github.com/openqasm/openpulse-python/issues
[188] https://github.com/openqasm/openpulse-python/pulls
[189] https://github.com/openqasm/openpulse-python/issues/39
[190] https://github.com/antlr/grammars-v4/blob/master/sql/plsql/PlSqlParser.g4
[191] https://github.com/openqasm/openpulse-python/pull/40/checks
[192] https://pypi.org/project/openpulse/
[193] https://www.antlr.org/
[194] https://openqasm.com/language/openpulse.html
[195] https://www.telusdigital.com/insights/digital-experience/article/an-introduction-to-language-lexing-and-parsing-with-antlr
[196] https://laure.gonnord.org/pro/teaching/CAP1718_ENSL/cap_tp2.pdf
[197] https://github.com/openqasm/openqasm/issues/296
[198] https://openqasm.com/language/openpulse.html
[199] https://openqasm.com/versions/3.0/language/openpulse.html
[200] https://openqasm.com/versions/3.1/language/openpulse.html
[201] https://arxiv.org/pdf/2104.14722
[202] https://docs.qbraid.com/v2/pyqasm/user-guide/openpulse
[203] https://www.scribd.com/document/570901540/open-quantum-assembly-language
[204] https://deepwiki.com/openqasm/openqasm/2.3-openpulse-grammar
[205] https://docs.oqc.app/qasm3.html
[206] https://docs.aws.amazon.com/braket/latest/developerguide/braket-openqasm-supported-features.md
[207] https://docs.aws.amazon.com/ko_kr/braket/latest/developerguide/braket-hello-pulse-openpulse.html
[208] https://openqasm.com/language/pulses.html
[209] https://deepwiki.com/openqasm/openqasm/6.2-pulse-level-control-examples
[210] https://openqasm.com/versions/3.0/language/pulses.html
[211] https://pkg.go.dev/github.com/splch/goqu/pulse
[212] https://github.com/openqasm/oqpy
[243] https://docs.aws.amazon.com/braket/latest/developerguide/braket-openqasm-supported-features.html
[244] https://docs.aws.amazon.com/braket/latest/developerguide/braket-openqasm-device-support.html
[245] https://docs.aws.amazon.com/pdfs/braket/latest/developerguide/braket-developer-guide.pdf
[246] https://docs.oqc.app/qasm3.html
[247] https://docs.aws.amazon.com/braket/latest/developerguide/braket-openqasm.html
[248] https://docs.aws.amazon.com/zh_tw/braket/latest/developerguide/braket-openqasm-device-support.html
[249] https://docs.aws.amazon.com/pt_br/braket/latest/developerguide/braket-openqasm-device-support.html
[250] https://docs.aws.amazon.com/zh_cn/braket/latest/developerguide/braket-openqasm-device-support.html
[251] https://aws.amazon.com/blogs/quantum-computing/amazon-braket-launches-braket-pulse-to-develop-quantum-programs-at-the-pulse-level/
[252] https://aws.amazon.com/blogs/quantum-computing/aws-open-sources-oqpy-to-make-it-easier-to-write-quantum-programs-in-openqasm-3/
[253] https://openqasm.com/versions/3.0/language/openpulse.html
[254] https://docs.aws.amazon.com/braket/latest/developerguide/braket-pulse-control.html
[255] https://docs.aws.amazon.com/braket/latest/developerguide/braket-openqasm-create-submit-task.html
[256] https://quantumcomputingcourses.com/platform/aws
[257] https://openqasm.com/language/openpulse.html
[213] https://qiskit.qotlabs.org/docs/guides/stretch
[214] https://www.ibm.com/quantum/blog/qiskit-2-0-release-summary
[215] https://qiskit.qotlabs.org/docs/api/qiskit/release-notes/2.0
[216] https://github.com/Qiskit/qiskit/issues/13063
[217] https://quantum.cloud.ibm.com/docs/guides/pulse-migration
[218] https://qiskit-community.github.io/qiskit-experiments/release_notes.html
[219] https://github.com/Qiskit/qiskit/wiki/Roadmap
[220] https://quantum.cloud.ibm.com/docs/en/guides/qiskit-2.0
[221] https://arxiv.org/pdf/2104.14722
[222] https://github.com/Qiskit/qiskit/issues/13662
[223] https://github.com/qiskit/qiskit/releases
[224] https://docs.quantum.ibm.com/api/qiskit/qiskit.providers.models.QasmBackendConfiguration
[225] https://www.ibm.com/quantum/blog/qiskit-1-3-release-summary
[226] https://qiskit.qotlabs.org/guides/pulse
[227] https://certiq.dev/docs/cram/s8
[228] https://docs.zhinst.com/labone_q_user_manual/core/reference/openqasm3.html
[229] https://www.zhinst.com/en/blogs/run-openqasm-circuits-on-your-quantum-chip/
[230] https://docs.qbraid.com/v2/pyqasm/user-guide/openpulse
[231] https://docs.zhinst.com/labone_q_user_manual/core/functionality_and_concepts/08_openqasm/tutorials/00_program_to_experiment.html
[232] https://openqasm.com/versions/3.0/language/openpulse.html
[233] https://openqasm.com/language/openpulse.html
[234] https://openqasm.com/versions/3.1/language/openpulse.html
[235] https://github.com/openqasm/oqpy
[236] https://docs.zhinst.com/labone_q_user_manual/applications_library/how-to-guides/sources/04_qasm/index.html
[237] https://docs.zhinst.com/labone_q_user_manual/applications_library/how-to-guides/sources/04_qasm/01_VQE_Qiskit.html
[238] https://openqasm.com/openqasm-pygments/
[239] https://deepwiki.com/openqasm/openqasm/7-ecosystem-and-implementations
[240] https://zenodo-rdm.web.cern.ch/records/7349266
[241] https://www.zhinst.com/en/blog-tag/labone-q
[242] https://github.com/openqasm/openpulse-python
[273] https://openqasm.com/language/delays.html
[274] https://scispace.com/pdf/openqasm-3-a-broader-and-deeper-quantum-assembly-language-3ezxsn6t.pdf
[275] https://qiskit.qotlabs.org/docs/guides/stretch
[276] https://openqasm.com/
[277] https://zachschoenfeld33.github.io/openqasm/
[278] https://openqasm.com/versions/3.1/index.html
[279] https://dl.acm.org/doi/10.1145/3505636
[280] https://openqasm.com/versions/3.0/language/openpulse.html
[281] https://openqasm.com/language/pulses.html
[282] https://openqasm.com/versions/3.0/language/pulses.html
[283] https://qiskit.qotlabs.org/docs/guides/qasm-feature-table
[284] https://openqasm.com/language/openpulse.html
[285] https://github.com/openqasm/openqasm
[286] https://openqasm.com/versions/3.0/intro.html
[287] https://www.semanticscholar.org/paper/Qiskit-Backend-Specifications-for-OpenQASM-and-McKay-Alexander/d2720e0041c69666280d397ece6dbb85ec16d1ee
[288] https://openqasm.com/language/delays.html
[289] https://arxiv.org/pdf/2104.14722
[290] https://openqasm.com/versions/3.0/language/delays.html
[291] https://www.scribd.com/document/570901540/open-quantum-assembly-language
[292] https://openqasm.com/versions/3.1/language/delays.html
[293] https://openqasm.com/versions/3.0/language/openpulse.html
[294] https://zachschoenfeld33.github.io/openqasm/
[295] https://openqasm.com/intro.html
[296] https://github.com/openqasm/openqasm
[297] https://openqasm.com/versions/3.0/intro.html
[298] https://dl.acm.org/doi/10.1145/3505636
[299] https://openqasm.com/language/directives.html
[300] https://openqasm.com/versions/3.0/language/classical.html
[301] https://qiskit.qotlabs.org/docs/guides/qasm-feature-table
[302] https://deepwiki.com/openqasm/openqasm/2-language-specification
[258] https://openqasm.com/versions/3.1/language/delays.html
[259] https://openqasm.com/versions/3.1/language/pulses.html
[260] https://openqasm.com/versions/3.1/language/scope.html
[261] https://openqasm.com/versions/3.1/_sources/language/types.rst.txt
[262] https://openqasm.com/versions/3.1/language/types.html
[263] https://openqasm.com/versions/3.1/grammar/index.html
[264] https://openqasm.com/versions/3.1/release_notes.html
[265] https://openqasm.com/versions/3.1/language/classical.html
[266] https://openqasm.com/versions/3.1/index.html
[267] https://openqasm.com/versions/3.1/language/index.html
[268] https://openqasm.com/versions/3.1/language/insts.html
[269] https://openqasm.com/language/delays.html
[270] https://openqasm.com/versions/3.1/language/openpulse.html
[271] https://openqasm.com/versions/3.1/language/standard_library.html
[272] https://openqasm.com/language/
[303] https://openqasm.com/language/delays.html
[304] https://arxiv.org/pdf/2104.14722v1
[305] https://scispace.com/pdf/openqasm-3-a-broader-and-deeper-quantum-assembly-language-3ezxsn6t.pdf
[306] https://www.scribd.com/document/570901540/open-quantum-assembly-language
[307] https://openqasm.com/versions/3.0/language/delays.html
[308] https://openqasm.com/versions/3.1/language/delays.html
[309] https://arxiv.org/html/2605.30358v1
[310] https://qiskit.qotlabs.org/docs/guides/stretch
[311] https://openqasm.com/intro.html
[312] https://openqasm.com/versions/3.0/language/openpulse.html
[313] https://zachschoenfeld33.github.io/openqasm/
[314] https://openqasm.com/language/openpulse.html
[315] https://openqasm.com/language/insts.html
[316] https://openqasm.com/
[317] https://github.com/openqasm/openqasm/blob/main/README.md
[333] https://openqasm.com/versions/3.1/grammar/index.html
[334] https://openqasm.com/grammar/index.html
[335] https://openqasm.com/versions/3.0/grammar/index.html
[336] https://github.com/openqasm/openqasm
[337] https://github.com/openqasm/openqasm/tree/main
[338] https://github.com/openqasm/openqasm/blob/main/README.md
[339] https://openqasm.com/language/
[340] https://github.com/openqasm/openqasm/releases
[341] https://openqasm.com/language/scope.html
[342] https://openqasm.com/versions/3.0/language/pulses.html
[343] https://github.com/openqasm/openqasm/issues/507
[344] https://zachschoenfeld33.github.io/openqasm/
[345] https://www.scribd.com/document/570901540/open-quantum-assembly-language
[346] https://arxiv.org/pdf/2104.14722v1
[347] https://github.com/openqasm/openqasm/blob/main/examples/teleport.qasm
[318] https://openqasm.com/versions/3.1/language/openpulse.html
[319] https://openqasm.com/versions/3.0/language/openpulse.html
[320] https://arxiv.org/pdf/2104.14722
[321] https://docs.qbraid.com/v2/pyqasm/user-guide/openpulse
[322] https://openqasm.com/language/openpulse.html
[323] https://github.com/openqasm/openqasm/issues/577
[324] https://deepwiki.com/openqasm/openqasm/2.3-openpulse-grammar
[325] https://pypi.org/project/openpulse/
[326] https://openqasm.com/language/pulses.html
[327] https://openqasm.com/versions/3.0/language/pulses.html
[328] https://docs.zhinst.com/labone_q_user_manual/core/reference/openqasm3.html
[329] https://docs.oqc.app/qasm3.html
[330] https://github.com/openqasm/oqpy
[331] https://www.scribd.com/document/570901540/open-quantum-assembly-language
[332] https://github.com/openqasm/openqasm/issues/296
[348] https://openqasm.com/language/openpulse.html
[349] https://docs.oqc.app/qasm3.html
[350] https://openqasm.com/versions/3.0/language/openpulse.html
[351] https://openqasm.com/language/pulses.html
[352] https://docs.qbraid.com/v2/pyqasm/user-guide/openpulse
[353] https://openqasm.com/versions/3.1/language/openpulse.html
[354] https://openqasm.com/versions/3.0/language/pulses.html
[355] https://deepwiki.com/openqasm/openqasm/2.3-openpulse-grammar
[356] https://arxiv.org/pdf/2104.14722
[357] https://openqasm.com/
[358] https://docs.aws.amazon.com/zh_cn/braket/latest/developerguide/braket-hello-pulse.html
[359] https://openqasm.com/versions/3.1/index.html
[360] https://openqasm.com/versions/3.0/index.html
[361] https://pkg.go.dev/github.com/splch/goqu/pulse
[362] https://github.com/openqasm/openqasm/issues/126
[363] https://openqasm.com/language/openpulse.html
[364] https://openqasm.com/versions/3.0/language/openpulse.html
[365] https://docs.qbraid.com/v2/pyqasm/user-guide/openpulse
[366] https://openqasm.com/versions/3.1/language/openpulse.html
[367] https://openqasm.com/language/pulses.html
[368] https://docs.aws.amazon.com/ko_kr/braket/latest/developerguide/braket-hello-pulse-openpulse.html
[369] https://docs.oqc.app/qasm3.html
[370] https://github.com/openqasm/openqasm/issues/126
[371] https://deepwiki.com/openqasm/openqasm/2.3-openpulse-grammar
[372] https://en.wikipedia.org/wiki/Phase_(waves)
[373] https://research.ibm.com/publications/openpulse-software-for-experimental-physicists-in-quantum-computing
[374] https://pyquil-docs.rigetti.com/en/stable/quilt_waveforms.html
[375] https://openqasm.com/versions/3.0/language/pulses.html
[376] https://dsp.stackexchange.com/questions/88933/how-can-i-apply-a-phase-shift-to-an-lfm-pulse
[377] https://pkg.go.dev/github.com/splch/goqu/pulse
[378] https://openqasm.com/language/openpulse.html
[379] https://openqasm.com/versions/3.1/language/openpulse.html
[380] https://openqasm.com/versions/3.0/language/openpulse.html
[381] https://deepwiki.com/openqasm/openqasm/2.3-openpulse-grammar
[382] https://docs.qbraid.com/v2/pyqasm/user-guide/openpulse
[383] https://docs.aws.amazon.com/braket/latest/developerguide/braket-openqasm-supported-features.md
[384] https://arxiv.org/abs/2102.01153v1
[385] https://docs.oqc.app/qasm3.html
[386] https://ar5iv.labs.arxiv.org/html/1809.03452
[387] https://github.com/openqasm/openpulse-python
[388] https://arxiv.org/pdf/2104.14722
[389] https://docs.zhinst.com/labone_q_user_manual/core/reference/openqasm3.html
[390] https://open-pulse.readthedocs.io/
[391] https://github.com/openqasm/oqpy
[392] https://github.com/openqasm/openqasm/issues/126
[408] https://openqasm.com/versions/3.0/language/classical.html
[409] https://openqasm.com/language/openpulse.html
[410] https://openqasm.com/versions/3.0/intro.html
[411] https://openqasm.com/
[412] https://openqasm.com/language/
[413] https://openqasm.com/versions/3.1/language/openpulse.html
[414] https://openqasm.com/language/classical.html
[415] https://arxiv.org/abs/2104.14722
[416] https://openqasm.com/versions/3.0/language/openpulse.html
[417] https://openqasm.com/intro.html
[418] https://quantumcomputingcourses.com/tutorials/openqasm3-mid-circuit-measurement
[419] https://quantumcomputingcourses.com/tutorials/qasm3-classical-control-flow
[420] https://openqasm.com/language/pulses.html
[421] https://openqasm.com/versions/3.0/language/pulses.html
[422] https://openqasm.com/language/directives.html
[393] https://openqasm.com/language/openpulse.html
[394] https://openqasm.com/versions/3.0/language/openpulse.html
[395] https://openqasm.com/versions/3.1/language/openpulse.html
[396] https://docs.qbraid.com/v2/pyqasm/user-guide/openpulse
[397] https://deepwiki.com/openqasm/openqasm/2.3-openpulse-grammar
[398] https://docs.aws.amazon.com/braket/latest/developerguide/braket-hello-pulse.html
[399] https://docs.aws.amazon.com/zh_cn/braket/latest/developerguide/braket-hello-pulse.html
[400] https://docs.oqc.app/qasm3.html
[401] https://docs.aws.amazon.com/zh_tw/braket/latest/developerguide/braket-hello-pulse.html
[402] https://openqasm.com/language/pulses.html
[403] https://docs.zhinst.com/labone_q_user_manual/core/reference/openqasm3.html
[404] https://github.com/openqasm/oqpy
[405] https://docs.aws.amazon.com/ko_kr/braket/latest/developerguide/braket-hello-pulse.html
[406] https://arxiv.org/pdf/2104.14722
[407] https://www.scribd.com/document/570901540/open-quantum-assembly-language
[453] https://qiskit.qotlabs.org/docs/guides/qasm-feature-table
[454] https://github.com/uuudown/QASMBench
[455] https://alldesign.dk/products/saet-med-2-foldeaesker-boxas-roed/
[456] https://docs.box.com/en/box-fundamentals/for-users/user-login-and-settings/language-and-time-zones
[457] https://quran.com/en/al-qasas
[458] https://sites.google.com/site/diyloudspeakerdesign/home/box-design/alignments/alignment-tables
[459] https://taylorlee.xyz/2018/04/20/quantum-hello-world/
[460] https://www.boxa.net/topic/91632-language-choice-on-986/
[461] https://www.boxas.com.au/small-business-handbook/small-business-depreciation/
[462] https://dictionary.cambridge.org/dictionary/swedish-english/boxas
[463] https://docs.quantum-machines.co/1.1.7/qm-qua-sdk/docs/Guides/timing_in_qua/
[464] https://www.boxas.com.au/small-business-handbook/accountant-for-doctors/
[465] https://github.com/Qiskit/textbook/blob/main/notebooks/quantum-hardware-pulses/calibrating-qubits-pulse.ipynb
[466] https://www.geeksforgeeks.org/artificial-intelligence/what-is-planning-domain-definition-language-ppdl/
[467] https://openqasm.com/versions/3.0/language/openpulse.html
[438] https://scispace.com/pdf/openqasm-3-a-broader-and-deeper-quantum-assembly-language-3ezxsn6t.pdf
[439] https://www.boxtogolf.com/
[440] https://arxiv.org/pdf/2104.14722v1
[441] https://mygolfspy.com/news-opinion/first-look/boxto-x-jack-nicklaus-hecho-en-mexico/
[442] https://docs.box.com/en/box-fundamentals/for-users/user-login-and-settings/language-and-time-zones
[443] https://github.com/boxto/AbarClassic
[444] https://docs.quantum-machines.co/1.1.7/qm-qua-sdk/docs/Guides/timing_in_qua/
[445] https://docs.quantum.ibm.com/api/qiskit/pulse
[446] https://openqasm.com/language/
[447] https://arxiv.org/abs/1707.03429
[448] https://www.tandfonline.com/doi/full/10.1080/00268976.2021.1966111
[449] https://github.com/PennyLaneAI/qml/blob/master/demonstrations/tutorial_optimal_control.py
[450] https://openqasm.com/
[451] https://docs.pennylane.ai/en/stable/code/api/pennylane.to_openqasm.html
[452] https://en.wikipedia.org/wiki/OpenQASM
[423] https://openqasm.com/versions/3.0/language/openpulse.html
[424] https://openqasm.com/language/pulses.html
[425] https://openqasm.com/language/delays.html
[426] https://zachschoenfeld33.github.io/openqasm/
[427] https://openqasm.com/intro.html
[428] https://openqasm.com/language/standard_library.html
[429] https://arxiv.org/html/2605.30358v1
[430] https://openqasm.com/versions/3.0/language/pulses.html
[431] https://deepwiki.com/openqasm/openqasm/6.2-pulse-level-control-examples
[432] https://openqasm.com/language/directives.html
[433] https://docs.oqc.app/qasm3.html
[434] https://openqasm.com/
[435] https://openqasm.com/versions/3.0/grammar/index.html
[436] https://github.com/openqasm/openqasm
[437] https://research.ibm.com/publications/qiskit-backend-specifications-for-openqasm-and-openpulse-experiments
[468] https://arxiv.org/pdf/2104.14722
[469] https://openqasm.com/language/delays.html
[470] https://arxiv.org/html/2605.30358v1
[471] https://zachschoenfeld33.github.io/openqasm/
[472] https://openqasm.com/language/insts.html
[473] https://quantum.cloud.ibm.com/docs/guides/qasm-feature-table
[474] https://openqasm.com/versions/3.0/intro.html
[475] https://openqasm.com/versions/3.1/language/delays.html
[476] https://openqasm.com/language/types.html
[477] https://dl.acm.org/doi/10.1145/3505636
[478] https://openqasm.com/intro.html
[479] https://docs.aws.amazon.com/braket/latest/developerguide/braket-openqasm-supported-features.html
[480] https://deepwiki.com/openqasm/openqasm/6.2-pulse-level-control-examples
[481] https://openqasm.com/versions/3.0/index.html
[482] https://www.scribd.com/document/570901540/open-quantum-assembly-language
