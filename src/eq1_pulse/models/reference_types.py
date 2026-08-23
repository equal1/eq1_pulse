"""Modules to provide representation of symbolic references.

A reference names something the program does not spell out inline: a variable, an externally
resolved constant, a declared pulse, or a channel. Every one of them has exactly one wire form.

Three of the four are *tagged objects* -- ``{"var": "amp"}``, ``{"ext": "q0.f01"}``,
``{"pulse_name": "pi_pulse"}`` -- and are the :class:`Reference` subclasses below: a plain
one-field model already validates and serializes that object in both schema modes, so there is
nothing to wrap, unwrap, or describe by hand.

The fourth, :class:`ChannelRef`, is the bare string ``"q0_drive"``. It is a
:class:`~pydantic.RootModel` rather than a :class:`Reference`, because a root model has no field
name to publish and is therefore bare by construction. The carve-out is argued on issue #10:
``channel`` and ``channels`` are closed, single-purpose fields in which a string can mean nothing
else, and a channel reference is the most frequent value in a program.

:class:`VariableRef` has *two* wire forms, chosen by position rather than by type, which is why the
carve-out lives in an annotation -- :obj:`VarName` -- rather than in the class:

* In a field typed exactly :class:`VariableRef` it is the bare name ``"iq"``. The field name already
  says the value is a variable, so ``{"var": {"var": "iq"}}`` spells the tag twice. This is the
  same argument as :class:`ChannelRef`'s, and the fields are the same kind of closed,
  single-purpose slot: ``Record.var``, ``Iteration.var``, ``Store.source`` and their four siblings.
* In a union of references -- :obj:`SymbolRef`, ``ValueRef``, ``ExternalParamValue``,
  :attr:`~eq1_pulse.models.expressions.SymbolExpr.symbol` -- it keeps ``{"var": "iq"}``. There a
  bare string is not unambiguous: it would have to be told apart from :class:`ExternalRef`, whose
  wire form is also a name, and from ``ExternalParamValue``'s plain :obj:`str` member, whose value
  is the string itself. The tag is what makes the union decidable.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Annotated, Any, Final, TypedDict, Union, get_args

from pydantic import BaseModel, Discriminator, GetCoreSchemaHandler, GetJsonSchemaHandler, RootModel, Tag
from pydantic_core import core_schema

from .base_models import NoExtrasModel
from .identifier_str import ExternalSymbolStr, IdentifierStr

if TYPE_CHECKING:
    from pydantic.json_schema import JsonSchemaValue
    from pydantic_core import CoreSchema

__all__ = (
    "ChannelRef",
    "ChannelRefLike",
    "ChannelTarget",
    "ExtRefDict",
    "ExternalRef",
    "PulseRef",
    "PulseRefLike",
    "Reference",
    "ReferenceDiscriminator",
    "SymbolRef",
    "SymbolRefLike",
    "VarName",
    "VariableRef",
    "VariableRefLike",
)


class Reference(NoExtrasModel):
    """Base class for the tagged symbolic references.

    A descendant declares exactly one field, whose name is the tag its wire object carries:
    :class:`VariableRef` is ``{"var": ...}``, :class:`ExternalRef` is ``{"ext": ...}``,
    :class:`PulseRef` is ``{"pulse_name": ...}``. That object is the wire form in both directions
    and in both schema modes, so this base adds no serializer, no validator and no schema hook --
    only the positional constructor sugar and the comparison against a bare name.

    ``extra="forbid"`` (via :class:`NoExtrasModel`) keeps that object exactly one field wide: without
    it, an object with the tag key plus unrelated keys would validate and silently drop the extras,
    letting a malformed or ambiguous tagged object slip past :class:`ReferenceDiscriminator`, which
    routes strictly on "the sole key this object carries".

    Note:
        :class:`ChannelRef` is deliberately *not* here. Its wire form is the bare channel name, and
        a :class:`~pydantic.RootModel` produces that with no machinery at all; see the module
        docstring.

    """

    @classmethod
    def _first_field_name(cls) -> str:
        return next(iter(cls.model_fields))

    def __init__(self, *args, **data) -> None:
        """Create a reference.

        Accepts the type of the first field also as positional argument.
        """
        ff = self._first_field_name()
        assert len(args) in (0, 1)
        if len(args) == 1:
            assert ff not in data
            data[ff] = args[0]
        super().__init__(**data)

    def __eq__(self, value):  # noqa: D105
        if not isinstance(value, Reference):
            first_field_value = getattr(self, self._first_field_name())
            return first_field_value == value

        return super().__eq__(value)


class VariableRef(Reference):
    """Reference to a variable, spelled ``{"var": "amp"}``.

    Variables must be declared in the surrounding context or one of its parents.
    """

    if TYPE_CHECKING:

        def __init__(self, var: str, **data):  # noqa: D107
            super().__init__(var=var, **data)

    var: IdentifierStr
    """The name of the variable being referenced."""


class ExternalRef(Reference):
    """Reference to a constant that is resolved outside the program, spelled ``{"ext": "q0.f01"}``.

    External symbols must be declared in the surrounding context or one of its parents. Their value
    is supplied per submission by the framework running the program, so a serialized program can be
    re-submitted against fresh values without being rebuilt.
    """

    if TYPE_CHECKING:

        def __init__(self, ext: str, **data):  # noqa: D107
            super().__init__(ext=ext, **data)

    ext: ExternalSymbolStr
    """The name of the external symbol being referenced."""


class PulseRef(Reference):
    """Reference to a pulse, spelled ``{"pulse_name": "pi_pulse"}``.

    Pulses must be declared in the surrounding context or one of its parents.
    """

    if TYPE_CHECKING:

        def __init__(self, pulse_name: str, **data):  # noqa: D107
            super().__init__(pulse_name=pulse_name, **data)

    pulse_name: IdentifierStr
    """The name of the pulse being referenced."""


class ChannelRef(RootModel[IdentifierStr]):
    """Reference to a channel, whose wire form is the bare channel name ``"q0_drive"``.

    Channels are defined in the target's hardware configuration.

    Unlike the :class:`Reference` subclasses this is a :class:`~pydantic.RootModel`, so the name
    *is* the model and there is no field name to spell twice. It validates and serializes the bare
    string in both schema modes with no override of any kind; :meth:`__eq__` below is the only
    member it carries.
    """

    root: IdentifierStr
    """The name of the channel being referenced."""

    def __eq__(self, value):  # noqa: D105
        if not isinstance(value, ChannelRef):
            return self.root == value

        return super().__eq__(value)


class ReferenceDiscriminator:
    """Annotation marker turning a union of reference types into a union tagged by wire form.

    Written once and applied to each union of references::

        type SymbolRef = Annotated[VariableRef | ExternalRef, ReferenceDiscriminator()]

    A :class:`Reference` member is tagged by the sole key its wire object carries, read off the one
    field it declares, so a new reference type is tagged by declaring it. :class:`ChannelRef` is
    the one member whose wire form is a bare string rather than an object; it is tagged by *being*
    a string, under :data:`_BARE_TAG`.

    Selection is a lookup on the wire shape rather than a scoring pass over every member, so a
    malformed reference is one ``union_tag_not_found`` error naming the forms that exist, instead
    of one error per member.
    """

    _BARE_TAG: Final = "channel"
    """The tag of the one reference whose wire form is bare -- named for the field it appears in."""

    def __get_pydantic_core_schema__(self, source_type: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
        """Build the tagged union's core schema from *source_type*'s members.

        :param source_type: The union of reference models this annotates.
        :param handler: The handler generating core schemas, reused for the rebuilt annotation.
        :return: The core schema of the equivalent :class:`~pydantic.Discriminator`-keyed union.
        :raises TypeError: If applied to anything but a union -- there is nothing to discriminate.
        """
        if not (references := get_args(source_type)):
            raise TypeError(f"{type(self).__name__} annotates a union of reference models, not {source_type!r}")

        tags = {reference: self._tag_of(reference) for reference in references}
        # The tag of the bare-string member, if this union has one at all. A union without one
        # (:obj:`SymbolRef`) has no string form, so a string there is untaggable rather than
        # mistagged.
        bare_tag = next((tag for reference, tag in tags.items() if issubclass(reference, RootModel)), None)

        def reference_tag(value: Any) -> str | None:
            """Return the tag *value* is spelled with, or :obj:`None` to report an unknown tag."""
            if isinstance(value, str):
                return bare_tag
            if isinstance(value, Mapping):
                if len(value) != 1:
                    return None
                # An object is tagged by its sole key -- but never by the bare tag, which names a
                # *string* form. ``{"channel": "ch1"}`` is the wrapped spelling this plan removed,
                # not a channel, and routing it to ChannelRef would report it as "not a string".
                tag = next(iter(value))
                return None if tag == bare_tag else tag
            return tags.get(type(value))

        members = tuple(Annotated[reference, Tag(tag)] for reference, tag in tags.items())
        return handler.generate_schema(Annotated[Union[*members], Discriminator(reference_tag)])

    @classmethod
    def _tag_of(cls, reference: type[BaseModel]) -> str:
        """The tag *reference*'s wire form carries.

        :param reference: A member of the annotated union.
        :return: The sole field name for a tagged :class:`Reference`, or :data:`_BARE_TAG` for a
            root model, which has no field name and whose wire form is therefore the bare value.
        """
        if issubclass(reference, RootModel):
            return cls._BARE_TAG

        return next(iter(reference.model_fields))


class VarRefDict(TypedDict):
    """Type dict for variable references.

    Example:

    .. code-block:: python

        {"var": "<variable_name>"}
    """

    var: str
    """The name of the variable being referenced."""


type VariableRefLike = VariableRef | VarRefDict
"""Type alias for valid arguments to create :class:`VariableRef` instances.

A bare string is not one of them: an identifier-shaped string is a string. The builder still
promotes one to a variable reference -- see :func:`~eq1_pulse.builder._coerce.as_symbol_ref` --
but that is a builder convenience and its signatures say so.
"""


def _bare_variable_name(value: VariableRef) -> str:
    """Serialize a bare variable reference as the name it carries.

    :param value: The reference held by a :obj:`VarName` field.
    :return: The variable name, which is that field's whole wire form.
    """
    return value.var


class _BareVariableRef:
    """Annotation marker spelling a :class:`VariableRef` field as the bare variable name.

    Applied through :obj:`VarName`; never written at a field directly.

    A field typed exactly :class:`VariableRef` already says its value is a variable, so the
    ``{"var": ...}`` tag inside it repeats the field name and nothing else: ``{"var": {"var": "iq"}}``
    where ``"iq"`` says the same. Union positions keep the tag; see the module docstring for why.

    The JSON side accepts the name and nothing else, so the accepted wire form is exactly the one
    the schema publishes. The Python side additionally accepts a :class:`VariableRef` instance and a
    :class:`VarRefDict`, which is what authoring code and the builder pass. That widening is kept
    out of :meth:`__get_pydantic_json_schema__`, which reports a string in *both* schema modes --
    otherwise the validation schema would describe an input shape the serialization schema never
    produces.
    """

    def __get_pydantic_core_schema__(self, source_type: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
        """Build the bare-name schema for the annotated :class:`VariableRef` field.

        :param source_type: The annotated type, :class:`VariableRef`.
        :param handler: The handler generating core schemas, reused for the tagged object form.
        :return: A core schema reading a name in JSON, and a name, instance or dict in Python.
        """
        from_name = core_schema.no_info_after_validator_function(VariableRef, handler.generate_schema(IdentifierStr))
        return core_schema.json_or_python_schema(
            json_schema=from_name,
            python_schema=core_schema.union_schema([from_name, handler(source_type)]),
            serialization=core_schema.plain_serializer_function_ser_schema(
                _bare_variable_name, return_schema=core_schema.str_schema()
            ),
        )

    def __get_pydantic_json_schema__(self, schema: CoreSchema, handler: GetJsonSchemaHandler) -> JsonSchemaValue:
        """Report the annotated field as a bare string.

        :param schema: The core schema built above, whose Python side is wider than the wire form.
        :param handler: The handler generating JSON schemas; unused, as the wire form is a string.
        :return: The JSON schema of a variable name, identical in the validation and serialization
            modes because it is built from neither.
        """
        return {"type": "string"}


type VarName = Annotated[VariableRef, _BareVariableRef()]
"""A :class:`VariableRef` field whose wire form is the bare variable name ``"iq"``.

Use it wherever a field is typed exactly :class:`VariableRef` -- never inside a union of references,
where the tag is what tells the members apart.
"""


class ExtRefDict(TypedDict):
    """Type dict for external symbol references.

    Example:

    .. code-block:: python

        {"ext": "<external_symbol>"}
    """

    ext: str
    """The name of the external symbol being referenced."""


class PulseRefDict(TypedDict):
    """Type dict for pulse references.

    Example:

    .. code-block:: python

        {"pulse_name": "<pulse_name>"}
    """

    pulse_name: str
    """The name of the pulse being referenced."""


type PulseRefLike = PulseRef | PulseRefDict
"""Type alias for valid arguments to create :class:`PulseRef` instances."""


type SymbolRef = Annotated[VariableRef | ExternalRef, ReferenceDiscriminator()]
"""Type alias for any reference to a named value: a program variable or an external constant.

Keyed on ``var``/``ext`` by :class:`ReferenceDiscriminator`. Neither member has a shorthand and
neither is preferred over the other, so there is no resolution order to depend on.
"""

type SymbolRefLike = VariableRefLike | ExternalRef | ExtRefDict
"""Type alias for valid arguments to create :obj:`SymbolRef` values."""


type ChannelTarget = Annotated[ChannelRef | ExternalRef, ReferenceDiscriminator()]
"""A channel, named directly or supplied externally: ``"q0_drive"`` or ``{"ext": "q0.drive"}``.

The two are told apart by JSON type -- string versus object -- by
:class:`ReferenceDiscriminator`, so a malformed channel produces one error naming which of the two
it failed to be.

An external channel is for a name the calibration store owns: which physical line drives ``q0``
should no more be hard-coded than ``q0.f01`` is.
"""

type ChannelRefLike = str | ChannelRef | ExternalRef | ExtRefDict
"""Type alias for valid arguments to denote a :obj:`ChannelTarget`.

The bare :obj:`str` here is the canonical wire form of a channel, not a convenience -- unlike the
strings the other ``*Like`` aliases dropped.
"""
