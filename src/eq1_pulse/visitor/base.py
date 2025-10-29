"""Base visitor classes for traversing pulse models.

This module provides abstract base classes and concrete implementations for
traversing Schedule and Sequence models using the visitor pattern.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..models.channel_ops import (
        Barrier,
        CompensateDC,
        Play,
        Record,
        SetFrequency,
        SetPhase,
        ShiftFrequency,
        ShiftPhase,
        Trace,
        Wait,
    )
    from ..models.data_ops import Discriminate, PulseDecl, Store, VariableDecl
    from ..models.schedule import (
        SchedConditional,
        SchedIteration,
        SchedRepetition,
        Schedule,
        ScheduledOperation,
    )
    from ..models.sequence import (
        Conditional,
        Iteration,
        OpSequence,
        Repetition,
    )

__all__ = (
    "BaseVisitor",
    "ScheduleVisitor",
    "SequenceVisitor",
)


class BaseVisitor[T](ABC):
    """Abstract base class for all visitors.

    This class defines the interface for visiting different types of operations
    in pulse models. Subclasses should implement the visit methods for the
    specific operation types they need to handle.

    The visitor pattern allows you to separate traversal logic from the operations
    being performed on the nodes.
    """

    # Channel operations
    def visit_Play(self, node: Play) -> T:
        """Visit a Play operation.

        :param node: The Play operation to visit

        :return: Result of visiting the Play operation
        """
        return self.generic_visit(node)

    def visit_Wait(self, node: Wait) -> T:
        """Visit a Wait operation.

        :param node: The Wait operation to visit

        :return: Result of visiting the Wait operation
        """
        return self.generic_visit(node)

    def visit_Barrier(self, node: Barrier) -> T:
        """Visit a Barrier operation.

        :param node: The Barrier operation to visit

        :return: Result of visiting the Barrier operation
        """
        return self.generic_visit(node)

    def visit_SetFrequency(self, node: SetFrequency) -> T:
        """Visit a SetFrequency operation.

        :param node: The SetFrequency operation to visit

        :return: Result of visiting the SetFrequency operation
        """
        return self.generic_visit(node)

    def visit_ShiftFrequency(self, node: ShiftFrequency) -> T:
        """Visit a ShiftFrequency operation.

        :param node: The ShiftFrequency operation to visit

        :return: Result of visiting the ShiftFrequency operation
        """
        return self.generic_visit(node)

    def visit_SetPhase(self, node: SetPhase) -> T:
        """Visit a SetPhase operation.

        :param node: The SetPhase operation to visit

        :return: Result of visiting the SetPhase operation
        """
        return self.generic_visit(node)

    def visit_ShiftPhase(self, node: ShiftPhase) -> T:
        """Visit a ShiftPhase operation.

        :param node: The ShiftPhase operation to visit

        :return: Result of visiting the ShiftPhase operation
        """
        return self.generic_visit(node)

    def visit_Record(self, node: Record) -> T:
        """Visit a Record operation.

        :param node: The Record operation to visit

        :return: Result of visiting the Record operation
        """
        return self.generic_visit(node)

    def visit_Trace(self, node: Trace) -> T:
        """Visit a Trace operation.

        :param node: The Trace operation to visit

        :return: Result of visiting the Trace operation
        """
        return self.generic_visit(node)

    def visit_CompensateDC(self, node: CompensateDC) -> T:
        """Visit a CompensateDC operation.

        :param node: The CompensateDC operation to visit

        :return: Result of visiting the CompensateDC operation
        """
        return self.generic_visit(node)

    # Data operations
    def visit_VariableDecl(self, node: VariableDecl) -> T:
        """Visit a VariableDecl operation.

        :param node: The VariableDecl operation to visit

        :return: Result of visiting the VariableDecl operation
        """
        return self.generic_visit(node)

    def visit_PulseDecl(self, node: PulseDecl) -> T:
        """Visit a PulseDecl operation.

        :param node: The PulseDecl operation to visit

        :return: Result of visiting the PulseDecl operation
        """
        return self.generic_visit(node)

    def visit_Discriminate(self, node: Discriminate) -> T:
        """Visit a Discriminate operation.

        :param node: The Discriminate operation to visit

        :return: Result of visiting the Discriminate operation
        """
        return self.generic_visit(node)

    def visit_Store(self, node: Store) -> T:
        """Visit a Store operation.

        :param node: The Store operation to visit

        :return: Result of visiting the Store operation
        """
        return self.generic_visit(node)

    @abstractmethod
    def generic_visit(self, node: Any) -> T:
        """Called for nodes where no specific visit method exists.

        :param node: The node to visit

        :return: Result of visiting the node
        """
        ...

    def visit(self, node: Any) -> T:
        """Dispatch to the appropriate visit method based on node type.

        :param node: The node to visit

        :return: Result of visiting the node
        """
        # Get the class name and convert to visit method name
        method_name = f"visit_{node.__class__.__name__}"
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)


class SequenceVisitor[T](BaseVisitor[T]):
    """Visitor for traversing Sequence models.

    This visitor provides traversal methods specific to sequences, including
    repetitions, iterations, and conditionals that contain OpSequence bodies.
    """

    def visit_OpSequence(self, node: OpSequence) -> T:
        """Visit an OpSequence.

        :param node: The OpSequence to visit

        :return: Result of visiting the OpSequence
        """
        results = [self.visit(item) for item in node.items]
        return self.combine_sequence_results(node, results)

    def visit_Repetition(self, node: Repetition) -> T:
        """Visit a Repetition operation.

        :param node: The Repetition operation to visit

        :return: Result of visiting the Repetition operation
        """
        body_result = self.visit_OpSequence(node.body)
        return self.combine_repetition(node, body_result)

    def visit_Iteration(self, node: Iteration) -> T:
        """Visit an Iteration operation.

        :param node: The Iteration operation to visit

        :return: Result of visiting the Iteration operation
        """
        body_result = self.visit_OpSequence(node.body)
        return self.combine_iteration(node, body_result)

    def visit_Conditional(self, node: Conditional) -> T:
        """Visit a Conditional operation.

        :param node: The Conditional operation to visit

        :return: Result of visiting the Conditional operation
        """
        body_result = self.visit_OpSequence(node.body)
        return self.combine_conditional(node, body_result)

    def combine_sequence_results(self, node: OpSequence, results: list[T]) -> T:
        """Combine results from visiting items in a sequence.

        :param node: The OpSequence node
        :param results: List of results from visiting each item

        :return: Combined result
        """
        return self.generic_visit(node)

    def combine_repetition(self, node: Repetition, body_result: T) -> T:
        """Combine result from visiting a repetition body.

        :param node: The Repetition node
        :param body_result: Result from visiting the body

        :return: Combined result
        """
        return self.generic_visit(node)

    def combine_iteration(self, node: Iteration, body_result: T) -> T:
        """Combine result from visiting an iteration body.

        :param node: The Iteration node
        :param body_result: Result from visiting the body

        :return: Combined result
        """
        return self.generic_visit(node)

    def combine_conditional(self, node: Conditional, body_result: T) -> T:
        """Combine result from visiting a conditional body.

        :param node: The Conditional node
        :param body_result: Result from visiting the body

        :return: Combined result
        """
        return self.generic_visit(node)

    def generic_visit(self, node: Any) -> T:
        """Called for nodes where no specific visit method exists.

        :param node: The node to visit

        :return: Result of visiting the node

        :raises NotImplementedError: Always raised as this must be overridden
        """
        raise NotImplementedError(f"No visit method for {type(node).__name__}")


class ScheduleVisitor[T](BaseVisitor[T]):
    """Visitor for traversing Schedule models.

    This visitor provides traversal methods specific to schedules, including
    repetitions, iterations, and conditionals that contain Schedule bodies.
    """

    def visit_Schedule(self, node: Schedule) -> T:
        """Visit a Schedule.

        :param node: The Schedule to visit

        :return: Result of visiting the Schedule
        """
        results = [self.visit_ScheduledOperation(item) for item in node.items]
        return self.combine_schedule_results(node, results)

    def visit_ScheduledOperation(self, node: ScheduledOperation) -> T:
        """Visit a ScheduledOperation.

        :param node: The ScheduledOperation to visit

        :return: Result of visiting the ScheduledOperation
        """
        op_result = self.visit(node.op)
        return self.combine_scheduled_operation(node, op_result)

    def visit_SchedRepetition(self, node: SchedRepetition) -> T:
        """Visit a SchedRepetition operation.

        :param node: The SchedRepetition operation to visit

        :return: Result of visiting the SchedRepetition operation
        """
        body_result = self.visit_Schedule(node.body)
        return self.combine_sched_repetition(node, body_result)

    def visit_SchedIteration(self, node: SchedIteration) -> T:
        """Visit a SchedIteration operation.

        :param node: The SchedIteration operation to visit

        :return: Result of visiting the SchedIteration operation
        """
        body_result = self.visit_Schedule(node.body)
        return self.combine_sched_iteration(node, body_result)

    def visit_SchedConditional(self, node: SchedConditional) -> T:
        """Visit a SchedConditional operation.

        :param node: The SchedConditional operation to visit

        :return: Result of visiting the SchedConditional operation
        """
        body_result = self.visit_Schedule(node.body)
        return self.combine_sched_conditional(node, body_result)

    def combine_schedule_results(self, node: Schedule, results: list[T]) -> T:
        """Combine results from visiting items in a schedule.

        :param node: The Schedule node
        :param results: List of results from visiting each scheduled operation

        :return: Combined result
        """
        return self.generic_visit(node)

    def combine_scheduled_operation(self, node: ScheduledOperation, op_result: T) -> T:
        """Combine result from visiting a scheduled operation.

        :param node: The ScheduledOperation node
        :param op_result: Result from visiting the operation

        :return: Combined result
        """
        return op_result

    def combine_sched_repetition(self, node: SchedRepetition, body_result: T) -> T:
        """Combine result from visiting a schedule repetition body.

        :param node: The SchedRepetition node
        :param body_result: Result from visiting the body

        :return: Combined result
        """
        return self.generic_visit(node)

    def combine_sched_iteration(self, node: SchedIteration, body_result: T) -> T:
        """Combine result from visiting a schedule iteration body.

        :param node: The SchedIteration node
        :param body_result: Result from visiting the body

        :return: Combined result
        """
        return self.generic_visit(node)

    def combine_sched_conditional(self, node: SchedConditional, body_result: T) -> T:
        """Combine result from visiting a schedule conditional body.

        :param node: The SchedConditional node
        :param body_result: Result from visiting the body

        :return: Combined result
        """
        return self.generic_visit(node)

    def generic_visit(self, node: Any) -> T:
        """Called for nodes where no specific visit method exists.

        :param node: The node to visit

        :return: Result of visiting the node

        :raises NotImplementedError: Always raised as this must be overridden
        """
        raise NotImplementedError(f"No visit method for {type(node).__name__}")
