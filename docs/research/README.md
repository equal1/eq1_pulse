# docs/research

Research notes backing design decisions. Each raw file is a verbatim (or near-verbatim) dump of a
web-grounded research query, kept because the results exceeded normal tool output limits and are
expensive to reproduce.

## Assessments

| Document                                                              | Topic                                                                     |
| --------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| [openpulse-alignment-assessment.md](openpulse-alignment-assessment.md) | How eq1_pulse's builder and models align with OpenPulse / OpenQASM 3, and whether `Schedule` can be eliminated. **Start here.** |
| [PR #7](https://github.com/equal1/eq1_pulse/pull/7) | The work that came out of it: isolate `Schedule`, unify on `OpSequence`, add the opaque `ExternalBlock`. Remaining follow-on work is tracked in [#8](https://github.com/equal1/eq1_pulse/issues/8). |
| [pydantic-json-schema-assessment.md](pydantic-json-schema-assessment.md) | Why every `model_json_schema()` override in `models/` was silently bypassed, what the published OpenAPI document was actually describing, and the conversion to `__get_pydantic_json_schema__`. |
| [sweeps-eq1lab-integration.md](sweeps-eq1lab-integration.md) | How eq1lab would consume the sweeps design in `docs/plans/sweeps-plan.md`, judged against the authoritative `eq1lab-experiments` corpus (`common_exp_lib`, `experiments/beta2`) and the `hp-peti/260824-qblox-branch-lift` qblox-pulsing branch: `@apparatus_pulse_action` typed signatures are `SweepDecl`s, `do_nd_inner_loop`'s positional level list is `ProgramArguments.sweeps`, `InnerTogetherSweep`→`SweepGroup`, and every derived sweep is a host-side affine transform of a compact endpoint (the manual form of `affine_form()`). `ParameterExpr` / `{np.expr}` is an eq1x-scripts-only construct, unused in eq1lab-experiments. Reopens no §9 decision; the corpus is a close structural match for the design. |

## Raw research dumps

| File                                                                                             | Query                                                                                                                     |
| ------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------- |
| [raw/01-openqasm3-openpulse-timing.deep-research.md](raw/01-openqasm3-openpulse-timing.deep-research.md) | Exhaustive reference on the OpenQASM 3 / OpenPulse timing and scheduling model: `duration`, `stretch`, `durationof`, `delay`, `barrier`, `box`, frames/ports, `play`/`capture`, waveform templates, real-time feedback, adoption status 2025–2026. |
| [raw/02-framework-timing-models.deep-research.md](raw/02-framework-timing-models.deep-research.md)       | How pulse frameworks represent timing, and the industry trend away from absolute schedules: Qiskit `Schedule` vs `ScheduleBlock`, Qiskit Pulse deprecation/removal, quantify-scheduler, Pulser, Braket, QUA, LabOne Q, Qibolab, oqpy; standard lowering algorithm from reference-point constraints to OpenPulse. |
| [raw/03-builder-migration-strategy.md](raw/03-builder-migration-strategy.md)                             | Can `box` + `delay` + `barrier` + `stretch` subsume a reference-point schedule? Minimal portable timing vocabulary; builder-DSL idioms in oqpy / LabOne Q / Qiskit / QUA / Pulser; deprecation-and-migration patterns; zero-duration ordering; multi-channel atomic measurement. |
| [raw/04-channel-vs-frame-port.md](raw/04-channel-vs-frame-port.md)                                       | Flat `channel` vs OpenPulse `port` + `frame`; quantify's `(port, clock)` pair in detail; Braket / LabOne Q / Qibolab / old Qiskit Pulse comparison; recommendation for a portable JSON IR. |
| [raw/05-operation-mapping.md](raw/05-operation-mapping.md)                                               | Operation-by-operation mapping of eq1_pulse ops to OpenPulse: conditional play, `record`/`trace` vs `capture_v0..v4`, `time_of_flight`, `discriminate`, `store` (result streams), `dc_comp`. Marks explicitly where no counterpart exists. |
| [raw/06-waveforms-units-types-control-flow.md](raw/06-waveforms-units-types-control-flow.md)             | Waveform typing (closed union vs `extern` templates), amplitude units (normalised vs volts), OpenQASM 3 classical types and array restrictions, control-flow mapping and `cal`/`defcal` duration rules. |
| [raw/07-pydantic-json-schema-customisation.deep-research.md](raw/07-pydantic-json-schema-customisation.deep-research.md) | Pydantic v2 JSON Schema customisation: why overriding `model_json_schema()` is bypassed for nested models, the `__get_pydantic_json_schema__` / `__get_pydantic_core_schema__` hooks, `WithJsonSchema` / `SkipJsonSchema` / `json_schema_extra` / `GenerateJsonSchema` and their precedence, validation vs serialization modes, `json_schema_input_type`, and FastAPI's `-Input`/`-Output` split. |

## Key primary sources

- OpenQASM live spec — https://openqasm.com/language/
  - timing: https://openqasm.com/language/delays.html
  - OpenPulse grammar: https://openqasm.com/language/openpulse.html
  - pulse-level gates: https://openqasm.com/language/pulses.html
  - types: https://openqasm.com/language/types.html
  - reference grammar: https://openqasm.com/grammar/index.html
- OpenQASM 3 paper (Cross et al.) — https://arxiv.org/pdf/2104.14722
- OpenQASM repo — https://github.com/openqasm/openqasm (current version 3.1)
- oqpy (Python → OpenQASM 3 + OpenPulse) — https://github.com/openqasm/oqpy
- openpulse-python (reference AST/parser) — https://github.com/openqasm/openpulse-python
- AWS Braket Pulse — https://docs.aws.amazon.com/braket/latest/developerguide/braket-pulse-control.html
- OQC OpenQASM 3 / OpenPulse support matrix — https://docs.oqc.app/qasm3.html
- quantify-scheduler user guide — https://quantify-os.org/docs/quantify-scheduler/dev/user/user_guide.html
- Qiskit `ScheduleBlock` design issue — https://github.com/Qiskit/qiskit-terra/issues/5679
- Qiskit 2.0 migration (pulse removal) — https://quantum.cloud.ibm.com/docs/en/guides/qiskit-2.0
- LabOne Q sections & timing rules — https://docs.zhinst.com/labone_q_user_manual/core/functionality_and_concepts/03_sections_pulses/concepts/01_timing_rules.html

## Caveats

These are LLM-synthesised research summaries with citations, not primary documents. Spot-check
anything load-bearing against the linked spec pages before acting on it — the OpenPulse chapter in
particular still carries the notice *"The OpenPulse grammar is still in active development and is
liable to change."*
