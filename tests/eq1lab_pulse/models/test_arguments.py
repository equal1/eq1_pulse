"""Tests for the invocation payload (parameter sweeps plan, task T7).

The wire form asserted here is plan §16's ``ProgramArguments`` block, transcribed:

.. code-block:: yaml

    parameters:
      n_shots: 1000

    sweeps:
      - detuning:   {mV:  {start: -20,  stop: 20,   num: 81}}     # level 0 -- one sweep
      - i_amp:      {mV:  {start: -1,   stop: 1,    num: 20}}     # level 1 -- a group,
        drive_freq: {MHz: {start: 4900, stop: 5100, num: 20}}     #            two entries
      - vg: {start: -400, stop: 400, num: 20001}                  # level 2 -- unit omitted

``sweeps`` is a list of levels, outermost first; a level with several entries is a group, and it
stays one list item with two keys rather than being flattened.
"""

import numpy as np
import pytest
from pydantic import ConfigDict, TypeAdapter, ValidationError

from eq1_pulse.models.arguments import ProgramArguments, QualifiedSweepValue, SweepArgument
from eq1_pulse.models.basic_types import ComplexVoltage

_SWEEP_ARGUMENT_ADAPTER: TypeAdapter[SweepArgument] = TypeAdapter(
    SweepArgument, config=ConfigDict(arbitrary_types_allowed=True)
)


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


def test_section_16_payload_round_trips_literally():
    """§16's block survives ``model_validate`` -> ``model_dump`` unchanged, group level and all."""
    arguments = ProgramArguments.model_validate(_SECTION_16_PAYLOAD)
    assert arguments.model_dump() == _SECTION_16_PAYLOAD


def test_section_16_payload_round_trips_through_json():
    """And through JSON, not just the Python mapping."""
    arguments = ProgramArguments.model_validate(_SECTION_16_PAYLOAD)
    from_json = ProgramArguments.model_validate_json(arguments.model_dump_json())
    assert from_json.model_dump() == _SECTION_16_PAYLOAD


def test_group_level_stays_one_item_with_two_keys():
    """The two-entry level is one list item carrying both sweeps, not two items."""
    arguments = ProgramArguments.model_validate(_SECTION_16_PAYLOAD)
    assert len(arguments.sweeps) == 3
    assert set(arguments.sweeps[1]) == {"i_amp", "drive_freq"}


def test_qualified_sweep_value_validates():
    """A unit-keyed compact form is a ``QualifiedSweepValue``."""
    value = QualifiedSweepValue.model_validate({"mV": {"start": 0, "stop": 1, "num": 5}})
    assert set(value.root) == {"mV"}


def test_qualified_sweep_value_rejects_two_keys():
    """Exactly one key -- a two-key mapping is not a single qualified value."""
    with pytest.raises(ValidationError):
        QualifiedSweepValue.model_validate(
            {"mV": {"start": 0, "stop": 1, "num": 5}, "V": {"start": 0, "stop": 1, "num": 5}}
        )


def test_qualified_sweep_value_rejects_unknown_unit():
    """The sole key must name a known unit."""
    with pytest.raises(ValidationError):
        QualifiedSweepValue.model_validate({"parsec": {"start": 0, "stop": 1, "num": 5}})


def test_qualified_sweep_value_rejects_a_scalar():
    """The value under the unit key is a list-valued ``SweepValue``, not a scalar quantity."""
    with pytest.raises(ValidationError):
        QualifiedSweepValue.model_validate({"mV": 100})


def test_mV_pair_is_a_complex_voltage_as_a_parameter():
    """``{"mV": [1, 2]}`` under ``parameters`` is a scalar ``ComplexVoltage`` (plan §16)."""
    arguments = ProgramArguments.model_validate({"parameters": {"bias": {"mV": [1, 2]}}})
    assert isinstance(arguments.parameters["bias"], ComplexVoltage)


def test_mV_pair_is_an_array_sweep_as_a_sweep():
    """The same ``{"mV": [1, 2]}`` under a sweep level is a two-item array, unit-qualified."""
    arguments = ProgramArguments.model_validate({"sweeps": [{"bias": {"mV": [1, 2]}}]})
    supplied = arguments.sweeps[0]["bias"]
    assert isinstance(supplied, QualifiedSweepValue)
    assert list(np.asarray(supplied.root["mV"])) == [1, 2]


def test_bare_sweep_value_without_a_unit_is_accepted_in_a_level():
    """A level entry may be a bare ``SweepValue`` -- taken to be in the declared unit."""
    adapted = _SWEEP_ARGUMENT_ADAPTER.validate_python({"start": -400, "stop": 400, "num": 20001})
    assert not isinstance(adapted, QualifiedSweepValue)

    arguments = ProgramArguments.model_validate({"sweeps": [{"vg": {"start": 0, "stop": 1, "num": 5}}]})
    assert not isinstance(arguments.sweeps[0]["vg"], QualifiedSweepValue)


def test_empty_level_raises():
    """Every level names at least one sweep."""
    with pytest.raises(ValidationError):
        ProgramArguments.model_validate({"sweeps": [{}]})


def test_name_repeated_across_levels_raises():
    """A sweep is supplied once; the same name in two levels is a contradiction about nesting."""
    with pytest.raises(ValidationError):
        ProgramArguments.model_validate(
            {
                "sweeps": [
                    {"d": {"start": 0, "stop": 1, "num": 5}},
                    {"d": {"start": 0, "stop": 1, "num": 5}},
                ]
            }
        )


def test_empty_program_arguments_validates():
    """No parameters and no sweeps is a valid -- if unusual -- invocation."""
    assert ProgramArguments().model_dump() == {}
    assert ProgramArguments.model_validate({}).model_dump() == {}


def test_supplied_sweep_where_a_parameter_belongs_is_a_validation_error():
    """``{"mV": [1, 2]}`` is a valid parameter, but a bare list is not (plan §16, the split)."""
    with pytest.raises(ValidationError):
        ProgramArguments.model_validate({"parameters": {"bias": [1, 2, 3]}})
