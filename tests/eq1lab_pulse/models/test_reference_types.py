from eq1_pulse.models.reference_types import ChannelRef, PulseRef, VariableRef


def test_channel_ref():
    ref = ChannelRef("ch1")
    assert ref.channel == "ch1"


def test_channel_ref_serialization():
    ref = ChannelRef("ch1")
    assert ref.model_dump() == "ch1"  # type: ignore


def test_channel_ref_validation():
    ref = ChannelRef.model_validate("ch1")
    assert ref.channel == "ch1"


def test_channel_ref_json_validation():
    ref = ChannelRef.model_validate_json('"ch1"')
    assert ref.channel == "ch1"


def test_channel_ref_json_serialization():
    ref = ChannelRef("ch1")
    assert ref.model_dump_json() == '"ch1"'


def test_pulse_ref():
    ref = PulseRef("pulse1")
    assert ref.pulse_name == "pulse1"


def test_pulse_ref_serialization():
    ref = PulseRef("pulse1")
    assert ref.model_dump() == "pulse1"  # type: ignore


def test_pulse_ref_validation():
    ref = PulseRef.model_validate("pulse1")
    assert ref.pulse_name == "pulse1"


def test_pulse_ref_json_validation():
    ref = PulseRef.model_validate_json('"pulse1"')
    assert ref.pulse_name == "pulse1"


def test_pulse_ref_json_serialization():
    ref = PulseRef("pulse1")
    assert ref.model_dump_json() == '"pulse1"'


def test_variable_ref():
    ref = VariableRef("var1")
    assert ref.var == "var1"


def test_variable_ref_serialization():
    ref = VariableRef("var1")
    assert ref.model_dump() == "var1"  # type: ignore


def test_variable_ref_validation():
    ref = VariableRef.model_validate("var1")
    assert ref.var == "var1"


def test_variable_ref_json_validation():
    ref = VariableRef.model_validate_json('"var1"')
    assert ref.var == "var1"


def test_variable_ref_json_serialization():
    ref = VariableRef("var1")
    assert ref.model_dump_json() == '"var1"'
