# Raw Perplexity result — 06: Waveform typing, units/amplitude, classical types, control flow

> Model: `sonar-reasoning-pro` (reason, high search context). Query: how a closed discriminated
> union of pulse shapes maps to OpenPulse `waveform`; whether amplitudes have physical units;
> mapping IR variable declarations to OpenQASM 3 classical types; mapping repeat/for/if to
> OpenQASM 3 control flow.
>
> Citation URL list truncated to primary sources at the end.

---

## Executive answer

- `arbitrary-sampled` maps directly to a `waveform` complex-sample array.
- `external` maps to an `extern (...) -> waveform` declaration, but the declaration is only
  portable if the target supplies the same external function and ABI.
- Per-play scalar amplitude scaling maps directly to `scale(wf, k)`.
- A fixed-frequency sine maps to the standard `sine` template; **a linear chirp does not**.
- A square pulse with **linear** rise/fall ramps has **no standard OpenPulse template**. Use
  explicit samples or a vendor `extern`.
- OpenPulse does **not** define volts, dBm, watts, or another physical amplitude unit. Its
  waveform amplitudes are abstract complex envelope values whose hardware interpretation is
  target-specific.
- OpenQASM 3 has standard timing and angle units, but **no general physical-unit system** for
  frequency, amplitude, voltage, or other variables.
- OpenQASM 3 has `for`, `while`, `if`, `switch`, and `box`, but **no `repeat` statement**.
- `defcal` bodies must have a compile-time-resolvable definite duration; branches must have equal
  duration and loops must have resolvable duration.

---

# 1. Waveform typing

OpenPulse defines `waveform` as either complex samples or an abstract mathematical waveform later
materialized by the compiler or hardware. The abstract form is represented by target-provided
`extern` waveform templates.

## Mapping table

| IR shape                              | OpenPulse lowering                                                          | Portability                                                        |
| ------------------------------------- | --------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| `square` with no ramps                | `constant(complex amp, duration d)`                                         | Good if the target supports `constant`                             |
| `square` with **linear** rise/fall ramps | Explicit complex samples, or vendor `extern linear_ramp_square(...) -> waveform` | Explicit samples are portable; an `extern` is vendor-specific  |
| `sine` with fixed frequency           | `sine(complex amp, duration d, float frequency, angle phase)`               | Good only where the target provides the `sine` extern              |
| `sine` with linear frequency sweep/chirp | Explicitly sampled chirp, or vendor `extern chirp(...) -> waveform`      | **No standard OpenPulse chirp template**                           |
| `arbitrary-sampled`                   | `waveform wf = [complex samples];`                                          | Direct semantic match                                              |
| `external` named pulse                | `extern fully_named_function(...) -> waveform`, then call it                | Portable only if the target defines the same external symbol and parameter contract |
| Per-play amplitude scale              | `scale(wf, k)`                                                              | Direct match for scalar real `k`                                   |
| Per-play complex rotation             | `phase_shift(wf, θ)` for angle-only rotation; `scale` for real magnitude     | Direct match for these operations                                  |
| Waveform addition/product             | `sum(wf1, wf2)` / `mix(wf1, wf2)`                                           | Target/compiler support is required                                |

The standard OpenPulse grammar lists `gaussian`, `sech`, `gaussian_square`, `drag`, `constant`,
and `sine` as waveform-template examples. It also defines `mix`, `sum`, `phase_shift`, `scale`.

### (a) Is `extern` the right portable model for named/vendor pulses?

**It is the right semantic model, but not by itself a portable implementation model.**

The specification describes waveform templates as functions "provided by the target device" and
declared with `extern`. An `extern` declaration says what function is expected; it does not
define a universal implementation or universal parameter ABI.

```qasm
extern vendor_linear_chirp(
    complex[float[64]] amp,
    duration d,
    float[64] f_start,
    float[64] f_end,
    angle[64] phase
) -> waveform;
```

is appropriate for a vendor extension, but portable only across targets that agree on:

1. the external symbol name;
2. parameter types and ordering;
3. units and numerical interpretation;
4. duration/sample-rate rules;
5. amplitude limits and clipping behavior;
6. whether evaluation occurs at compile time or in real time.

For a closed IR union, retain the external function's fully qualified name and parameter
dictionary in the IR, but treat it as a **target capability requirement**, not as a universally
executable OpenPulse construct.

### (b) Does per-play amplitude scaling lower to `scale(wf, k)`?

**Yes, for a real scalar amplitude factor.**

```qasm
play(frame0, scale(wf, k));
```

OpenPulse defines `scale(waveform wf, float factor) -> waveform` as scaling the waveform samples'
amplitude. If your IR permits a complex per-play multiplier, split into magnitude and phase:
`complex scale c = r · exp(iθ)` lowers conceptually to `scale(phase_shift(wf, θ), r)`, subject to
the target's support for the required runtime expressions and `angle` conversions.

### (c) Can a linear-chirp sine use standard templates?

**No, not with the standard `sine` signature.**

```qasm
extern sine(complex[float[size]] amp, duration d, float[size] frequency, angle[size] phase) -> waveform;
```

That describes a fixed-frequency sine, not a frequency function `f(t)`. A linear chirp must be
represented as either:

1. explicit samples, e.g. `exp(i(φ0 + 2π(f0 t + ½ αt²)))`; or
2. a target-specific external template such as `extern chirp(...) -> waveform`; or
3. multiple segmented fixed-frequency waveforms, if the target and timing semantics allow.

Segmenting is not generally equivalent to a continuous linear chirp and can introduce phase
discontinuities unless phase accumulation is handled explicitly.

### (d) Is a flat-top square with linear ramps standardized?

**No.** `gaussian_square` is specifically a flat-top pulse with Gaussian-shaped edges. The
OpenPulse template list has no `linear_square`, `trapezoid`, or linear-ramp flat-top template.
Use explicit samples, or define a vendor extension:

```qasm
extern linear_square(complex[float[64]] amp, duration d, duration rise, duration fall) -> waveform;
```

---

# 2. Units and amplitude

## OpenPulse amplitude semantics

OpenPulse specifies waveform amplitudes as complex envelope values. It defines `amp` as the
waveform amplitude and permits explicit complex samples such as:

```qasm
waveform wf = [1+0im, 0+1im, 1/sqrt(2)+1/sqrt(2)im];
```

It does **not** define a physical amplitude unit, amplitude-to-voltage conversion, dBm
convention, impedance, DAC full-scale voltage, or universal amplitude range. Thus this is not
standard OpenPulse:

```qasm
constant(0.2 V, 100 ns)     // NOT valid
constant(-10 dBm, 100 ns)   // NOT valid
```

OpenPulse has no standard `V`, `mV`, `dBm`, `W`, or general unit annotation for waveform
amplitudes.

## Platform conventions

| Platform                       | Documented waveform amplitude convention                                                                                          | Physical volts/dBm in the pulse language? |
| ------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| OpenPulse                      | Abstract complex envelope samples and template amplitudes; the specification does not define a physical amplitude unit or universal range | No                                        |
| Old Qiskit Pulse               | Complex-valued samples with **maximum unit norm**; pulse samples are dimensionless relative envelope values, time in backend `dt` cycles | No portable voltage meaning               |
| AWS Braket Pulse               | Complex waveform amplitudes; AWS examples explicitly describe amplitude `0.1` as "arbitrary units"                                 | No standard volts/dBm in the Braket waveform abstraction |
| OQC OpenQASM/OpenPulse         | Exposes OpenPulse waveform templates; reports support for `constant`, `gaussian`, `sech`, `gaussian_square`, `drag`, `sine`, `arbitrary`, `scale`; the public capability table does not define a universal physical amplitude unit | No portable volts/dBm convention          |

### Important distinction

"Normalized" does not necessarily mean that every provider uses exactly the same electrical
normalization. It normally means the value is a dimensionless envelope coordinate interpreted by
a provider-specific calibrated signal chain. One provider may map `|sample| = 1` to a DAC
full-scale setting, while another may impose a different scale, attenuation, or waveform-specific
limit.

## Recommended volts-to-OpenPulse lowering

Do not lower physical volts directly to a bare OpenPulse number without target calibration
metadata. Use a target-specific conversion:

```text
normalized_amplitude =
    (requested_voltage / target_full_scale_voltage)
    × target_port_gain
    × target_attenuation_correction
```

More generally, define a target calibration function
`u = A_target(port, requested_physical_amplitude, frequency, impedance, time)` and then lower:

```qasm
waveform wf = gaussian(u + 0im, 100dt, 16dt);
play(frame0, wf);
```

The target profile should carry at least:

| Required metadata                        | Purpose                                                        |
| ---------------------------------------- | -------------------------------------------------------------- |
| Port or frame                            | Selects the physical signal path                               |
| DAC/full-scale mapping                   | Converts normalized envelope values to electrical amplitude    |
| Impedance convention                     | Distinguishes voltage, power, and delivered load               |
| Analog gain/attenuation                  | Accounts for the control chain                                 |
| Maximum sample magnitude                 | Detects clipping                                               |
| Frequency-dependent calibration          | Handles gain and transfer-function variation                   |
| Complex IQ imbalance model, if applicable| Converts complex envelope to actual I/Q output                 |

If no such target profile exists, the only portable lowering is to preserve the voltage quantity
as an IR annotation or compilation-time requirement and reject the program when no conversion is
available.

---

# 3. Classical types

OpenQASM 3 has scalar classical types including `bit`, `bool`, `int[n]`, `uint[n]`, `float[n]`,
`angle[n]`, `complex[float[n]]`, `duration`, and `stretch`. Arrays use a separate
`array[base_type, dimensions...]` declaration.

## IR-to-OpenQASM mapping

| IR field                                    | OpenQASM 3 mapping                                                        |
| ------------------------------------------- | ------------------------------------------------------------------------- |
| `dtype = bool`, scalar                      | `bool x;`                                                                 |
| `dtype = bit`, scalar measurement bit       | `bit x;`                                                                  |
| `dtype = int`, width `n`                    | `int[n] x;`                                                               |
| `dtype = uint`, width `n`                   | `uint[n] x;`                                                              |
| `dtype = float`, precision `n`              | `float[n] x;`                                                             |
| `dtype = complex`, component precision `n`  | `complex[float[n]] x;`                                                    |
| `dtype = angle`, precision `n`              | `angle[n] x;`                                                             |
| `shape = (d1,)`, base `float[n]`            | `array[float[n], d1] x;`                                                  |
| `shape = (d1,d2)`, base `complex[float[n]]` | `array[complex[float[n]], d1, d2] x;`                                     |
| `dtype = duration`                          | `duration x;`                                                             |
| `dtype = stretch`                           | `stretch x;` where supported                                              |
| `unit = "ns"`, `"us"`, etc. on a duration   | Use a duration literal such as `10ns`; do not attach a unit to an arbitrary variable |
| `unit = "MHz"` on a float                   | **No standard OpenQASM type**; retain as IR metadata or lower to a target-defined convention |

## Arrays

OpenQASM 3 arrays are statically sized: `array[float[32], 3, 2] a;`. The standard supports arrays
whose base type is `int`, `uint`, `float`, `complex`, `angle`, `bool`, or `duration`. `bit`,
`bit[n]`, `stretch`, and quantum types are **not** valid array base types. Arrays cannot be
resized or reshaped, and the specification limits multidimensional arrays to at most seven
dimensions.

The current specification also states:

> "Arrays cannot be declared inside the body of a function or gate. All arrays must be declared
> within the global scope of the program."

Therefore a generic IR array declaration cannot always be lowered where it is syntactically
convenient. A compiler should hoist the array to global scope or materialize/unroll it.

## Real-time status

- `bool`, integer types, and measurement bits are the most generally useful real-time types.
- `float` is permitted by the language, but hardware support is implementation-dependent.
- `complex` is permitted, but the specification explicitly warns that real-world hardware may not
  support runtime manipulation of complex values.
- Arrays are statically typed and representable, but global declaration and controller-memory
  restrictions make runtime array use target-dependent.
- Compile-time evaluation is expected for expressions involving literals and `const` values;
  runtime support for transcendental functions and complex arithmetic is implementation-specific.
- `waveform` is not an ordinary classical variable type; it is a pulse-level value used by
  calibration constructs.

Accordingly, mark each IR variable as one of:
`compile_time` / `controller_runtime` / `measurement_feedback_runtime` / `pulse_parameter_runtime`.

Do not assume that a syntactically valid `float`, `complex`, or array declaration is executable on
hardware.

## Variables in `cal` and `defcal`

Calibration blocks have a calibration-specific scope. The precise rules can depend on the loaded
calibration grammar, so an IR should not assume that ordinary circuit-scope declarations and
calibration-scope declarations have identical visibility or lifetime.

OpenPulse examples permit waveform and frame declarations in `cal` and `defcal` contexts, and
`play` is restricted to `defcal` in the OpenPulse grammar.

Practical restrictions for a portable lowering:

1. Keep arrays at global scope unless the selected calibration grammar explicitly supports them locally.
2. Use scalar calibration parameters for pulse duration, frequency, phase, amplitude, and shape parameters.
3. Require waveform duration to be definite and realizable on the associated port.
4. Treat runtime `float`/`complex` manipulation inside calibration code as target-dependent.
5. Do not assume an arbitrary IR function body can be embedded as a `defcal`; calibration grammar
   support is vendor-selectable.

## Physical units on variables

**No general physical-unit system exists in OpenQASM 3.** Standard timing units are
`ns, μs, us, ms, s, dt`, and `angle` represents a fixed-point angle modulo `2π`. There is no
standard variable type or syntax for a frequency in MHz, an amplitude in volts, a power in dBm,
or a resistance in ohms.

Use one of:

1. compiler-side unit checking and conversion;
2. IR metadata such as `{value: 5.0, unit: "GHz"}`;
3. target-defined extern functions;
4. a target profile that specifies the convention for bare `float` values.

OpenPulse frame construction commonly uses a bare floating-point carrier frequency, but the unit
convention is supplied by the target/calibration environment rather than by a general OpenQASM
physical-unit type.

---

# 4. Control flow

## Direct mappings

| IR construct                | OpenQASM 3 lowering                                            |
| --------------------------- | -------------------------------------------------------------- |
| `repeat(count) { body }`    | `for int i in [0:count-1] { body }`                            |
| `for(var, integer range)`   | `for int i in [start:step:end] { ... }`                        |
| `for(var, explicit set)`    | `for float f in {a,b,c} { ... }`, or corresponding scalar type |
| `if(var) { ... }`           | `if (var) { ... }`                                             |
| `if/else`                   | `if (var) { ... } else { ... }`                                |
| `while(cond)`               | `while (cond) { ... }`                                         |
| `switch(value)`             | `switch (value) { case ... {} default {} }`                    |
| Timing-constrained region   | `box[...] { ... }`                                             |

The official grammar has `for`, `if`, `while`, and `switch` productions; **it has no `repeat`
production.**

## Is there a plain `repeat N times`?

**No.** Lower it to a `for` loop over an index:

```qasm
for int i in [0:n-1] {
    body;
}
```

The index may be unused. If `n` is zero, the compiler must handle the resulting empty range
correctly; do not blindly emit an invalid descending or negative range.

## Integer ranges

OpenQASM 3 supports range expressions `[start:step:end]` with an implicit step of `1` when
omitted.

```qasm
for int i in [0:n-1]    { /* repeated body */ }
for int i in [0:2:n-1]  { /* every second index */ }
```

## Real-valued sets

The grammar permits the iterator type to be a scalar type; the classical specification describes
`for <type> <name> in <values>`. Therefore a finite literal set of real values can be:

```qasm
for float[64] f in {5.0e9, 5.1e9, 5.2e9} {
    // body
}
```

However, this does **not** make frequency iteration universally portable in hardware. Three
separate questions must be checked:

1. **Language validity:** Is the iterator type and set expression accepted?
2. **Controller capability:** Can the controller hold and update a runtime floating-point variable?
3. **Pulse/calibration capability:** Can the target use `f` in a frame or `set_frequency`
   operation at runtime?

For a compile-time sweep, prefer `const` values or unroll the loop in the compiler.

## Is `for float f in {...}` compile-time or real-time?

**The syntax alone does not force either behavior.** OpenQASM 3 supports low-level classical
control flow, and implementations may execute supported loop constructs on a controller. At the
same time, compilers are expected to constant-fold expressions involving literals and `const`
values. Thus:

- A loop over a literal or `const` finite set may be unrolled at compile time.
- A loop whose values depend on runtime state may require real-time controller support.
- A target may reject runtime floating-point iteration even though the source is legal OpenQASM.
- Inside a `defcal`, duration constraints may force compile-time resolution or rejection.

For a portable IR, annotate loop intent explicitly (`unroll_required` / `controller_runtime` /
`either`) and make frequency sweeps `unroll_required` unless the target advertises runtime
floating-point frame control.

## Control flow inside `cal`/`defcal`

> `defcal` bodies must have a definite duration known at compile time, regardless of parameters
> or system state. If control flow is present, every branch must have definite and equivalent
> duration; loops must have a resolvable definite duration.

```qasm
defcal reset $0 {
    bit res = measure $0;
    if (res) {
        play(frame0, corrective_pulse);
    } else {
        delay[corrective_duration] frame0;   // equal duration required
    }
}
```

A loop is acceptable only if the compiler can determine the total duration:

```qasm
defcal repeated_pulse $0 {
    for int i in [0:3] {
        play(frame0, wf);
    }
}
```

This is **not** generally acceptable as a portable calibration body:

```qasm
defcal bad $0 {
    while (runtime_condition) {  // total duration not statically bounded
        play(frame0, wf);
    }
}
```

`cal` and `defcal` also differ in pulse placement: the OpenPulse grammar states that `play` may
appear only inside `defcal`, while waveform construction and other calibration operations can
occur in `cal` contexts.

## `box`

`box` is not a loop. It is a timing/scheduling region used to constrain the relative timing of its
contents. It is useful when lowering an IR "timed block," but it does not replace `repeat`,
`for`, or `while`.

---

## Recommended IR design changes

```text
Waveform:
  shape: ...
  amplitude:
    value: ...
    unit: normalized | V | dBm
  duration:
    value: ...
    unit: ns | us | s | dt
  realization:
    explicit_samples | target_extern | compiler_generated

ControlFlow:
  execution: compile_time | controller_runtime
  duration: static | dynamic
  calibration_safe: true | false

Variable:
  dtype: ...
  shape: ...
  unit: ...
  storage: compile_time | controller_runtime
```

The most important rule is to preserve the distinction between **physical amplitude** and
**OpenPulse normalized envelope amplitude**, and to require an explicit target calibration
conversion before emitting the latter.

---

## Primary citations

- https://openqasm.com/language/openpulse.html
- https://openqasm.com/versions/3.1/language/openpulse.html
- https://openqasm.com/versions/3.0/language/openpulse.html
- https://openqasm.com/language/types.html
- https://openqasm.com/language/classical.html
- https://openqasm.com/language/scope.html
- https://openqasm.com/language/pulses.html
- https://openqasm.com/grammar/index.html
- https://openqasm.com/versions/3.0/intro.html
- https://arxiv.org/pdf/2104.14722
- https://docs.quantum.ibm.com/api/qiskit/1.4/qiskit.pulse.library.Waveform
- https://arxiv.org/pdf/2004.06755 — Qiskit Pulse paper (unit-norm samples)
- https://docs.aws.amazon.com/braket/latest/developerguide/braket-pulse-control.html
- https://amazon-braket-sdk-python.readthedocs.io/en/stable/_apidoc/braket.pulse.waveforms.html
- https://docs.oqc.app/qasm3.html
