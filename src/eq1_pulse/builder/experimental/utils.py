"""Utility classes and functions for the builder interface.

This module contains supporting utilities for building pulse sequences and schedules,
including operation tokens, schedule parameters, and resolution functions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final, TypedDict

from ...models.experimental.schedule import RelTime
from .._coerce import as_quantity

if TYPE_CHECKING:
    from ...models.experimental.schedule import RefPtLike, RelTimeLike, ScheduledOperation

__all__ = ("SCHEDULE_PARAM_NAMES", "OperationToken", "ScheduleParams", "resolve_schedule_params")


class ScheduleParams(TypedDict, total=False):
    """Type definition for schedule parameters used in builder operations.

    :param op_name: Optional name for the operation. Spelled ``op_name`` rather than
        ``name`` because :func:`~eq1_pulse.builder.var_decl` and
        :func:`~eq1_pulse.builder.pulse_decl` already take a ``name`` of their own.
    :param rel_time: Relative time from the reference point
    :param ref_op: Name of or token for the reference operation
    :param ref_pt: Reference point on the reference operation
    :param ref_pt_new: Reference point on the new operation
    """

    op_name: str | None
    rel_time: RelTimeLike | None
    ref_op: str | OperationToken | None
    ref_pt: RefPtLike | None
    ref_pt_new: RefPtLike | None


SCHEDULE_PARAM_NAMES: Final[frozenset[str]] = frozenset(ScheduleParams.__annotations__)
"""The parameter names accepted wherever ``**schedule_params`` appears."""


class OperationToken:
    """Token representing a scheduled operation for reference in relative positioning.

    :param name: The name assigned to the operation
    :param operation: The scheduled operation this token refers to
    """

    def __init__(self, name: str, operation: ScheduledOperation):
        """Initialize an operation token."""
        self.name = name
        self.operation = operation

    def __str__(self) -> str:
        """Return the operation name."""
        return self.name


def resolve_schedule_params(params: ScheduleParams) -> dict[str, Any]:
    """Resolve operation tokens in schedule parameters to operation names.

    This utility function processes schedule parameters and converts any
    :class:`OperationToken` references in the ``ref_op`` field to their
    corresponding operation names (strings).

    :param params: Schedule parameters potentially containing operation tokens

    :return: Resolved parameters with tokens replaced by operation names

    :raises TypeError: If an unrecognised parameter name is passed

    Examples

    .. code-block:: python

        from eq1_pulse.builder import play, square_pulse, resolve_schedule_params

        # With token
        token = play("ch1", pulse)
        params = {"ref_op": token, "ref_pt": "end"}
        resolved = resolve_schedule_params(params)
        # resolved["ref_op"] is now the string name

        # Without token (already a string)
        params = {"ref_op": "op_1", "ref_pt": "end"}
        resolved = resolve_schedule_params(params)
        # resolved["ref_op"] remains "op_1"
    """
    resolved: dict[str, Any] = dict(params)

    # Reject anything that is not a schedule parameter, rather than silently dropping
    # it further down. "name" gets its own message: it is what ScheduledOperation calls
    # the field, so it is the natural thing to reach for.
    if unknown := set(resolved) - SCHEDULE_PARAM_NAMES:
        if "name" in unknown:
            raise TypeError("Use 'op_name' to name a scheduled operation, not 'name'.")
        known = ", ".join(sorted(SCHEDULE_PARAM_NAMES))
        raise TypeError(f"Unknown schedule parameter(s): {', '.join(sorted(unknown))}. Expected one of: {known}.")

    # Resolve operation token to name
    if "ref_op" in resolved and isinstance(resolved["ref_op"], OperationToken):
        resolved["ref_op"] = resolved["ref_op"].name

    # Remove rel_time if it's 0 (will use default None), and read the authoring forms of the rest
    # here rather than at the model: ScheduledOperation.rel_time takes the canonical object only.
    if "rel_time" in resolved:
        if resolved["rel_time"] == 0 or resolved["rel_time"] is None:
            resolved.pop("rel_time")
        else:
            resolved["rel_time"] = as_quantity(RelTime, resolved["rel_time"])

    return resolved
