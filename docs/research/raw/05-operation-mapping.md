# Raw Perplexity result — 05: Operation-by-operation mapping of eq1_pulse ops to OpenPulse

> Model: `sonar-reasoning-pro` (reason, high search context). Query: exact OpenQASM 3 / OpenPulse
> counterpart (or explicit "none exists") for conditional play, record/trace, discriminate,
> store, and dc_comp.
>
> Citation URL list truncated to primary sources at the end.

---

## Bottom line

OpenQASM 3/OpenPulse is a **pulse-scheduling and calibration language**, not a complete
experiment-result or acquisition-processing language. Several requested operations map only
partially to OpenPulse primitives; `time_of_flight`, named result accumulation, and a
standardized DC-compensation operation have **no standard OpenQASM 3/OpenPulse counterpart**.

The relevant standard keywords are: `defcalgrammar`, `cal`, `defcal`, `frame`, `port`,
`waveform`, `play`, `capture`, `delay`, `barrier`, `extern`, `scale`, `set_phase`, `shift_phase`,
`set_frequency`, `shift_frequency`, `get_phase`, `get_frequency`, and `discriminate`.

---

## 1. Conditional `play`

| Pulse IR operation                                    | OpenQASM 3/OpenPulse counterpart                | Exact status                                                                                        |
| ----------------------------------------------------- | ----------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `play(channel, pulse, scale_amp)`                     | `play(frame, waveform)`                         | **Yes, partial.** `channel` becomes a `frame`; `pulse` becomes a `waveform`. Amplitude scaling is normally `scale(waveform, factor)`, or an amplitude argument to a waveform constructor. |
| `cond=var`                                            | OpenQASM `if` using a `bit` or Boolean expression | **Yes in a `defcal`, subject to timing restrictions.**                                              |
| Play only when a real-time bit is set                 | `if (b) { play(frame, waveform); }`             | **Not sufficient by itself for a valid fixed-duration `defcal`.** A conditional branch must have definite and equivalent compile-time duration. |
| `if (b) { play(...); }` directly inside an outer `cal { ... }` | —                                       | **No standard counterpart as written.** `cal` is primarily the calibration scope/configuration container; standard examples put pulse instructions inside nested `defcal` bodies. |
| `scale_amp`                                           | `scale(waveform, factor)`                       | **Yes, but the keyword is `scale`, not `scale_amp`.**                                               |

```qasm
play(frame fr, waveform wfm);
play(drive_frame, scale(my_waveform, amp_scale));
```

Standard waveform constructors instead expose an amplitude parameter:

```qasm
extern constant(complex[float[size]] amp, duration d) -> waveform;
extern gaussian(complex[float[size]] amp, duration d, duration sigma) -> waveform;
extern drag(complex[float[size]] amp, duration d, duration sigma, float[size] beta) -> waveform;
```

OpenPulse does **not** define a generic `scale_amp` argument on `play`; `scale` is the documented
waveform operation for scaling an existing waveform.

### Conditional example

```qasm
defcal conditional_play $0 {
    bit b = /* result of a real-time acquisition or measurement */;

    if (b) {
        play(drive_frame, pulse);
    } else {
        delay[durationof(pulse)] drive_frame;
    }
}
```

Both paths must have a **definite and equivalent duration resolvable at compile time**. Thus a
bare `if (b) { play(...); }` with no compensating `else` is generally not a valid fixed-duration
`defcal`: the true branch advances the frame, while the false branch does not. The `defcal`
duration requirement and equivalent-branch rule are explicit in the OpenQASM pulse specification.

`play` and `capture` also advance the relevant frame clock by the duration of their waveform or
acquisition. Durations must be realizable on the associated port's sample grid; otherwise
compilation must fail.

### Important limitation

Whether a particular vendor permits **real-time acquisition results to control pulse-level
branching** is implementation-dependent. OpenQASM 3 supplies the classical `if` construct, but
OpenPulse does not standardize the hardware path that converts an acquisition into a bit quickly
enough for feedback.

---

## 2. `record` and `trace`

### Exact documented capture signatures

| OpenPulse keyword/signature                                                | Return                | Meaning                                                            |
| -------------------------------------------------------------------------- | --------------------- | ------------------------------------------------------------------ |
| `extern capture_v0(frame output);`                                         | unspecified / none    | Minimum capture operation; data may go to an implementation-defined external buffer. |
| `extern capture_v1(frame output, waveform filter) -> complex[float[32]];`  | `complex[float[32]]`  | Integrated or filtered IQ value.                                   |
| `extern capture_v2(frame output, waveform filter) -> bit;`                 | `bit`                 | Discriminated binary result.                                       |
| `extern capture_v3(frame output, duration len) -> waveform;`              | `waveform`            | Raw waveform / trace samples.                                      |
| `extern capture_v4(frame output, duration len) -> int;`                   | `int`                 | Count, for example a photon or trigger count.                      |

These are **documented vendor-defined extern signatures**, not universally implemented mandatory
acquisition modes.

### Mapping table

| Pulse IR operation                            | Closest OpenPulse form                        | Result                                                                                 |
| --------------------------------------------- | --------------------------------------------- | ---------------------------------------------------------------------------------------- |
| `record(channel, var, duration, integration=full)` | `var = capture_v1(acq_frame, filter)`    | **Partial match.** `capture_v1` returns integrated/filtered complex IQ, but the standard does not define a keyword called `full`. |
| `record(channel, var, duration, integration=demod)` | `var = capture_v1(acq_frame, kernel_waveform)` | **Partial match.** The filter/kernel is the documented mechanism for reducing the acquired signal to IQ. |
| `trace(channel, array_var, duration)`         | `array_var = capture_v3(acq_frame, duration)` | **Yes, conceptually.** `capture_v3` returns a raw waveform.                            |
| Discriminated acquisition                     | `bit b = capture_v2(acq_frame, filter)`       | **Yes, conceptually.** Thresholding/classification is performed by the vendor-defined capture implementation. |
| `time_of_flight`                              | —                                             | **NO standard counterpart.**                                                           |

The documented filter is a `waveform` that is dot-producted with the measured IQ data to produce
a single IQ value. Therefore, for demodulation/integration, the standard-level abstraction is:

```qasm
waveform kernel = /* vendor-defined integration/demodulation kernel */;
complex[float[32]] iq = capture_v1(acq_frame, kernel);
```

The OpenPulse specification does **not** state that capture automatically demodulates according
to the capture frame's frequency and phase. A frame does carry frequency and phase, and those
determine transmitted carrier frequency and phase; for capture, the standard explicitly
guarantees at least the capture *time*, while the filtering/demodulation behavior is
vendor-defined.

### Time of flight

There is no standard keyword such as `time_of_flight(...)`, `tof(...)`, or
`acquisition_delay(...)`. The available standard timing constructs are `delay[duration] frame;`,
`capture(frame, ...)`, and `barrier frame1, frame2;`.

A compiler or vendor may implement time of flight through a calibrated port delay, a frame or
hardware acquisition latency, a `delay` before capture, a vendor-specific capture frame, or
experiment configuration. But these are not equivalent standard OpenPulse syntax. Consequently:

> **`time_of_flight` has NO standardized OpenQASM 3/OpenPulse counterpart.**

---

## 3. `discriminate`

| Pulse IR operation                                                | OpenPulse counterpart                              | Exact status                                             |
| ----------------------------------------------------------------- | -------------------------------------------------- | -------------------------------------------------------- |
| `discriminate(target, source, threshold, rotation, projection=real)` | `extern discriminate(complex[float[64]] iq) -> bit;` | **Only a partial counterpart.**                        |
| `projection=imag`                                                 | Same extern, vendor-defined implementation         | **No standard projection keyword.**                      |
| `projection=abs`                                                  | Same extern, vendor-defined implementation         | **No standard projection keyword.**                      |
| `projection=phase`                                                | Same extern, vendor-defined implementation         | **No standard projection keyword.**                      |
| Explicit `threshold`                                              | `capture_v2(..., filter) -> bit` or vendor extern  | **Vendor configuration/extension, not specified by the language.** |
| Explicit `rotation`                                               | Vendor discriminator configuration or preprocessing| **Vendor configuration/extension, not specified by the language.** |

The standard documents:

```qasm
extern discriminate(complex[float[64]] iq) -> bit;
extern boxcar(waveform input) -> complex[float[64]];
```

and gives a conceptual processing chain:

```qasm
waveform raw_output = capture_v3(capture_frame, 16000dt);
complex[float[64]] iq = boxcar(raw_output);
bit result = discriminate(iq);
```

The language specifies neither the discriminator threshold nor a rotation/projection parameter.
Those are normally supplied through vendor calibration data, acquisition configuration, or a
vendor-specific extern. Thus:

> `extern discriminate(...) -> bit` is a **type-level hook**, not a standardized discrimination
> algorithm or parameter schema.

`capture_v2` is the closer single-instruction analogue when the hardware performs integration
and discrimination internally, but the standard does not define its threshold, rotation, or
projection semantics.

---

## 4. Named result streams and accumulation

### OpenQASM 3/OpenPulse

| Requested operation           | Standard counterpart                                       | Status                                                                 |
| ----------------------------- | ---------------------------------------------------------- | ------------------------------------------------------------------------ |
| `store(key, source_var, mode=last)` | Assignment, `return`, or vendor capture buffer       | **No standard named-result-store operation.**                          |
| `mode=average`                | —                                                          | **NO OpenQASM 3/OpenPulse counterpart.**                               |
| `mode=count`                  | `capture_v4(...) -> int` only for a hardware-defined count | **Partial only; not general result accumulation.**                     |
| `mode=trace`                  | `capture_v3(...) -> waveform`                              | **Partial only; acquires a trace but does not define named shot-stream storage.** |
| Named result streams          | —                                                          | **NO standard language concept.**                                      |
| Cross-shot accumulation       | —                                                          | **NO standard language concept.**                                      |
| Average, sum, append, histogram, buffer | —                                                | **NO standard OpenQASM 3/OpenPulse operators.**                        |

OpenQASM `extern` declarations can return values or invoke vendor-defined operations, and a
capture may write to an external buffer. However, the standard does not define a result-stream
type, shot index, named result key, accumulation mode, or cross-shot reduction operator.
Therefore:

> **Result accumulation is outside standard OpenQASM 3/OpenPulse and is normally handled by the
> job, backend, compiler, or experiment layer.**

### Comparison with QUA

| Capability            | QUA                                                    | OpenQASM 3/OpenPulse                             |
| --------------------- | ------------------------------------------------------ | ------------------------------------------------ |
| Declare output stream | `declare_stream()`                                     | **None standardized**                            |
| Save a value          | `save(value, stream)`                                  | **None standardized**                            |
| Save only final item  | `stream.save("name")`                                  | **None standardized**                            |
| Save all items        | `stream.save_all("name")`                              | **None standardized**                            |
| Buffering             | `.buffer(n)`                                           | **None standardized**                            |
| Averaging             | `.average()` or `buffer(...).map(FUNCTIONS.average())` | **None standardized**                            |
| Named result key      | `"name"` terminal                                      | **None standardized**                            |
| ADC trace stream      | `declare_stream(adc_trace=True)`                       | Closest is `capture_v3`, without QUA's pipeline  |

QUA explicitly separates program execution from result processing: `declare_stream()` creates an
output stream, `save()` inserts values, and `stream_processing()` defines buffering, averaging,
and terminal storage.

```python
I_st = declare_stream()
save(I, I_st)

with stream_processing():
    I_st.buffer(n_points).buffer(n_avg).map(FUNCTIONS.average()).save_all("I")
```

This is a close analogue to `store(..., mode=average)`, but it is a **QUA feature**, not an
OpenQASM feature.

### Qblox and Quantify

Qblox exposes acquisition and binning in the scheduler/instrument protocol rather than through
OpenPulse language constructs. Documented acquisition modes include scope/raw input, integration,
thresholded binary acquisition, and trigger counting.

Quantify/Qblox uses `BinMode` values:

| Acquisition/protocol use          | Documented bin modes             |
| --------------------------------- | -------------------------------- |
| `TriggerCount` on QRM             | `APPEND`, `DISTRIBUTION`, `SUM`  |
| `TriggerCount` on QTM             | `APPEND`, `SUM`                  |
| `Timetag` on QTM                  | `APPEND`, `AVERAGE`              |
| `TimetagTrace` on QTM             | `APPEND`                         |
| `Trace` on QRM/QRM-RF             | `AVERAGE`                        |
| `Trace` on QTM                    | `FIRST`                          |
| `ThresholdedTriggerCount`         | `APPEND`                         |

These are close operational analogues of `append`, `average`, and `count`, but they are
**Qblox/Quantify acquisition-protocol features**, not standard OpenQASM 3/OpenPulse keywords.

Amazon Braket result types and Qiskit primitives similarly define result handling at the
task/primitives layer — `Sample`, `Probability`, `Expectation`, `Variance` — rather than adding a
general OpenQASM result-stream language.

---

## 5. DC offset compensation

| Requested capability                        | OpenQASM 3/OpenPulse                                 | Status                                  |
| ------------------------------------------- | ---------------------------------------------------- | --------------------------------------- |
| Constant DC output offset                   | A `waveform` with zero-frequency/baseband behavior, if supported by the vendor | Partial, vendor-dependent |
| Play a corrective waveform                  | `play(frame, waveform)`                              | Yes                                     |
| Automatically calculate compensating area   | —                                                    | **NO standard counterpart**             |
| `max_amp` constraint for compensation       | —                                                    | **NO standard counterpart**             |
| `rise_time` / `fall_time` parameters        | Construct a vendor waveform or use a vendor extern   | **No standard keyword**                 |
| Net-zero pulse transformation over a schedule | —                                                  | **NO standard counterpart**             |
| Static calibrated DC offset                 | Vendor configuration / calibration                   | **NO standard OpenPulse keyword**       |
| Bias-tee/high-pass precompensation          | —                                                    | **NO standard counterpart**             |

OpenPulse can express the **final corrective pulse if its samples are already known**:

```qasm
waveform compensation = /* calculated externally or by vendor */;
play(compensation_frame, compensation);
```

It cannot standardly express "calculate a waveform whose integral cancels all preceding pulses."
That calculation is a scheduler/compiler/vendor extension.

### Qblox

```python
create_dc_compensation_pulse(...)   # params: pulses, sampling_rate, port, amplitude,
                                    #         reference_magnitude, duration, t0
```

Calculates a square pulse whose area counteracts the specified pulses. Also:

```python
PulseCompensation(body, max_compensation_amp=..., time_grid=..., sampling_rate=...)
```

which inserts square compensation pulses so the integrated output is zero for each port.
Qblox's `VoltageOffset` is a different feature: it sets a constant output voltage and is not
itself an automatic net-zero corrective-pulse algorithm.

### Quantum Machines / QUA

```python
set_dc_offset(element, element_input, offset)
```

plus configuration-level analog-output offsets, and ramp-to-zero behavior for returning an
element from its current DC value to zero over a duration. Not OpenPulse standard keywords.

### Zurich Instruments

Exposes DC voltage offsets through calibration properties such as `voltage_offset`, and supports
HDAWG real-time precompensation: exponential, bounce, high-pass, and FIR compensation. These are
hardware calibration/filter features, not a standard OpenPulse `dc_comp` instruction.

> **Automatic DC-offset compensation is necessarily a vendor/compiler/scheduler extension in
> OpenQASM 3/OpenPulse.** The portable OpenPulse fallback is to calculate the compensation
> waveform outside the language and then use ordinary `play(frame, waveform);`.

---

## Consolidated mapping

| Pulse IR operation                          | Exact OpenQASM 3/OpenPulse counterpart                                              | Standard status                                                            |
| ------------------------------------------- | ------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------- |
| `play(channel, pulse, scale_amp, cond=var)` | `play(frame, scale(waveform, factor))` inside a `defcal`; conditional with OpenQASM `if` | **Partial.** Conditional branches must have definite, equivalent duration. |
| `record(..., integration=full)`             | `capture_v1(frame, waveform) -> complex[float[32]]`                                 | **Partial.** No standard `full` keyword.                                   |
| `record(..., integration=demod)`            | `capture_v1(frame, filter_waveform) -> complex[float[32]]`                           | **Partial.** Kernel/filter is the documented mechanism; frame demodulation is not specified. |
| `trace(...)`                                | `capture_v3(frame, duration) -> waveform`                                            | **Closest direct counterpart.**                                            |
| `time_of_flight`                            | —                                                                                    | **NO counterpart exists in standard OpenPulse.**                           |
| `discriminate(...)`                         | `extern discriminate(complex[float[64]]) -> bit` or `capture_v2(frame, waveform) -> bit` | **Partial.** Threshold, rotation, and projection are vendor-defined.   |
| `store(..., last)`                          | —                                                                                    | **NO standard named result-stream counterpart.**                           |
| `store(..., average)`                       | —                                                                                    | **NO counterpart exists.** Use QUA/Quantify/backend processing.            |
| `store(..., count)`                         | `capture_v4(...) -> int` only for hardware-defined counts                            | **Partial, not general accumulation.**                                     |
| `store(..., trace)`                         | `capture_v3(...) -> waveform`                                                        | **Acquisition only; no standard named stream.**                            |
| `dc_comp(...)`                              | Precomputed `play(frame, compensation_waveform)`                                     | **Only manual waveform playback.** Automatic compensation has no standard counterpart. |

The practical architecture is therefore: use OpenPulse for **frames, waveforms, timing,
playback, acquisition invocation, and real-time branch structure**; use vendor extensions or the
experiment/job layer for **time-of-flight calibration, discrimination parameters, shot
accumulation, binning, averaging, and DC-compensation synthesis**.

---

## Primary citations

- https://openqasm.com/versions/3.0/language/openpulse.html
- https://openqasm.com/language/openpulse.html
- https://openqasm.com/versions/3.1/language/openpulse.html
- https://openqasm.com/versions/3.0/language/pulses.html
- https://openqasm.com/language/pulses.html
- https://arxiv.org/pdf/2104.14722
- https://docs.oqc.app/qasm3.html
- https://docs.quantum-machines.co/0.1/qm-qua-sdk/docs/Guides/stream_proc/
- https://docs.quantum-machines.co/1.2.3/docs/API_references/qua/dsl_main/
- https://docs.qblox.com/en/main/autoapi/qblox_scheduler/operations/pulse_library/index.html
- https://docs.qblox.com/en/v2026.04.0/_modules/qblox_scheduler/operations/pulse_compensation_library.html
- https://quantify-os.org/docs/quantify-scheduler/dev/reference/qblox/Acquisition%20details.html
- https://docs.qblox.com/en/main/products/architecture/modules/qrm.html
- https://docs.zhinst.com/hdawg_user_manual/functional_description/specific/pre_compensation.html
- https://docs.zhinst.com/labone_q_user_manual/core/functionality_and_concepts/02_logical_signals/concepts/02_calibration_properties.html
- https://docs.aws.amazon.com/braket/latest/developerguide/braket-result-types.html
