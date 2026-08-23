# Execution breakdown: nested operation wire format

Companion to [op-wire-format-plan.md](op-wire-format-plan.md). Five tasks, each sized for a single
clean session.

**Run them in numeric order.** Each assumes every lower-numbered task is complete and committed.
Each leaves the tree green — which is why a model change and its test/doc fallout live in the same
task rather than being split.

---

## Common preamble — paste into every session

> **Environment.** `conda activate eq1_pulse-dev` before running anything. If the prompt does not
> show `(eq1_pulse-dev)`, activation did not happen.
>
> **Conventions.** Follow `.github/copilot-instructions.md`. Load-bearing points: ReST docstrings
> (`:param:` / `:return:` / `:raises:`, no `:type:` where the annotation says it); blank lines must
> be **completely** empty; no trailing whitespace anywhere; max 2 consecutive blank lines at top
> level, 1 inside a function; 120-column lines; `X | Y` inside `isinstance()`, never a tuple;
> aligned pipes in markdown tables. Models inherit from the bases in `models/base_models.py`.
>
> **The wire form is the contract.** Every change here is observable in `model_dump_json()`. When
> you change a shape, change the docstring that describes it in the same edit — several modules
> (`reference_types`, `expressions`, `pulse_types`) spell wire forms out in prose, and a stale
> example there is worse than none.
>
> **Symmetry is non-negotiable.** `tests/eq1lab_pulse/models/test_schema_symmetry.py` asserts
> validation-mode and serialization-mode schemas are equal for every model, that none is empty, and
> that a canonical document round-trips. Any schema hook you write must satisfy all three. If you
> widen what Python accepts, do it through `json_or_python_schema` so the widening never reaches the
> JSON schema.
>
> **Verify.** `./qa/run_all_qa.sh` (pyright + mypy + pytest with coverage). It must pass before you
> report done. If it passed before your change and fails after, you are not done.
>
> **Context.** Read `docs/plans/op-wire-format-plan.md` — the sections named in your task.
>
> **Do not `git checkout`** with uncommitted work in flight; use `git stash` and handle untracked
> files deliberately.

---

## Task 1 — `NestedWireModel` machinery — **DONE** (`9cd1a68`, `51dd72b`)

**Plan sections:** §3.1, §3.2
**Files:** `src/eq1_pulse/models/base_models.py`, `tests/eq1lab_pulse/models/test_base_models.py` (new)

Add `NestedWireModel(LeanModel)` with `_wire_tag_source_` / `_wire_payload_key_` class vars and the
three hooks in the §3.1 table: wrap serializer, wrap validator, JSON-schema hook.

Nothing opts in during this task. `LeanModel`'s own behaviour must be byte-identical afterwards —
that is the check that the machinery is additive.

Cover in tests, against throwaway models defined in the test file, not real ones:

- tag read from the field's **value** (`_wire_payload_key_ = None`) and from the field's **name**
  (`_wire_payload_key_ = "op"`), per §3.2
- round-trip: `validate(dump(x)) == x` and `dump(validate(d)) == d`
- the D3 empty-payload case: a model whose non-tag fields all have defaults dumps to the bare tag
  string and validates back from it; a model with a required field does **not** grow that form
- both schema modes agree; `title`/`description` sit on the outer schema (per plan §4's worked
  example) and `additionalProperties: false` on both levels
- an extra key alongside the tag is rejected; a two-key object is rejected

**Done when** QA is green and the new tests fail if the wrap is removed.

---

## Task 2 — Operations nest — **DONE** (`2abee58`)

**Plan sections:** §0, §3.1, §3.3, §5
**Files:** `models/basic_types.py` (`OpBase`), `models/channel_ops.py`, `models/data_ops.py`,
`models/sequence.py`, `models/experimental/schedule.py`, plus the tests listed below

1. `OpBase` inherits `NestedWireModel` and sets `_wire_tag_source_ = "op_type"`. No per-op edit —
   all 20 operations inherit it. Keep the `op_type` field (D6).
2. Rewrite the four union discriminators (§3.3 table) from `Discriminator("op_type")` to a callable
   that returns the sole key of a mapping, the `op_type` value of a model instance, and `None`
   otherwise. Write the callable **once** and import it; do not copy it four times.
3. Confirm `OpSequenceItem = DiscriminableOp | OpSequence` still resolves: an operation is a
   single-key object, a nested sequence is an array, so the callable returns `None` for the array
   and the plain union falls through to `OpSequence`. Add a test that a nested sequence inside a
   body still validates.
4. Update the docstrings that quote the flat form — `sequence.py` module docstring,
   `channel_ops.py`'s `ChannelOp` alias, `data_ops.py`'s `DataOp` alias, and the `:ivar op_type:`
   lines in `control_flow.py` / `sequence.py`.
5. Update the asserting tests: `models/test_sequence.py`, `models/test_data_ops.py`,
   `models/test_channel_ops.py`, `models/test_external_block.py`,
   `models/test_valueref_rebuild_sweep.py`, `experimental/test_schedule.py`,
   `test_range_conversion.py`, `test_builder_zipped_iteration.py`, `test_openapi_generator.py`.

**Watch for:** `test_openapi_generator.py` asserts on the generated document and will need its
expectations moved to the nested shape. `ScheduledOperation.op: Schedulable` now holds a single-key
object — check `experimental/test_schedule.py` covers that.

**Done when** QA is green and `test_schema_symmetry.py` passes unmodified.

---

## Task 3 — Expression operator nodes nest — **DONE** (`665537f`, `4957350`)

**Plan sections:** §3.2, §3.4
**Files:** `models/expressions.py`, `models/pulse_types.py`, `tests/eq1lab_pulse/models/test_expressions.py`,
`tests/eq1lab_pulse/test_builder_expressions.py`

1. The six nodes in the §3.4 table opt into `NestedWireModel`, copying all three ClassVars from
   that row verbatim. Every one of them sets `_wire_tag_from_ = "name"` — expression nodes are
   tagged by field name, never by operator value, because `"-"` is both unary and binary. Do not
   change `NestedWireModel` itself; §3.4's four combinations are all reachable as it stands.
2. `LiteralExpr` and `SymbolExpr` do **not** opt in. Their wire form is unchanged.
3. Tighten `expression_tag_of` from "the first known key present" to "the sole key, if known".
   Keep it returning `None` for anything else — `_external_param_value_tag` in `pulse_types.py`
   depends on that to fall through to the unit and reference branches. Unlike the four operation
   unions, `Expression` stays a **bare** `Discriminator(expression_tag_of)`: its members are all
   concrete node classes, so it needs none of `OperationDiscriminator`'s per-member `Tag` walking.
   See plan §3.3.
4. Update the `expressions.py` module docstring: it currently argues the design in terms of the
   flat keys (`compare_op` / `not_op` / `logical_op` versus `unary_op` / `binary_op`). The argument
   survives verbatim — the tag is still the field name (§3.2) — but the examples must show the
   nested payload.
5. Leave `MAX_EXPRESSION_DEPTH` at 32; add the §3.4 note about JSON depth to its docstring.

**Watch for:** the builder (`builder/_expressions.py`) constructs nodes by keyword (`binary_op="+"`)
and is unaffected by D6's reasoning — the Python field names do not change. If you find yourself
editing the builder, stop and re-read §3.4.

**Done when** QA is green and `examples/expression_ramsey.py` runs and produces the nested form.

---

## Task 4 — Bare variable references

**Plan sections:** §3.5
**Files:** `models/reference_types.py`, `models/channel_ops.py`, `models/control_flow.py`,
`models/data_ops.py`, `models/external_block.py`, `tests/eq1lab_pulse/models/test_reference_types.py`

1. Add `VarName` and its `_BareVariableRef` annotation to `reference_types.py`, per §3.5. The JSON
   side accepts an `IdentifierStr` only; the Python side additionally accepts a `VariableRef`
   instance and a `VarRefDict`. Serializer emits `.var`. Schema hook reports `{"type": "string"}`
   in both modes.
2. Apply it at the seven sites in the §3.5 table. `IterationBase.var` becomes
   `list[VarName] | VarName`.
3. `VariableRef` itself is untouched — `SymbolRef`, `ValueRef`, `ExternalParamValue` and
   `SymbolExpr.symbol` all keep `{"var": ...}`. Add a test asserting exactly that split, because it
   is the part a later reader will assume is an oversight.
4. Check for flat-form document literals beyond the files named above — Task 3 found
   `tests/eq1lab_pulse/models/test_valueref_rebuild_sweep.py` embedded some that its own file list
   had missed. `grep -rn '"var":' tests/` before you declare done.
5. Update the `reference_types.py` module docstring. It currently says `ChannelRef` is *the* bare
   reference, carved out on #10. That is no longer the whole story: `VariableRef` is bare in
   var-typed fields and tagged in union positions, and the docstring must say why (a union position
   has to tell it from `ExternalRef` and from `ExternalParamValue`'s plain `str`).

**Watch for:** `ExternalBlock._validate_flex_duration_params` iterates `params`, not `results` — it
needs no change, but confirm it, because `results` is one of the seven sites.

**Done when** QA is green and `{"discriminate": {"target": "outcome", "source": "iq", ...}}` is what
`Discriminate(...).model_dump()` produces.

---

## Task 5 — Regenerate artefacts and sweep the docs

**Plan sections:** §4, §5, §6
**Files:** `output/eq1_pulse_openapi.{json,yaml}`, `docs/source/user_guide/builder_guide.rst`,
`docs/source/examples/basic_usage.rst`, `docs/source/examples/index.rst`, `examples/*.py`

1. `python -m eq1_pulse.utilities.openapi_generator` and move both outputs into `output/`.
   **The diff will be large and that is expected** — the checked-in copy is stale independently of
   this work (§4): it predates expressions entirely and still shows `SymbolRef` where `ValueRef` is
   current. Do not hand-trim it.
2. Confirm §6.1: operation unions now carry a plain `oneOf` with no `discriminator` keyword, while
   `PulseType` and the integration union keep theirs. Record that in the plan's §6 if it turns out
   differently.
3. **`examples/*.py` need no source edits** — every one builds through the builder API, and no
   example file contains a flat-form literal (verified by grep). But nine of them *print* wire
   output via `model_dump`/`model_dump_json`: `builder_example`, `calibrated_rabi`,
   `discriminate_example`, `expression_ramsey`, `measure_if_example`, `pulse_shapes_example`,
   `spin_qubit_rabi`, `spin_qubit_t2star`, `zipped_iteration_example`. Run each and eyeball that
   the printed form is nested.
4. Regenerate the wire dumps quoted in the three `.rst` files **from that actual output** — do not
   hand-edit the old text. They hold 27 `op_type` occurrences between them:
   `examples/basic_usage.rst` (14), `user_guide/builder_guide.rst` (10), `examples/index.rst` (3).
5. Add a short "wire format" section to `builder_guide.rst` stating both conventions (§6.2) —
   nested for operations, flat for pulses and integrations — so the asymmetry is documented rather
   than discovered.

**Done when** QA is green, `cd docs && ./generate_html.sh` builds clean, and every example runs.
