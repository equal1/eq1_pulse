"""The schema-symmetry invariant (issue #10, tasks 1 and 7).

For every model ``M`` in :func:`get_all_pydantic_models`:
``M.model_json_schema(mode="validation") == M.model_json_schema(mode="serialization")``.
"""

from eq1_pulse.utilities.openapi_generator import get_all_pydantic_models

# Task 3 replaced SequenceBase with a RootModel, so the two containers rooted on it -- the last
# models with no serialization-mode schema at all -- describe themselves like everything else.
# There is no longer any exception to "no empty schemas".
_EMPTY_SCHEMA_EXCEPTIONS: frozenset[str] = frozenset()


def test_no_model_differs_between_validation_and_serialization_schema():
    """Every model's validation and serialization schemas agree.

    A model that reappears here has grown an input-only wire form, or a schema-generation hook has
    lost information rebuilding one of the two modes -- either way, name it and fix it; do not
    special-case it into a ledger.
    """
    asymmetric = {
        model.__name__
        for model in get_all_pydantic_models()
        if model.model_json_schema(mode="validation") != model.model_json_schema(mode="serialization")
    }
    assert not asymmetric, f"Models with mismatched validation/serialization schemas: {sorted(asymmetric)}"


def test_no_empty_serialization_schemas():
    """No model's serialization-mode schema is empty or title-only, :data:`_EMPTY_SCHEMA_EXCEPTIONS` apart.

    ``LeanModel``'s plain ``@model_serializer(mode="wrap")`` declares no ``return_type``, so before
    task 1's fix, ``handler(core_schema)`` had nothing to derive an output schema from and every
    such model's serialization schema collapsed to ``{}``.
    """
    for model in get_all_pydantic_models():
        if model.__name__ in _EMPTY_SCHEMA_EXCEPTIONS:
            continue
        schema = model.model_json_schema(mode="serialization")
        content_keys = set(schema) - {"$defs", "title"}
        assert content_keys, f"{model.__name__}'s serialization schema is empty or title-only: {schema}"


def _canonical_round_trip_instances():
    """One representative instance per model family, covering every module :func:`get_all_pydantic_models` scans."""
    from eq1_pulse.models.basic_types import Amplitude, Duration, Threshold
    from eq1_pulse.models.channel_ops import Wait
    from eq1_pulse.models.data_ops import ComparisonMode, Discriminate, VariableDecl
    from eq1_pulse.models.expressions import BinaryExpr, LiteralExpr, SymbolExpr
    from eq1_pulse.models.external_block import ExternalBlock
    from eq1_pulse.models.pulse_types import SquarePulse
    from eq1_pulse.models.reference_types import ExternalRef, PulseRef, VariableRef
    from eq1_pulse.models.sequence import OpSequence, Repetition
    from eq1_pulse.models.units import Seconds

    return [
        Seconds(s=10),
        Duration("10us"),
        Amplitude("100mV"),
        VariableRef(var="amp"),
        PulseRef(pulse_name="p1"),
        ExternalRef(ext="q0.f01"),
        Wait(channels=["ch1"], duration=Duration("10us")),
        SquarePulse(duration=Duration("10us"), amplitude=Amplitude("100mV")),
        VariableDecl("x", dtype="float"),
        Discriminate(
            target=VariableRef(var="outcome"),
            source=VariableRef(var="iq"),
            threshold=Threshold(V=0.5),
            compare=ComparisonMode.GreaterEqual,
        ),
        ExternalBlock(program="eq1.cal.measure", channels={"readout": "ch1"}, duration=Duration("10us")),
        BinaryExpr(
            binary_op="*",
            lhs=SymbolExpr(symbol=VariableRef(var="scale")),
            rhs=LiteralExpr(value=Amplitude("80mV")),
        ),
        Repetition(count=3, body=OpSequence([Wait(channels=["ch1"], duration=Duration("10us"))])),
        OpSequence([Wait(channels=["ch1"], duration=Duration("10us"))]),
    ]


def test_round_trip_preserves_the_canonical_document():
    """``dump(validate(d)) == d`` for a canonical document per model family.

    The symmetry tests above check that the *shape described by the schema* agrees between modes;
    this checks that *actual data* survives a validate/dump cycle unchanged, which is what the
    schema promises when it says the two modes agree.
    """
    import json

    for instance in _canonical_round_trip_instances():
        model = type(instance)
        document = json.loads(instance.model_dump_json())
        round_tripped = json.loads(model.model_validate(document).model_dump_json())
        assert round_tripped == document, f"{model.__name__} did not round-trip: {document} -> {round_tripped}"
