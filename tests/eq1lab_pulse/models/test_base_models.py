"""The ``{tag: payload}`` wire form :class:`NestedWireModel` layers on top of :class:`LeanModel`.

Every model exercised here is a throwaway declared in this file, so the machinery is tested
independently of whichever real models happen to be on it. :func:`test_lean_model_output_is_untouched`
pins the other half of the claim -- that a plain :class:`LeanModel` serializes exactly as it did
before :class:`NestedWireModel` existed.
"""

from typing import Any, ClassVar, Literal

import pytest
from pydantic import BaseModel, Field, ValidationError, model_serializer

from eq1_pulse.models.base_models import LeanModel, NestedWireModel


class TaggedByValue(NestedWireModel):
    """Tagged by the value of its tag source, the rule operations use.

    Carries a required field, so it can never reach an empty payload.
    """

    _wire_tag_source_: ClassVar[str] = "op_type"

    op_type: Literal["play"] = "play"
    channel: str
    scale: float = 1.0


class TaggedByValueAllDefaults(NestedWireModel):
    """Tagged by value, with every non-tag field defaulted, so D3's bare-tag form applies."""

    _wire_tag_source_: ClassVar[str] = "op_type"

    op_type: Literal["barrier"] = "barrier"
    channels: list[str] = Field(default_factory=list)


class TaggedByName(NestedWireModel):
    """Tagged by the *name* of its tag source, the rule expression operator nodes use.

    The operator value is kept inside the payload under ``"op"``, because operator values overlap
    between node types and only the field name tells them apart.
    """

    _wire_tag_source_: ClassVar[str] = "unary_op"
    _wire_tag_from_: ClassVar[Literal["value", "name"]] = "name"
    _wire_payload_key_: ClassVar[str | None] = "op"

    unary_op: Literal["-", "+"]
    rhs: int


class TaggedByNameDropped(NestedWireModel):
    """Tagged by *name*, with a single-valued operator dropped from the payload.

    The shape ``NotExpr`` needs: only the field name tells the node apart, and its one
    possible value carries nothing the name does not already carry, so repeating it inside
    would be the redundancy this wire format exists to remove.
    """

    _wire_tag_source_: ClassVar[str] = "not_op"
    _wire_tag_from_: ClassVar[Literal["value", "name"]] = "name"

    not_op: Literal["not"]
    rhs: int


class Unconfigured(NestedWireModel):
    """A subclass that never names a tag source, and so must behave exactly like a lean model."""

    op_type: Literal["plain"] = "plain"
    amount: int = 0


class NoStaticTag(NestedWireModel):
    """A tag source that is not a single-valued literal: the tag is unknowable, so no wrap happens.

    This is the shape an abstract base such as ``OpBase`` has before its subclasses narrow
    ``op_type`` to a concrete literal.
    """

    _wire_tag_source_: ClassVar[str] = "op_type"

    op_type: str


class Holder(NestedWireModel):
    """Holds another wrapped model, which is how operations nest inside a body."""

    _wire_tag_source_: ClassVar[str] = "op_type"

    op_type: Literal["holder"] = "holder"
    inner: TaggedByValue


class PlainLean(LeanModel):
    """A plain lean model, used to pin the unwrapped behaviour this change must not disturb."""

    op_type: Literal["lean"] = "lean"
    channel: str
    scale: float = 1.0


def test_tag_is_the_field_value_when_no_payload_key_is_set():
    """``op_type: Literal["play"]`` puts the *value* at the key and does not repeat it inside."""
    assert TaggedByValue(channel="q0").model_dump() == {"play": {"channel": "q0"}}
    assert TaggedByValue(channel="q0", scale=0.5).model_dump() == {"play": {"channel": "q0", "scale": 0.5}}


def test_tag_is_the_field_name_when_a_payload_key_is_set():
    """``_wire_payload_key_ = "op"`` puts the field *name* at the key and its value under ``op``."""
    assert TaggedByName(unary_op="-", rhs=3).model_dump() == {"unary_op": {"op": "-", "rhs": 3}}


def test_tag_from_name_can_drop_a_single_valued_operator():
    """The two knobs are orthogonal: tag from the name, and still drop the value."""
    assert TaggedByNameDropped(not_op="not", rhs=3).model_dump() == {"not_op": {"rhs": 3}}


def test_tag_from_name_with_a_dropped_value_round_trips():
    """The dropped operator is recovered from the field's sole literal, not from the tag."""
    document = {"not_op": {"rhs": 3}}
    restored = TaggedByNameDropped.model_validate(document)
    assert restored.not_op == "not"
    assert restored.rhs == 3
    assert restored.model_dump() == document


def test_payload_key_comes_first_in_the_payload():
    """The operator reads before its operands, as it does in the source it came from."""
    assert list(TaggedByName(unary_op="+", rhs=1).model_dump()["unary_op"]) == ["op", "rhs"]


@pytest.mark.parametrize(
    "instance",
    [
        TaggedByValue(channel="q0"),
        TaggedByValue(channel="q0", scale=0.25),
        TaggedByValueAllDefaults(),
        TaggedByValueAllDefaults(channels=["a", "b"]),
        TaggedByName(unary_op="-", rhs=3),
        Holder(inner=TaggedByValue(channel="q0", scale=0.5)),
    ],
    ids=lambda instance: type(instance).__name__,
)
def test_validate_of_dump_returns_the_same_model(instance):
    """``validate(dump(x)) == x``, through JSON as well as through Python objects."""
    model = type(instance)
    assert model.model_validate(instance.model_dump()) == instance
    assert model.model_validate_json(instance.model_dump_json()) == instance


@pytest.mark.parametrize(
    ("model", "document"),
    [
        (TaggedByValue, {"play": {"channel": "q0"}}),
        (TaggedByValue, {"play": {"channel": "q0", "scale": 0.25}}),
        (TaggedByValueAllDefaults, "barrier"),
        (TaggedByValueAllDefaults, {"barrier": {"channels": ["a"]}}),
        (TaggedByName, {"unary_op": {"op": "-", "rhs": 3}}),
        (Holder, {"holder": {"inner": {"play": {"channel": "q0", "scale": 0.5}}}}),
    ],
    ids=lambda parameter: getattr(parameter, "__name__", str(parameter)),
)
def test_dump_of_validate_returns_the_same_document(model, document):
    """``dump(validate(d)) == d`` for a canonical document, which is what "one wire form" means."""
    assert model.model_validate(document).model_dump() == document


def test_empty_payload_serializes_as_the_bare_tag():
    """D3: ``{"barrier": {}}`` carries nothing the key does not already carry, so the key is all there is.

    The annotation is needed because pydantic declares ``model_dump()`` as returning
    ``dict[str, Any]``, which the bare-tag form is deliberately not.
    """
    dumped: Any = TaggedByValueAllDefaults().model_dump()
    assert dumped == "barrier"
    assert TaggedByValueAllDefaults().model_dump_json() == '"barrier"'


def test_the_bare_tag_validates_back():
    """The bare-tag form is accepted wherever it is emitted, in Python and in JSON."""
    assert TaggedByValueAllDefaults.model_validate("barrier") == TaggedByValueAllDefaults()
    assert TaggedByValueAllDefaults.model_validate_json('"barrier"') == TaggedByValueAllDefaults()


def test_the_object_form_of_an_empty_payload_is_still_accepted():
    """The bare tag is what gets *emitted*; the explicit empty object remains readable."""
    assert TaggedByValueAllDefaults.model_validate({"barrier": {}}) == TaggedByValueAllDefaults()


def test_a_model_with_a_required_field_never_takes_the_bare_tag_form():
    """D3 is decided statically: a class that cannot reach an empty payload does not grow the form."""
    assert not TaggedByValue._wire_payload_can_be_empty()
    with pytest.raises(ValidationError):
        TaggedByValue.model_validate("play")


def test_a_model_keeping_its_tag_value_inside_never_takes_the_bare_tag_form():
    """A payload holding the operator always has at least that key, so it is never empty."""
    assert not TaggedByName._wire_payload_can_be_empty()
    with pytest.raises(ValidationError):
        TaggedByName.model_validate("unary_op")


@pytest.mark.parametrize(
    "document",
    [
        {"play": {"channel": "q0"}, "extra": 1},
        {"play": {"channel": "q0"}, "op_type": "play"},
        {"play": {"channel": "q0", "bogus": 1}},
        {"play": {"channel": "q0", "op_type": "play"}},
        {"not_a_tag": {"channel": "q0"}},
        {"play": "q0"},
    ],
    ids=str,
)
def test_malformed_wire_objects_are_rejected(document):
    """One key, naming the tag, pointing at a closed payload -- anything else is not this model."""
    with pytest.raises(ValidationError):
        TaggedByValue.model_validate(document)


def test_keyword_construction_still_works():
    """``__init__`` routes through the same validator, so the wrap must let a flat field set through."""
    assert TaggedByValue(channel="q0", scale=0.5).channel == "q0"
    assert TaggedByName(unary_op="+", rhs=2).unary_op == "+"
    assert TaggedByValueAllDefaults(channels=["a"]).channels == ["a"]


@pytest.mark.parametrize(
    "model",
    [TaggedByValue, TaggedByValueAllDefaults, TaggedByName, Unconfigured, NoStaticTag, Holder],
    ids=lambda model: model.__name__,
)
def test_both_schema_modes_agree(model):
    """The hook reshapes one schema rather than deriving two, so the modes cannot drift apart."""
    assert model.model_json_schema(mode="validation") == model.model_json_schema(mode="serialization")


@pytest.mark.parametrize(
    "model",
    [TaggedByValue, TaggedByValueAllDefaults, TaggedByName, Unconfigured, NoStaticTag, Holder],
    ids=lambda model: model.__name__,
)
def test_no_schema_is_empty_or_title_only(model):
    """The same invariant ``test_schema_symmetry.py`` holds over the real models."""
    schema = model.model_json_schema(mode="serialization")
    assert set(schema) - {"$defs", "title"}


def test_the_wrapped_schema_is_a_single_key_object():
    """The model's own schema names the tag, and the payload underneath is a closed record."""
    schema = TaggedByValue.model_json_schema()
    assert schema["type"] == "object"
    assert schema["required"] == ["play"]
    assert set(schema["properties"]) == {"play"}
    assert schema["additionalProperties"] is False

    payload = schema["properties"]["play"]
    assert payload["type"] == "object"
    assert payload["additionalProperties"] is False
    assert payload["required"] == ["channel"]
    assert set(payload["properties"]) == {"channel", "scale"}


def test_the_wrapped_schema_keeps_the_models_title_and_description():
    """``title`` and ``description`` stay on the schema published under the model's name."""
    schema = TaggedByValue.model_json_schema()
    assert schema["title"] == "TaggedByValue"
    assert schema["description"].startswith("Tagged by the value of its tag source")


def test_the_tag_source_is_renamed_rather_than_dropped_when_the_tag_is_its_name():
    """``unary_op`` leaves the payload; the value it carried is described under ``op`` instead."""
    payload = TaggedByName.model_json_schema()["properties"]["unary_op"]
    assert list(payload["properties"]) == ["op", "rhs"]
    assert payload["required"] == ["op", "rhs"]
    assert payload["properties"]["op"]["enum"] == ["-", "+"]


def test_the_bare_tag_form_appears_in_the_schema_only_where_it_applies():
    """The alternate form is part of a class's schema exactly when D3 gives it one."""
    empty_capable = TaggedByValueAllDefaults.model_json_schema()
    assert {"const": "barrier", "type": "string"} in empty_capable["anyOf"]

    assert "anyOf" not in TaggedByValue.model_json_schema()
    assert "anyOf" not in TaggedByName.model_json_schema()


@pytest.mark.parametrize(
    ("model", "instance"),
    [(Unconfigured, Unconfigured(amount=2)), (NoStaticTag, NoStaticTag(op_type="x"))],
    ids=lambda parameter: getattr(parameter, "__name__", str(parameter)),
)
def test_an_unconfigured_subclass_stays_flat(model, instance):
    """No tag source, or none that can be read statically, means no wrap at all -- in either direction."""
    flat = instance.model_dump()
    assert flat == {field: getattr(instance, field) for field in flat}
    assert model.model_validate(flat) == instance
    assert "properties" in model.model_json_schema()


def test_lean_model_output_is_untouched():
    """The machinery is additive: a plain :class:`LeanModel` dumps and validates exactly as before.

    Defaults are still elided, the single-valued literal discriminator is still kept, and the wire
    form is still the flat object -- none of which :class:`NestedWireModel` may reach into.
    """
    assert PlainLean(channel="q0").model_dump() == {"op_type": "lean", "channel": "q0"}
    assert PlainLean(channel="q0", scale=0.5).model_dump() == {"op_type": "lean", "channel": "q0", "scale": 0.5}
    assert PlainLean.model_validate({"op_type": "lean", "channel": "q0"}) == PlainLean(channel="q0")

    schema = PlainLean.model_json_schema()
    assert schema == PlainLean.model_json_schema(mode="serialization")
    assert set(schema["properties"]) == {"op_type", "channel", "scale"}
    assert schema["required"] == ["channel"]


class SelfReferential(NestedWireModel):
    """A node whose operand field points back at its own type, as expression nodes do.

    This is the shape that trips the pydantic-core defect
    :func:`test_pydantic_still_double_invokes_a_recursive_wrap_serializer` pins.
    """

    _wire_tag_source_: ClassVar[str] = "binary_op"
    _wire_tag_from_: ClassVar[Literal["value", "name"]] = "name"
    _wire_payload_key_: ClassVar[str | None] = "op"

    binary_op: Literal["+", "-"]
    rhs: "SelfReferential | int"


class SelfReferentialHolder(LeanModel):
    """Reaches a :class:`SelfReferential` through a field, which is what triggers the defect."""

    node: SelfReferential


SelfReferential.model_rebuild()
SelfReferentialHolder.model_rebuild()


def test_pydantic_still_double_invokes_a_recursive_wrap_serializer():
    """Pin the upstream defect :class:`NestedWireModel`'s re-entrancy guard works around.

    When a model with a ``@model_serializer(mode="wrap")`` is *both* self-referential and reached
    through another model's field, pydantic-core invokes the serializer twice on the same instance,
    the second time over the first's output -- pydantic#11812 and pydantic#11563.

    **This test failing is good news.** It means the upstream defect is fixed, and the guard in
    :meth:`NestedWireModel._wrap_serializer` -- along with the ``_wire_serializing`` context
    variable it reads -- can be deleted. Do not "fix" this test by loosening the assertion.
    """
    calls: list[str] = []

    class Node(BaseModel):
        name: str
        child: "Node | None" = None

        @model_serializer(mode="wrap")
        def _serialize(self, wrapped):
            calls.append(self.name)
            return {"wrapped": wrapped(self)}

    class Holder(BaseModel):
        node: Node

    Node.model_rebuild()
    Holder.model_rebuild()

    Holder(node=Node(name="a")).model_dump()
    assert calls == ["a", "a"], (
        "pydantic no longer double-invokes a recursive wrap serializer -- delete "
        "NestedWireModel's re-entrancy guard and the _wire_serializing ContextVar"
    )


def test_a_self_referential_node_is_wrapped_exactly_once():
    """The guard's payload: one wrap per node, however the node is reached.

    Without it the outermost node comes back double-wrapped -- ``{"binary_op": {"op": {"op": ...}}}``
    for a node that keeps its operator, and an empty ``{"binary_op": {}}`` for one that drops it.
    """
    node = SelfReferential(binary_op="+", rhs=SelfReferential(binary_op="-", rhs=1))

    standalone = node.model_dump()
    through_a_field = SelfReferentialHolder(node=node).model_dump()["node"]

    expected = {"binary_op": {"op": "+", "rhs": {"binary_op": {"op": "-", "rhs": 1}}}}
    assert standalone == expected
    assert through_a_field == expected, "reached through a field, the node was wrapped twice"
    assert SelfReferential.model_validate(expected) == node
