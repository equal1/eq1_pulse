"""Tests for :func:`~eq1_pulse.utilities.check_arguments.check_arguments` (parameter sweeps, task T8).

The checker is advisory and nothing calls it, so these tests are the whole specification of what it
finds. Programs are built through the builder; payloads are ``ProgramArguments`` validated from the
plain mappings a caller would write. Every check in plan §16 appears here in both directions -- a
payload that fits (no findings) and one that does not (a finding naming the declaration, and for a
nesting drift both what the payload asserted and what the program says).
"""

from eq1_pulse.builder import (
    build_sequence,
    ext,
    extern_decl,
    for_,
    if_,
    param_decl,
    play,
    repeat,
    step_pulse,
    sub_sequence,
    sweep,
    sweep_decl,
    sweep_group,
    var,
    var_decl,
)
from eq1_pulse.models import ValueLimits
from eq1_pulse.models.arguments import ProgramArguments
from eq1_pulse.models.sequence import OpSequence
from eq1_pulse.utilities.check_arguments import Finding, check_arguments


def _args(payload: object) -> ProgramArguments:
    """Validate *payload* into a :class:`ProgramArguments`, as a caller's mapping would be.

    :param payload: The raw invocation mapping
    :return: The validated payload
    """
    return ProgramArguments.model_validate(payload)


def _categories(findings: list[Finding]) -> list[str]:
    """Return the category of each finding, in order.

    :param findings: The findings to summarise
    :return: Their categories
    """
    return [finding.category for finding in findings]


# ---------------------------------------------------------------------------
# The happy path: plan §16's own example
# ---------------------------------------------------------------------------


_SECTION_16_PAYLOAD = {
    "parameters": {"n_shots": 1000},
    "sweeps": [
        {"detuning": {"mV": {"start": -20, "stop": 20, "num": 81}}},
        {
            "i_amp": {"mV": {"start": -1, "stop": 1, "num": 20}},
            "drive_freq": {"MHz": {"start": 4900, "stop": 5100, "num": 20}},
        },
        {"vg": {"start": -400, "stop": 400, "num": 20001}},
    ],
}


def _section_16_program() -> OpSequence:
    """Build a program whose structure is exactly §16's payload: ``[{detuning}, {i_amp, drive_freq}, {vg}]``.

    :return: The built sequence
    """
    with build_sequence() as seq:
        param_decl("n_shots", "int")
        sweep_decl("detuning", "float", unit="mV")
        with sweep_group():
            sweep_decl("i_amp", "float", unit="mV")
            sweep_decl("drive_freq", "float", unit="MHz")
        sweep_decl("vg", "float", unit="mV")
        var_decl("v", "float", unit="mV")
    return seq


def test_section_16_payload_against_matching_program_has_no_findings():
    """The example payload against a program with that exact structure: nothing is wrong."""
    assert check_arguments(_section_16_program(), _args(_SECTION_16_PAYLOAD)) == []


# ---------------------------------------------------------------------------
# Check 2 -- unit agreement
# ---------------------------------------------------------------------------


def test_volts_supplied_for_a_millivolt_declaration_is_a_finding():
    """The headline case: ``unit: V`` for a ``unit: mV`` sweep, compared as strings."""
    with build_sequence() as seq:
        sweep_decl("d", "float", unit="mV")

    findings = check_arguments(seq, _args({"sweeps": [{"d": {"V": {"start": 0, "stop": 1, "num": 5}}}]}))

    assert _categories(findings) == ["unit"]
    assert "mV" in findings[0].message and "'V'" in findings[0].message


def test_a_unit_stated_for_a_unitless_declaration_is_a_finding():
    """A sweep declared with no unit, supplied with one, disagrees just as V-for-mV does."""
    with build_sequence() as seq:
        sweep_decl("d", "float")

    findings = check_arguments(seq, _args({"sweeps": [{"d": {"mV": {"start": 0, "stop": 1, "num": 5}}}]}))

    assert _categories(findings) == ["unit"]
    assert "without a unit" in findings[0].message


def test_matching_unit_produces_no_finding():
    """A stated unit that equals the declared one is fine."""
    with build_sequence() as seq:
        sweep_decl("d", "float", unit="mV")

    assert check_arguments(seq, _args({"sweeps": [{"d": {"mV": {"start": 0, "stop": 1, "num": 5}}}]})) == []


def test_omitted_unit_produces_no_finding():
    """A value with no unit key is taken to be in the declared unit."""
    with build_sequence() as seq:
        sweep_decl("d", "float", unit="mV")

    assert check_arguments(seq, _args({"sweeps": [{"d": {"start": 0, "stop": 1, "num": 5}}]})) == []


# ---------------------------------------------------------------------------
# Check 1 -- name coverage
# ---------------------------------------------------------------------------


def test_a_missing_required_sweep_is_a_finding():
    """A group member declared without a default and left out of the payload is reported."""
    with build_sequence() as seq:
        with sweep_group():
            sweep_decl("a", "float", unit="mV")
            sweep_decl("b", "float", unit="mV")

    findings = check_arguments(seq, _args({"sweeps": [{"a": {"start": 0, "stop": 1, "num": 5}}]}))

    assert any(f.category == "name-coverage" and "'b'" in f.message for f in findings)


def test_an_unknown_sweep_name_is_a_finding():
    """A payload naming a sweep the program does not declare is reported."""
    with build_sequence() as seq:
        sweep_decl("a", "float", unit="mV")

    findings = check_arguments(
        seq,
        _args(
            {
                "sweeps": [
                    {"a": {"start": 0, "stop": 1, "num": 5}},
                    {"ghost": {"start": 0, "stop": 1, "num": 5}},
                ]
            }
        ),
    )

    assert any(f.category == "name-coverage" and "'ghost'" in f.message for f in findings)


def test_an_unknown_parameter_name_is_a_finding():
    """Same for a parameter the program does not declare."""
    with build_sequence() as seq:
        param_decl("real", "int", default=1)

    findings = check_arguments(seq, _args({"parameters": {"bogus": 5}}))

    assert any(f.category == "name-coverage" and "'bogus'" in f.message for f in findings)


# ---------------------------------------------------------------------------
# Check 3 -- nesting agreement: one drift case per shape
# ---------------------------------------------------------------------------


def test_drift_two_levels_swapped():
    """Two solo sweeps supplied in the wrong order: each level names both sides."""
    with build_sequence() as seq:
        sweep_decl("a", "float", unit="mV")
        sweep_decl("b", "float", unit="mV")

    findings = check_arguments(
        seq,
        _args(
            {
                "sweeps": [
                    {"b": {"start": 0, "stop": 1, "num": 5}},
                    {"a": {"start": 0, "stop": 1, "num": 5}},
                ]
            }
        ),
    )

    nesting = [f for f in findings if f.category == "nesting"]
    assert len(nesting) == 2
    assert all("assert" in f.message and "program says" in f.message for f in nesting)


def test_drift_sweep_moved_into_a_group():
    """Two solo sweeps asserted as one group level: level count disagrees, both structures named."""
    with build_sequence() as seq:
        sweep_decl("a", "float", unit="mV")
        sweep_decl("b", "float", unit="mV")

    findings = check_arguments(
        seq,
        _args({"sweeps": [{"a": {"start": 0, "stop": 1, "num": 5}, "b": {"start": 0, "stop": 1, "num": 5}}]}),
    )

    assert _categories(findings) == ["nesting"]
    assert "[{a}, {b}]" in findings[0].message and "[{a, b}]" in findings[0].message


def test_drift_group_split_across_two_levels():
    """A declared group asserted as two separate levels."""
    with build_sequence() as seq:
        with sweep_group():
            sweep_decl("a", "float", unit="mV")
            sweep_decl("b", "float", unit="mV")

    findings = check_arguments(
        seq,
        _args(
            {
                "sweeps": [
                    {"a": {"start": 0, "stop": 1, "num": 5}},
                    {"b": {"start": 0, "stop": 1, "num": 5}},
                ]
            }
        ),
    )

    assert _categories(findings) == ["nesting"]
    assert "[{a, b}]" in findings[0].message and "[{a}, {b}]" in findings[0].message


def test_drift_one_level_too_many():
    """An extra asserted level: the count mismatch names both structures."""
    with build_sequence() as seq:
        sweep_decl("a", "float", unit="mV", default=[0.0, 1.0, 2.0])

    findings = check_arguments(
        seq,
        _args(
            {
                "sweeps": [
                    {"a": {"start": 0, "stop": 1, "num": 5}},
                    {"a_extra": {"start": 0, "stop": 1, "num": 5}},
                ]
            }
        ),
    )

    nesting = [f for f in findings if f.category == "nesting"]
    assert len(nesting) == 1
    assert "1 sweep level" in nesting[0].message and "supply 2" in nesting[0].message


# ---------------------------------------------------------------------------
# A transform-driven loop consumes its bases
# ---------------------------------------------------------------------------


def test_transform_driven_loop_consumes_its_base_sweep():
    """Plan §13 example C: a loop over transforms of one sweep, checked against a one-level payload."""
    with build_sequence() as seq:
        sweep_decl("detuning", "float", unit="mV")
        extern_decl("vg.m11", "float")
        extern_decl("vg.o1", "float", unit="mV")
        extern_decl("vg.m21", "float")
        extern_decl("vg.o2", "float", unit="mV")
        var_decl("p1", "float", unit="mV")
        var_decl("p2", "float", unit="mV")
        with for_(
            ["p1", "p2"],
            [
                sweep("detuning") * ext("vg.m11") + ext("vg.o1"),
                sweep("detuning") * ext("vg.m21") + ext("vg.o2"),
            ],
        ):
            play("gate_1", step_pulse(duration="100ns", amplitude=var("p1")))
            play("gate_2", step_pulse(duration="100ns", amplitude=var("p2")))

    findings = check_arguments(seq, _args({"sweeps": [{"detuning": {"mV": {"start": -20, "stop": 20, "num": 81}}}]}))

    assert findings == []


# ---------------------------------------------------------------------------
# Check 4 -- group agreement
# ---------------------------------------------------------------------------


def test_group_with_unequal_supplied_lengths_is_a_finding():
    """A level with two entries of different lengths cannot advance on one index."""
    with build_sequence() as seq:
        with sweep_group():
            sweep_decl("a", "float", unit="mV")
            sweep_decl("b", "float", unit="mV")

    findings = check_arguments(
        seq,
        _args(
            {
                "sweeps": [
                    {
                        "a": {"start": 0, "stop": 1, "num": 5},
                        "b": {"start": 0, "stop": 1, "num": 8},
                    }
                ]
            }
        ),
    )

    assert _categories(findings) == ["group"]
    assert "a=5" in findings[0].message and "b=8" in findings[0].message


# ---------------------------------------------------------------------------
# Check 5 -- shape and limits
# ---------------------------------------------------------------------------


def test_shape_mismatch_is_a_finding():
    """``shape=(10,)`` pins ten items; a value with four is reported."""
    with build_sequence() as seq:
        sweep_decl("d", "float", unit="mV", shape=(10,))

    findings = check_arguments(seq, _args({"sweeps": [{"d": {"start": 0, "stop": 1, "num": 4}}]}))

    assert _categories(findings) == ["shape"]
    assert "10" in findings[0].message and "4" in findings[0].message


def test_a_value_outside_declared_limits_is_a_finding():
    """An endpoint above the declared maximum is reported; units are not converted."""
    with build_sequence() as seq:
        sweep_decl("d", "float", unit="mV", limits=ValueLimits(minimum=0, maximum=100))

    findings = check_arguments(seq, _args({"sweeps": [{"d": {"start": 0, "stop": 200, "num": 5}}]}))

    assert _categories(findings) == ["limits"]
    assert "maximum" in findings[0].message


# ---------------------------------------------------------------------------
# Everything at once
# ---------------------------------------------------------------------------


def test_three_distinct_problems_are_three_findings_in_one_call():
    """A required parameter left out, a wrong unit, and a shape mismatch -- all reported together."""
    with build_sequence() as seq:
        param_decl("p", "int")
        sweep_decl("d", "float", unit="mV", shape=(5,))

    findings = check_arguments(
        seq,
        _args({"sweeps": [{"d": {"V": {"start": 0, "stop": 1, "num": 8}}}]}),
    )

    assert sorted(_categories(findings)) == ["name-coverage", "shape", "unit"]


# ---------------------------------------------------------------------------
# Walking the program: nested scopes and body-bearing operations
# ---------------------------------------------------------------------------


def test_declarations_are_found_through_nested_scopes_and_bodies():
    """A loop consuming a sweep is found inside ``repeat`` and ``if_`` bodies, past a ``sub_sequence``."""
    with build_sequence() as seq:
        var_decl("flag", "bool")
        sweep_decl("d", "float", unit="mV")
        var_decl("x", "float", unit="mV")
        with sub_sequence():
            play("aux", step_pulse(duration="40ns", amplitude="10mV"))
        with repeat(3):
            with if_(var("flag")):
                with for_("x", sweep("d")):
                    play("gate", step_pulse(duration="40ns", amplitude=var("x")))

    # `d` is consumed by the loop, so it is the sole level -- a one-level payload fits.
    assert check_arguments(seq, _args({"sweeps": [{"d": {"mV": {"start": 0, "stop": 1, "num": 5}}}]})) == []
    # and a mismatched nesting is still caught from inside those bodies.
    findings = check_arguments(seq, _args({"sweeps": []}))
    assert any(f.category == "nesting" for f in findings)


def test_array_valued_argument_is_measured_for_group_and_shape():
    """A bare list argument has a length and endpoints like a compact form does."""
    with build_sequence() as seq:
        with sweep_group():
            sweep_decl("a", "float", unit="mV")
            sweep_decl("b", "float", unit="mV")

    findings = check_arguments(seq, _args({"sweeps": [{"a": [0.0, 1.0, 2.0], "b": [0.0, 1.0]}]}))

    assert _categories(findings) == ["group"]
    assert "a=3" in findings[0].message and "b=2" in findings[0].message


def test_limit_bound_stated_as_a_wrapped_quantity_in_a_matching_unit():
    """A ``minimum`` written ``{"mV": 0}`` is compared to an mV-declared sweep without conversion."""
    with build_sequence() as seq:
        sweep_decl("d", "float", unit="mV", limits=ValueLimits(minimum={"mV": 0}))

    findings = check_arguments(seq, _args({"sweeps": [{"d": [-5.0, 0.0, 5.0]}]}))

    assert _categories(findings) == ["limits"]
    assert "minimum" in findings[0].message


def test_limit_bound_in_a_different_unit_is_skipped_not_converted():
    """A bound stated in V against an mV value is not comparable, and is not guessed at."""
    with build_sequence() as seq:
        sweep_decl("d", "float", unit="mV", limits=ValueLimits(minimum={"V": 0}))

    assert check_arguments(seq, _args({"sweeps": [{"d": [-5.0, 0.0, 5.0]}]})) == []


def test_finding_str_is_category_tagged():
    """``str(Finding)`` renders ``[category] message`` for a log line."""
    assert str(Finding("unit", "d was mV")) == "[unit] d was mV"
