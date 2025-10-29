"""Utility classes and functions for the builder interface.

This module contains supporting utilities for building pulse sequences and schedules,
including operation tokens, schedule parameters, and resolution functions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict

if TYPE_CHECKING:
    from ..models.schedule import RefPtLike, RelTimeLike, ScheduledOperation

__all__ = ("OperationToken", "ScheduleParams", "resolve_schedule_params")


class ScheduleParams(TypedDict, total=False):
    """Type definition for schedule parameters used in builder operations.

    :param name: Optional name for the operation
    :param rel_time: Relative time from the reference point
    :param ref_op: Name of or token for the reference operation
    :param ref_pt: Reference point on the reference operation
    :param ref_pt_new: Reference point on the new operation
    """

    name: str | None
    rel_time: RelTimeLike | None
    ref_op: str | OperationToken | None
    ref_pt: RefPtLike | None
    ref_pt_new: RefPtLike | None


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

    # Resolve operation token to name
    if "ref_op" in resolved and isinstance(resolved["ref_op"], OperationToken):
        resolved["ref_op"] = resolved["ref_op"].name

    # Remove rel_time if it's 0 (will use default None)
    if "rel_time" in resolved and resolved["rel_time"] == 0:
        del resolved["rel_time"]

    return resolved
