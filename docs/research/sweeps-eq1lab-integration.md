# How eq1lab would consume eq1_pulse sweeps — integration assessment

**Date:** 2026-08-27
**Branch context:** `hp-peti/sweep-specs` (this repo);
`hp-peti/260824-qblox-branch-lift` (the eq1lab "qblox pulsing" branch);
`eq1lab-experiments@main` (the authoritative experiment corpus).
**Task:** R-1 in `docs/plans/sweeps-tasks.md` (that file and `docs/plans/sweeps-plan.md` are
removed when the sweeps branch merges — the **Background** section below reproduces everything from
them this assessment relies on, so it stands alone).
**Question asked:** how would eq1lab adopt the sweeps design — where do scan ranges live, what would
consume a `SweepDecl`, does `TogetherSweep` need more than `SweepGroup`, is the argument payload
compatible, which of `normalize_sweep_argument`'s forms survive, and how far does `ParameterExpr`
reach past the expression grammar (§5).

This is a survey. It changes nothing in this repo and proposes no eq1lab change. `§N` markers
throughout point at the digested design in **Background**, not at the deleted plan file.

### Which sources are authoritative

| Source | Weight | Why |
| --- | --- | --- |
| **`../eq1lab-experiments`** — `common_exp_lib/sequence_lib/standard_sequence.py` and `experiments/beta2/**` | **authoritative** | current, run against real hardware, uses the current `@apparatus_pulse_action` / `do_nd_inner_loop` inner-loop API |
| **`../eq1lab`** on `hp-peti/260824-qblox-branch-lift` | authoritative for the qblox consumer | the branch that lowers inner-loop sweeps to a `qblox_scheduler` schedule |
| `../eq1x-scripts` (`opx_scripts_alpha4/**`, `experiments/tno_*/**`) | **not authoritative** | a separate, older YAML-driven runner whose `input:` block and `{np.expr: …}` mechanism (`ParameterExpr`) are **not used anywhere in `eq1lab-experiments`**. Cited below only where it shows a *different* design the plan should be aware of, never as evidence of what eq1lab needs. |

Perplexity was not needed — every load-bearing fact is in the checkouts.

---

## Background: the sweeps design, digested

`docs/plans/sweeps-plan.md` and `docs/plans/sweeps-tasks.md` are removed when the sweeps branch
merges. This section reproduces the parts this assessment leans on, so it stands alone. Section
markers below (§2.2, §9 Q17, …) refer to the plan as it stood at
`hp-peti/sweep-specs` on 2026-08-27.

### The purpose (§0)

Store an experiment **once**, as a pulse program, and invoke it again with different sweep ranges.
Everything else follows: values come from outside (the program cannot embed or unroll them), they
travel on every invocation (so their encoding matters — a linear sweep is three numbers), and the
nesting structure must be readable off the declarations without walking loop bodies.

### Framing (§1)

- **A sweep is rank-1; a value is rank-0.** A sweep is a *list*, not an "axis": items may repeat
  and need not be ordered.
- **Transforms on sweeps are ordinary expressions** — `sweep("d") * ext("m") + ext("o")` is a
  `BinaryExpr` tree over a `SweepExpr` leaf, the same nodes and wire form scalars already use. There
  is no separate transform model and no assignment (§4.2).
- **Values are supplied per invocation; `default` is a fallback.**
- **Compact forms are first-class** as supplied values, not an optimisation a consumer applies.
- **Nesting order has one source per sweep** — the `for_` that consumes it, or declaration order if
  none does. No `placement` field.
- **eq1_pulse declares and never enforces** — bounds, units, lengths travel on the declaration;
  nothing here evaluates or materialises a sweep.
- **Units are compared, never converted** — a supplied unit must equal the declared one as a
  string.

### Models

- **`SweepValue` (§2.1):** `LinSpace | Range | NumpyIntArray1D | NumpyFloatArray1D |
  NumpyComplexArray1D`. `LinSpace` = `{start, stop, num}` (O(1)); `Range` = `{start, stop, step}`
  (O(1)); arrays are O(n). Decidable by wire shape, no tag.
- **`SweepDecl` (§4.1):** the list-valued sibling of `ParameterDecl` — `name`, `dtype`, `shape`,
  `unit`, `default`, `limits`. Counts as one level of nesting. `shape` pins an accepted length when
  the author wants one; left `None`, any length is accepted.
- **`SweepGroup` (§4.3):** `sweeps: list[SweepSpec]` (min 2), independent sweeps advanced in
  lock-step, occupying one nesting level of the length its members share. Members carry their **own**
  `dtype` / `unit` / `limits` (a voltage and a frequency routinely move together). `SweepSpec` is
  `SweepDecl` minus `op_type`, so the group's wire form writes `sweep_decl:` once, not per member.
  This is eq1lab's `TogetherSweep`, flattened onto the declarations.
- **`affine_form()` (§2.2):** an *advisory recogniser* in `utilities/`, not a model. Given an
  expression it returns `AffineForm(terms: dict[str, Expression], offset: Expression)` when the tree
  is `Σ scaleᵢ·sweepᵢ + offset`, else `None`. An affine transform of a `LinSpace` is a `LinSpace`
  (`scale*LinSpace(a,b,n)+off == LinSpace(scale*a+off, scale*b+off, n)`), and a linear combination
  of equal-length `LinSpace`s likewise — which is why a group's members must be lock-step. A
  generator that wants to upload three numbers calls it and takes the fast path; one that does not
  evaluates the tree elementwise. Nothing in `models/` runs it. Compactness is therefore **not**
  guaranteed by the type — that is the deliberate cost of the 2026-08-26 revision (§17).
- **Rank enforcement (§3):** two annotated aliases over `Expression`, each running a bounded walk —
  `ScalarExpression` rejects a tree that reads any sweep (guards `ValueRef`, i.e. `Play.amplitude`,
  `Delay.duration`, `ConditionalBase.var`, … and, separately, `ExternalParamValue`);
  `SweepSource` requires one (guards `for_` items and sweep-read sites). `SweepExpr` is the only
  rank-1 leaf, spelled `{"sweep": "name"}`. `IndexExpr` (`sweep[i]`) and `LenExpr` (`len`) are the
  boundary back down: their operand is a `SweepSource` but they **produce a scalar**, and the rank
  walk does not descend into them. There is no `SweepRef` reference type (§3.4) — a sweep name is a
  plain `IdentifierStr` everywhere it appears.

### Expression grammar (§5) — the closed set

| Kind | Members |
| --- | --- |
| binary | `+  -  *  /  %`  (no `**`, no `//`, no `@`) |
| unary | `-`  (abs is `CallExpr("abs")`) |
| compare | `<  <=  >  >=  ==  !=` |
| logical | `and  or  not` |
| `CallExpr` functions | `min  max  abs  sqrt  sin  cos  tan  exp  log`  — and nothing else |
| `IndexExpr` | `sweep[i, …]` — operand is a sweep, indices are scalars |
| `LenExpr` | `len(sweep)` → int |

No attribute access, list/dict literals, comprehensions, subscripting of non-sweeps, or `numpy`
beyond those nine function names. Every operator is elementwise over a sweep; a node is rank-1
exactly when an operand is.

### Iteration and nesting (§6, §7)

`IterableSequence = LinSpace | Range | NumpyIterableArray | SweepSource | Indices`. `Indices`
iterates `0..count-1` (index iteration; the value form binds the item itself). Nesting order:
unconsumed sweeps in declaration order (host drives them, always outermost), then consumed sweeps
in `for_` nesting order. A sweep may be consumed by **at most one** `for_`. A group contributes one
dimension; a zipped `for_` must name members of one group (or a base plus sweeps derived from it).

### Builder (§8)

`sweep("vg")` returns an `Expr` (a `SweepExpr` leaf); `sweep_decl(name, dtype, …)` declares a
supplied sweep; `sweep_group()` declares a lock-step group. A transform has no name — it is written
where it is read.

### Not in scope (§10)

- **Categorical sweeps** over channel / pulse references — they make per-channel scheduling
  data-dependent. `SweepValue` is numeric.
- **Combining sweeps from different nesting levels** — `sweep("d1") + sweep("d2")` where `d1`, `d2`
  are *nested* rather than grouped. That is an outer product, rank-2, and needs a broadcasting story
  the IR does not have. A full virtual-gate matrix over a 2-D charge-stability scan
  (`P1 = m11·d1 + m12·d2`) is the motivating case; the plan's answer is to flatten the scan to one
  `SweepGroup`, or to compute the combination **in the loop body** on the loop variables, where it
  is ordinary rank-0 arithmetic.

### Where the arithmetic runs (§4.4)

A transform in a loop's `items` runs **before** the loop (host generator, or list upload — three
numbers if `affine_form()` succeeds, one float per item otherwise). The same expression as an
in-body `assign` runs **per iteration on the sequencer** (one list + real-time arithmetic). Both
are kept: a primitive transpiler materialises the list; hardware that can compute per iteration
saves the upload.

### Worked examples this assessment refers to (§13)

```python
# C — virtual gates: one supplied sweep, two transforms of it (one dimension)
sweep_decl("detuning", "float", unit="mV")
var_decl("p1", "float", unit="mV"); var_decl("p2", "float", unit="mV")

with for_(["p1", "p2"], [
    sweep("detuning") * ext("vg.m11") + ext("vg.o1"),
    sweep("detuning") * ext("vg.m21") + ext("vg.o2"),
]):
    play("gate_1", step_pulse(amplitude=var("p1")))
    play("gate_2", step_pulse(amplitude=var("p2")))
# Reading one base makes the two transforms lock-step; no SweepGroup needed.
# Each is affine, so affine_form() still uploads three numbers per gate.
```

```python
# D — independent sweeps in lock-step: what SweepGroup is for
with sweep_group():
    sweep_decl("i_amp", "float", unit="mV")
    sweep_decl("drive_freq", "float", unit="MHz")     # different unit, same group

with for_(["a", "f"], [sweep("i_amp"), sweep("drive_freq")]):
    set_frequency("q0_drive", var("f"))
    play("q0_drive", square_pulse(duration="40ns", amplitude=var("a")))
```

```python
# G — sum/difference of two lock-step sweeps, computed before the loop
with sweep_group():
    sweep_decl("d1", "float", unit="mV")
    sweep_decl("d2", "float", unit="mV")

with for_(["c", "e"], [sweep("d1") + sweep("d2"), sweep("d1") - sweep("d2")]):
    ...
```

### The invocation payload (T7 / §16, §9 Q18–Q19)

`ProgramArguments` is a model in `models/arguments.py`, published in the schema — so a stored
experiment *and* the arguments it ran with are both validated artifacts. It splits `parameters`
(scalars) from `sweeps`. `sweeps` is a **nested list of levels**, outermost first; a level with
several entries is a group. The nesting is an *assertion* checked against the program (§7 still says
position comes from the program alone), not a second source of truth. `check_arguments()` is a
separate advisory utility in `utilities/` — it compares names, units, group membership and lengths;
nothing calls it automatically.

### The 2026-08-26 revision (§17)

The design was widened from **affine-only** transforms (a modelled `AffineSweep` carrying `terms` +
`offset`) to **general elementwise arithmetic** over lock-step sweeps — every operator in §5,
products and quotients included. The `AffineSweep` model became the `affine_form()` recogniser.
Cross-level combination stayed rejected. Net: one grammar, spelled one way everywhere, at the cost
that compactness is now recognised rather than guaranteed.

### R-1's six questions (from `sweeps-tasks.md`)

1. Where do scan ranges live today — literals in scripts, or resolved from config per device?
2. What would consume a `SweepDecl` — trace `do_nd_inner_loop` / `nd_sweep` and find the seam.
3. Does anything need `TogetherSweep` semantics `SweepGroup` does not cover — esp.
   `SweepPlaceholder` and the `wrapped_nd_inner_loop` / QDAC-trigger path.
4. Does eq1lab have a payload shape T7's `parameters` / `sweeps` split would fight with?
5. Which of `normalize_sweep_argument`'s nine input forms would eq1lab still need after adopting
   `SweepValue`, and which are qcodes-compat shims droppable at the boundary?
6. How far does `ParameterExpr` reach — enumerate what eq1lab builds with it and check each against
   §5's grammar and §4's lock-step rule; anything needing two independent-length sweeps in one
   expression is the finding that would reopen §10.

R-1 "gates nothing" — D-1 through D-3 (the decisions it was meant to inform) are already closed. It
is kept because questions 2, 3, 5 and 6 are still worth answering before eq1lab adopts this.

---

## Findings summary

1. **Scan ranges are caller-supplied, as plan §9 Q17 assumes.** In `eq1lab-experiments`, an
   experiment script reads base ranges as `{start, stop, num}` / `{start, stop, step}` dicts from a
   per-experiment config (`get_experiment_meta_parameter("burst_duration", type=dict)`), optionally
   derives further ranges from them **in plain Python** (endpoint arithmetic — see finding 6), and
   passes concrete dicts/arrays positionally to `do_nd_inner_loop`. Nothing resolves a range from a
   calibration store by name; calibration values (`resonance_frequency`, an IF offset) enter only as
   *scalars the script adds to endpoints itself*. Plan §9 Q17 does **not** reopen.

2. **The thing that would consume a `SweepDecl` is the typed signature of an
   `@apparatus_pulse_action("qua")` function**, checked and lowered through
   `eq1lab_core.inner_loop.interface_types`. A parameter annotated
   `InnerLinSweep[Annotated[int, "Hz"]]` *is* a `SweepDecl` with `dtype` and `unit`;
   `InnerTogetherSweep[InnerLinSweep[…], InnerLinSweep[…]]` *is* a `SweepGroup`. On the qblox branch
   these feed `for_each_in_linspace_`, `for_each_in_zip_linspaces_`, `for_each_in_arange_`,
   `iterate_linspace_`, `iterate_array_` in `eq1lab/pulsing/qblox/_loops.py`, with an explicit
   index variable available. The mapping to plan §6 is close to one-to-one.

3. **`SweepGroup` covers `TogetherSweep` / `InnerTogetherSweep` completely**, and Q10's decision to
   give members their own `dtype` / `unit` / `limits` is required: the beta2 vector-scan programs
   group two `float`/`V` sweeps today, and the framework's own type allows grouping a `V` with a
   `Hz`. `SweepPlaceholder` and the `wrapped_nd_inner_loop` / QDAC-trigger path map to an
   *unconsumed* `sweep_decl(name, shape=(N,))` — but that path is a host-DC-sweep concern that the
   beta2 pulse programs do not touch; there all sweeping is inner (hardware) and every sweep is
   consumed by a `for_each_in_*`.

4. **The argument payload is shape-compatible with T7 and, on the authoritative corpus, already
   split.** `do_nd_inner_loop(("if_freq", d0), ("iteration", d1), [("bv0", d2a), ("bv1", d2b)],
   outputs=…, actions=[prog])` is exactly `ProgramArguments.sweeps` as an ordered list of levels
   where a level may be a group (a sub-list). Scalars (`n_iterations`, LO frequency) are kept out of
   that call entirely — they are `ManualParameter`s / config reads — so eq1lab already separates
   `parameters` from `sweeps` the way T7 does. The `{np.expr}` mixing of derived channels into one
   ordered block that motivated the "friction" note in the previous draft is an **eq1x-scripts**
   trait, not an eq1lab one.

5. **Only three of `normalize_sweep_argument`'s nine forms appear in the authoritative corpus** —
   `(name, {start, stop, num|step})`, `(name, array)`, and `[(name, …), (name, …)]` for a group.
   The six qcodes-object forms (`_LinSweep`, `_ArraySweep`, `_TogetherSweep`, generic
   `_AbstractSweep` incl. `LogSweep`) are used only in the framework's own `08_nd_sweeper` teaching
   examples. `SweepValue`'s `LinSpace | Range | array` union is a superset of what eq1lab experiments
   actually pass; the qcodes shims can be dropped at the eq1_pulse boundary with no corpus impact.

6. **`ParameterExpr` and plan §5's grammar barely intersect the question, because
   `eq1lab-experiments` never uses `ParameterExpr`.** Zero occurrences. Every derived sweep in the
   authoritative corpus is built by **host-side arithmetic on the compact `{start, stop, num}`
   endpoints** before the `do_nd_inner_loop` call — `ns_to_cycles(burst_duration)` (a `×0.25`
   rescale of a `LinSpace`, in ~12 files), `if_freq_sweep = {start: detune["start"] + qubit_if,
   …}` (a `+offset` on a `Range`), `bias1 = {start: comp["start"]/slope + off, …}` paired with
   `bias0` as a lock-step group (the vector-scan / virtual-gate case). These are exactly the affine
   identities plan §2.2's `affine_form()` recognises — eq1lab is doing `affine_form()` by hand
   today. The only in-program arithmetic on a swept quantity is rank-0 arithmetic on the loop
   variable (`if_freq_qua + detuning_Hz`), which the plan already permits (§10). The
   `VIRTUAL_GATE_MATRIX @ [vSP1, vSP2]` cross-level construct that plan §10 rejects exists **only in
   eq1x-scripts** and has no counterpart in `eq1lab-experiments`.

**Net for the plan: no decision in §9 reopens, and the authoritative corpus is a close structural
match for the design as written.** The one substantive gap is the reverse of a problem: eq1lab bakes
affine transforms into sweep endpoints host-side, where the plan would carry them symbolically in
the IR and fold them with `affine_form()`. Adopting the plan lets eq1lab stop precomputing;
nothing forces it to.

---

## 1. Where do scan ranges live today?

**Caller-supplied. No resolve-by-name.**

In `eq1lab-experiments/experiments/beta2/**` the pattern is uniform. An experiment script:

1. reads **base ranges** as dicts from a per-experiment config store:
   ```python
   burst_duration_sweep = get_experiment_meta_parameter("burst_duration", type=dict)  # {start, stop, num}
   detune_freq_sweep    = get_experiment_meta_parameter("detune_freq", type=dict)      # {start, stop, step}
   comp_voltage         = get_experiment_meta_parameter("comp_level")                  # {start, stop, n_steps}
   ```
2. reads **scalars** it needs for endpoint math from a calibration store:
   ```python
   target_qubit_if = get_if(target_qubit)                       # calibration-derived scalar
   slope           = get_experiment_meta_parameter("slope", type=float)
   ```
3. **derives** any further ranges in Python (finding 6), then
4. passes concrete dicts/arrays positionally to `do_nd_inner_loop`.

`eq1lab_core.sweep_types` (`LinSweep`, `ArraySweep`, `TogetherSweep`, `SweepPlaceholder`,
`normalize_sweep_argument`) is a pure value-carrier layer — every constructor takes concrete
`start` / `stop` / `num` / `array`. There is no registry lookup, no `resolve()`, no
`ExternalDecl`-style "get this range from the device".

**Does the "mostly config" alarm in the task fire?** Partially, and it is worth stating precisely:
the *base* ranges do come from a config store (`experiment_meta_parameter`), and one endpoint is
often a calibration scalar (`detune["start"] + target_qubit_if`). But the resolution happens **in
the experiment script, in Python**, and what reaches the program is a literal dict. From
eq1_pulse's side this is still "the caller supplies the values" (§0, §9 Q17) — the caller is the
script, and it has already done the arithmetic. There is no evidence for a `provenance` field or a
resolve-by-name path; the plan's "always caller-supplied" is correct. What eq1lab would *gain* by
adopting the plan is that steps 2–3 could move into the IR as `ext()` symbols + affine
`SweepExpr` trees, evaluated once at invocation instead of open-coded per script.

The **eq1x-scripts** YAML runner does resolve names differently — its `input:` block names each
axis and `{np.expr: …}` transforms reference sibling axes by name — but that runner is not used by
`eq1lab-experiments` and is out of scope for what eq1lab needs.

---

## 2. What would consume a `SweepDecl`?

**The typed signature of the pulse-action function is the declaration site.** From
`beta2/single_qubit/102a_rabi_chevron.py`:

```python
@apparatus_pulse_action("qua")
def OPX_prog(
    detuning       : InnerLinSweep[Annotated[int, "Hz"]],   # SweepDecl(dtype=int, unit="Hz")
    burst_duration : InnerLinSweep[Annotated[int, "ns"]],   # SweepDecl(dtype=int, unit="ns")
    iteration      : InnerLinSweep[int],                    # SweepDecl(dtype=int)  — the shots axis
    IQ_1           : MeasurementResult[Annotated[complex, "V"]],
    IQ_2           : MeasurementResult[Annotated[complex, "V"]],
):
    with for_each_in_linspace_(declare(int), detuning) as detuning_Hz:
        with for_each_in_linspace_(declare(int), ns_to_cycles(burst_duration)) as burst_duration_cycles:
            with for_each_in_linspace_(declare(int), iteration):
                ...
```

`OPX_prog.inner_input_parameters` reflects those annotations back out (used to build
`init_measurement`). The annotation carries dtype and unit exactly as plan §4.1's `SweepDecl`
does; a `default` has no spelling here (always supplied) but plan §4.1 makes it optional too.

**The seam** where an eq1_pulse `SweepDecl` / `SweepValue` would be read instead of a qcodes tuple
is `eq1lab_core.inner_loop.interface_types`:

| eq1lab interface type | plan model | note |
| --- | --- | --- |
| `InnerLinSweep = TypedDict{start, stop, num}` | `LinSpace` | byte-identical; `np.linspace(**sweep)` works on both |
| *(step form expanded to num before this layer)* | `Range` (`{start, stop, step}`) | `LinSweep.__init__` converts step→num; a `Range` consumer would do the same |
| `InnerLoopArray[T]` (wraps list / ndarray) | `NumpyFloatArray1D` etc. | `.as_numpy()` / `.as_list()` |
| `InnerTogetherSweep[…]` | `SweepGroup` | §3 |

Downstream, on `hp-peti/260824-qblox-branch-lift` (`eq1lab/pulsing/qblox/_loops.py`):

| plan §6 | qblox branch |
| --- | --- |
| `for_("x", sweep("d"))` | `for_each_in_linspace_(x, sweep_dict)` |
| `for_` over a `SweepGroup` | `for_each_in_zip_linspaces_((x, y), [ls_x, ls_y])` |
| index iteration `sweep("d")[var("i")]` | the `idx_var` bound next to `var` by `for_each_in_linspace_` |
| `Indices` — iterate `0..N-1` | `for_each_in_linspace_(i, start=0, stop=N-1, num=N)` |
| host-driven unconsumed sweep | `iterate_linspace_` / `iterate_array_`, or the outer `nd_sweep` Python loop |

The only qblox concept with no plan counterpart is `grouping="buffer" | "average"` (keep every
sweep point vs average into one bin) — a result/acquisition concern, correctly out of plan scope.

`ParameterExpr` is consumed one layer up (`_nd_sweep._convert_expr_config` / `param_nd_sweep`) and
is evaluated **host-side, per iteration, to a number** before anything reaches `do_nd_inner_loop` —
it never crosses this seam as a tree. `eq1lab-experiments` never exercises that path.

---

## 3. Does anything need `TogetherSweep` semantics `SweepGroup` does not cover?

**No.** Three representations of the same concept, all pointing at `SweepGroup`:

- **Declaration:** `bv0__bv1: InnerTogetherSweep[InnerLinSweep[Annotated[float, "V"]],
  InnerLinSweep[Annotated[float, "V"]]]` — a group of two, each with its own dtype+unit. The
  `bv0__bv1` name splits on `__` into member names. This is `SweepGroup` holding `list[SweepSpec]`
  (plan §4.3 / Q10) — and Q10's "members carry their own dtype/unit/limits" is not optional.
- **Invocation:** `do_nd_inner_loop(…, [("bv0", bias0_voltage_sweep), ("bv1",
  bias1_voltage_sweep)], …)` — a level that is a list-of-pairs is a group. Matches
  `ProgramArguments.sweeps` (Q19).
- **Consumption:** `with for_each_in_zip_linspaces_(amps, bv0__bv1):` — a zipped loop over the
  group. Matches "a zipped `for_` must name members of one group" (§7).

Framework-level `TogetherSweep` (`sweep_types.py`) is a flat, equal-length bag of
single-parameter sweeps, each with its own `Parameter`; nested `TogetherSweep`s are flattened.
That is `SweepGroup` exactly — no recursion, equal-length enforced early
(`__init__` raises; plan enforces at build/invocation). `get_dimension_index_for_parameter`
already treats all members as sharing one axis index = "a group contributes one dimension" (§7).

**`SweepPlaceholder` / the QDAC-trigger path** (`eq1lab/pulsing/trigger_dc_list.py`,
`replace_dc_gate_sweeps_with_placeholder_lin_sweep`): the wrapper pulls host-driven DC-gate sweeps
out of the inner-loop input list, substitutes a placeholder that contributes a dimension but no
values, coalesces consecutive placeholders, and forwards the rest. In plan terms a `SweepPlaceholder`
is an **unconsumed** `sweep_decl(name, shape=(N,))` — position from declaration order (§7), host
drives it. Nothing here needs group semantics `SweepGroup` lacks. This whole path is a DC-sweep
concern; the beta2 pulse programs never use it (their outer `nd_sweep` is a 1-point dummy and every
real axis is an inner hardware loop).

---

## 4. How are values supplied to a program today, and is T7 compatible?

D-3 is closed — `ProgramArguments` is a model (T7) with a `parameters` / `sweeps` split, `sweeps` a
list of levels (Q18/Q19). Against the authoritative corpus:

**Shape: a near-exact match.** `do_nd_inner_loop`'s positional inputs are already an ordered list of
levels, outermost first, and a level that is a sub-list is a group
(`beta2/double_qubits/206d_vector_frequency_scan.py`):

```python
do_nd_inner_loop(
    ("if_freq",   if_freq_sweep),                                  # level 0
    ("iteration", {"start": 1, "stop": n_iterations, "step": 1}),  # level 1
    [("bv0", bias0_voltage_sweep), ("bv1", bias1_voltage_sweep)],  # level 2 — a group
    outputs=[*OPX_prog.inner_output_parameters],
    actions=[OPX_prog],
)
```

That is `ProgramArguments.sweeps` with one adjustment of spelling (tuples → mapping). List order is
nesting order, and it lines up with both the signature order and the `for_each_in_*` nesting —
three statements of the same fact, kept consistent by hand.

**The `parameters` / `sweeps` split already exists in practice.** Scalars — `n_iterations`, the LO
frequency, metadata `ManualParameter`s — are *not* passed to `do_nd_inner_loop`. They are set via
`get_experiment_meta_parameter`, `apparatus_set_input_params`, `apparatus_record_const_param_values`.
Only sweeps go into the positional level list. So T7's split matches how beta2 already thinks; an
adapter routes config scalars → `parameters`, the `do_nd_inner_loop` level list → `sweeps`. The
"one ordered block mixing constants, sweeps and derived channels" concern from the previous draft
was an **eq1x-scripts** `input:`-block trait and does not apply here.

**Unit handling matches.** `Annotated[int, "Hz"]` on the declaration, compared (not converted)
against the value's unit, is plan Q15's `{Hz: {start: …}}` wrapper compared as a string.

**One real modelling mismatch: the shots axis.** beta2 models averaging/repetitions as a sweep —
`iteration: InnerLinSweep[int]`, `{"start": 1, "stop": N, "step": 1}`, consumed by a
`for_each_in_linspace_` whose bound value is discarded. In eq1_pulse this is more naturally
`Repetition.count` or `Indices`, not a `SweepDecl`. Not a plan change — just a note that an adapter
should recognise the `iteration` idiom and lower it to a repetition rather than a 1-D sweep axis
that widens the result tensor.

---

## 5. Which of `normalize_sweep_argument`'s nine forms survive `SweepValue`?

`normalize_sweep_argument` accepts nine input forms. Classified against
`SweepValue = LinSpace | Range | NumpyIntArray1D | NumpyFloatArray1D | NumpyComplexArray1D`
(plan §2.1) and cross-checked against what `eq1lab-experiments` actually passes:

| # | Form | Used in authoritative corpus? | After `SweepValue` |
| --- | --- | --- | --- |
| 6 | `(name, {start, stop, num \| step})` | **yes — dominant** | `{start,stop,num}` **is** `LinSpace`; `{…,step}` **is** `Range`; the `(name, …)` pairing is the payload key |
| 8 | `(name, list \| ndarray)` | **yes** (`InnerLoopArray`, RB circuit lists) | array member of `SweepValue` |
| 3 | `[(name, …), (name, …)]` → group | **yes** (vector scan) | `SweepGroup` |
| 1 | framework `TogetherSweep` | no (only `InnerTogetherSweep` annotations) | `SweepGroup` |
| 4 | framework `ParameterSweep` (`LinSweep`/`ArraySweep`) | no | `LinSpace` / array |
| 2 | qcodes `_TogetherSweep` | no | shim — **drop** |
| 5 | qcodes `_LinSweep` | no | shim — **drop** |
| 7 | qcodes `_ArraySweep` | no | shim — **drop** |
| 9 | generic qcodes `_AbstractSweep` (`LogSweep`, `GeometricSweep`, …) | no | materialised to an array via `get_setpoints()` |

**What eq1lab still needs after adopting `SweepValue`:** forms 6, 8, 3 — i.e. `LinSpace`, `Range`,
array, `SweepGroup`. Forms 2/5/7 are pure qcodes-object adapters and collapse to "recognise the
dict/array shape", which `SweepValue` does with no discriminator. Form 9 (`LogSweep` etc.) loses
compact transport — `SweepValue` has only `LinSpace` and `Range` as O(1) forms — but this appears
only in the framework's teaching examples (`08_nd_sweeper/03_qcodes_sweeps.py`), never in
`eq1lab-experiments`. Not a reason to reopen anything.

---

## 6. How far does `ParameterExpr` reach past plan §5's grammar?

### 6.1 `eq1lab-experiments` does not use `ParameterExpr` at all

Zero occurrences of `ParameterExpr`, `{expr:` / `{np.expr:` in `common_exp_lib` or
`experiments/beta2`. `ParameterExpr` (an unrestricted Python `eval` with `numpy`, comprehensions,
`@`, `**`, subscripting) is a feature of the **eq1x-scripts** YAML runner's host-side DC-sweep
path. Assessing its grammar against plan §5 answers a question the authoritative corpus does not
ask. For completeness: across ~110 distinct `{np.expr}` strings in eq1x-scripts, all but three fall
inside plan §5 (bare-name aliases and affine combinations); the exceptions are
`VIRTUAL_GATE_MATRIX @ [vSP1, vSP2]` with `_pgates[0]` / `_pgates[1]` indexing (the case plan §10
names and rejects) and one `np.sqrt(P1**2 + (-P1)**2)` (representable after `x**2 → x*x`).

### 6.2 How the authoritative corpus derives sweeps

**By host-side arithmetic on compact endpoints, before the inner-loop call** — the manual form of
plan §2.2's `affine_form()`. Recurring idioms:

| Idiom | Files | Affine form | Plan equivalent |
| --- | --- | --- | --- |
| `ns_to_cycles(burst_duration)` — rescales `{start,stop}` by `//4`, keeps `num` | ~12 (`101a`, `102a`, `103a–f`, `100b`, `204a`, `207`, `207a`, …) | `LinSpace × 0.25` | `sweep("t") * 0.25`, `affine_form()` → 3 numbers |
| `if_freq_sweep = {start: detune["start"] + qubit_if, stop: …, step: …}` | many (`102a`-derived, `201a`, `202a`, `206a/d`, …) | `Range + offset` | `sweep("detune") + ext("q.if")` |
| `bias0 = {start: c["start"] − Δ, stop: c["stop"] + Δ, num: n}` **paired with** `bias1 = {start: c["start"] + Δ, stop: c["stop"] − Δ, num: n}`, shipped as a group | `100d`, `206a`, `206d` (vector scan) | one base `c`, two affine transforms, one lock-step group | **plan §13 example C / D verbatim** — `sweep_group()` + two `BinaryExpr` trees |
| `bias1 = {start: c["start"]/slope + off, …}` | `206a`, `206d`, `206d_compensation` | `base × (1/slope) + off` | `sweep("c") * (1/slope) + off` |

`ns_to_cycles` on a dict is genuinely host-side — its `LinspaceDict` overload returns a new
`LinspaceDict`, it is not a sequencer op (`eq1lab/pulsing/qua/_common_ops.py`).

### 6.3 In-program arithmetic on a swept quantity

The only arithmetic *inside* the program touching a swept value is rank-0 arithmetic on the **loop
variable**: `x_gate(qubit_index, if_freq=if_freq_qua + detuning_Hz, …)` in `102a`. `detuning_Hz` is
the bound loop variable, `if_freq_qua` a constant QUA int. Plan §10 handles this exactly — "write
it in the body instead, on the loop variables, where it is ordinary rank-0 arithmetic". No sweep
expression tree, no cross-level combination.

### 6.4 The vector-scan / virtual-gate case

`eq1lab-experiments` does vector scans (`206d_vector_frequency_scan`, `206a_fingerprint_Scan`,
`100d`) as **one base range + two affine host-side transforms + a lock-step group**. That is the
pattern plan §13 example C and example D are written for, and plan §2.2 keeps compact. There is no
`@` matrix multiply, no result subscripting, no cross-level (nested) combination anywhere in the
authoritative corpus. The eq1x-scripts `VIRTUAL_GATE_MATRIX @ [vSP1, vSP2]` form — which *would*
hit plan §10's rejection — is a different subsystem and not evidence of an eq1lab need.

**If** a future experiment needed a full N×N virtual-gate matrix over genuinely independent
(nested) axes feeding a pulse parameter, plan §10's rejection would bite and the escape hatch
("flatten to one `SweepGroup`, or compute in the loop body") would apply. No current experiment
does this — the vector scans are all rank-1 lock-step.

---

## What this means for the sweeps plan

**No decision in plan §9 reopens.** Point by point:

| Decision | Evidence from `eq1lab-experiments` | Verdict |
| --- | --- | --- |
| **Q17** — values always caller-supplied, no resolve-by-name | scripts read `{start,stop,num}` dicts from config and do endpoint math in Python; nothing resolves a range by name | **confirmed** |
| **Q10** — `SweepGroup` holds full `SweepSpec`s, per-member dtype/unit/limits | `InnerTogetherSweep[InnerLinSweep[Annotated[float,"V"]], …]` — members carry their own dtype+unit | **confirmed** |
| **Q18 / Q19** — payload is a model; `sweeps` a nested list of levels, a group is a sub-list | `do_nd_inner_loop(("a", d0), ("b", d1), [("c0", d2a), ("c1", d2b)], …)` is this exactly | **confirmed** |
| **Q2 / Q2a** (2026-08-26 revision) — general elementwise arithmetic over lock-step sweeps | every derived sweep is affine over a base or a group; the revision's affine subset covers 100% of the corpus, and `affine_form()` would give the compact transport eq1lab hand-codes | **confirmed the revision was right** |
| **Q15** — unit compared as a string, never converted | `Annotated[int, "Hz"]` on the declaration, validator-compared | **confirmed** |
| **§10** — no cross-level sweep combination; matrix virtual gates go in a group or the body | the corpus does vector scans as base + affine transforms + lock-step group (§13 C/D); the cross-level `@` form is eq1x-scripts only | **not reopened** |

**Observations for adoption (ergonomic, not structural):**

1. **eq1lab computes affine transforms host-side into endpoints** (`ns_to_cycles`,
   `+ qubit_if`, `/ slope`). The plan carries them symbolically and folds them with
   `affine_form()`. Adopting the plan lets the experiment script stop precomputing and get compact
   transport for free — the payoff is a single validated artifact (program + arguments) and no
   open-coded endpoint math; the cost is that the "just mutate the dict" simplicity goes away.
2. **Position is stated three times today** — signature order, `do_nd_inner_loop` argument order,
   `for_each_in_*` nesting — and kept consistent by hand. Plan §7 gives position exactly one source
   (the consuming `for_`, else declaration order). That is a simplification eq1lab would inherit.
3. **The `iteration` shots axis** is modelled as a 1-D sweep. An eq1_pulse adapter should lower it
   to `Repetition` / `Indices`, not a `SweepDecl`, so it does not widen the result tensor.
4. **`ParameterExpr` / the eq1x-scripts `input:` block** is a separate host-side DC-sweep runner.
   Nothing in it needs to influence the plan; if that runner is ever unified with the pulse-program
   path, its `{np.expr}` transforms are mostly affine and fit §5, with the virtual-gate matrix as
   the one construct needing §10's flatten-or-body treatment.
5. **`LogSweep` / analytic `_AbstractSweep`s lose compact transport** under `SweepValue`
   (`LinSpace` + `Range` only). Not used in `eq1lab-experiments`; a framework-example concern.

The qblox pulsing branch (`hp-peti/260824-qblox-branch-lift`) is, if anything, *more* aligned with
the plan than the qcodes-era code: `for_each_in_linspace_` / `for_each_in_zip_linspaces_` / `idx_var`
in `pulsing/qblox/_loops.py` is close to a direct implementation of plan §6, and `InnerLinSweep` is
`LinSpace` under another name.
