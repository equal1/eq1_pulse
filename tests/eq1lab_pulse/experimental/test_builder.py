"""Tests for the schedule half of the builder interface."""

import pytest

from eq1_pulse.builder import build_sequence, experimental, external_block, full_integration, sine_pulse, square_pulse
from eq1_pulse.builder import sub_sequence as sequence_sub_sequence
from eq1_pulse.builder.experimental import OperationToken
from eq1_pulse.models import Discriminate, Play, PulseDecl, SquarePulse, Store, VariableDecl
from eq1_pulse.models.experimental.schedule import RefPt, Schedule


class TestBuildSchedule:
    """Tests for build_schedule context manager."""

    def test_empty_schedule(self):
        """Test creating an empty schedule."""
        with experimental.build_schedule() as sched:
            pass
        assert isinstance(sched, Schedule)
        assert len(sched.items) == 0

    def test_schedule_with_operations(self):
        """Test schedule with operations and timing."""
        with experimental.build_schedule() as sched:
            op1 = experimental.play("ch1", square_pulse(duration="10us", amplitude="100mV"))
            experimental.play(
                "ch2", square_pulse(duration="10us", amplitude="100mV"), ref_op=op1, ref_pt="start", rel_time="5us"
            )

        assert len(sched.items) == 2

    def test_nested_schedule_representation(self):
        """Test nested schedule representation with sub_schedule context manager.

        The sub_schedule context manager creates a nested schedule and automatically
        adds it to the parent schedule with optional timing parameters.
        """
        with experimental.build_schedule() as outer:
            # Create inner schedule with operations
            with experimental.sub_schedule(op_name="sub_schedule") as _inner:
                experimental.play("ch1", square_pulse(duration="10us", amplitude="100mV"))
                experimental.play("ch2", square_pulse(duration="5us", amplitude="50mV"))

            # Add another operation relative to the nested schedule
            experimental.play(
                "ch3",
                square_pulse(duration="3us", amplitude="75mV"),
                ref_op="sub_schedule",
                ref_pt="end",
                rel_time="2us",
            )

        # Outer schedule should have 2 items: the nested schedule and the play operation
        assert len(outer.items) == 2

        # First item should be the inner schedule wrapped in ScheduledOperation
        assert isinstance(outer.items[0].op, Schedule)
        inner_sched = outer.items[0].op
        assert len(inner_sched.items) == 2
        assert outer.items[0].name == "sub_schedule"

        # Second item should be the play operation scheduled relative to the nested schedule
        assert isinstance(outer.items[1].op, Play)
        assert outer.items[1].ref_op == "sub_schedule"
        assert outer.items[1].ref_pt == RefPt.End
        assert outer.items[1].rel_time is not None

    def test_nested_schedule_modular_blocks(self):
        """Test using sub_schedule to create modular, reusable operation blocks.

        This demonstrates how sub-schedules can be used to encapsulate
        related operations (e.g., initialization, gates, readout) and
        compose them into larger schedules with precise timing control.
        """
        with experimental.build_schedule() as main_schedule:
            # Declare variable for measurement result
            experimental.var_decl("result", "complex", unit="mV")

            # Create initialization sub-schedule
            with experimental.sub_schedule(op_name="initialization"):
                experimental.play("qubit", square_pulse(duration="100ns", amplitude="200mV"))
                experimental.wait("qubit", duration="50ns")

            # Create gate operation positioned after initialization
            gate_token = experimental.play(
                "qubit",
                square_pulse(duration="20ns", amplitude="150mV"),
                ref_op="initialization",
                ref_pt="end",
                rel_time="10ns",
            )

            # Create measurement sub-schedule positioned after gate
            with experimental.sub_schedule(op_name="measurement", ref_op=gate_token, ref_pt="end", rel_time="50ns"):
                experimental.play("drive", square_pulse(duration="1us", amplitude="50mV"))
                experimental.record("readout", var="result", duration="1us", integration=full_integration())

        # Verify structure: var_decl + 2 sub-schedules + 1 gate operation
        assert len(main_schedule.items) == 4

        # Check var_decl is first
        assert isinstance(main_schedule.items[0].op, VariableDecl)

        # Check initialization block
        assert isinstance(main_schedule.items[1].op, Schedule)
        assert main_schedule.items[1].name == "initialization"
        init = main_schedule.items[1].op
        assert len(init.items) == 2  # play + wait

        # Check gate operation timing
        assert isinstance(main_schedule.items[2].op, Play)
        assert main_schedule.items[2].ref_op == "initialization"
        assert main_schedule.items[2].ref_pt == RefPt.End

        # Check measurement block
        assert isinstance(main_schedule.items[3].op, Schedule)
        assert main_schedule.items[3].name == "measurement"
        meas = main_schedule.items[3].op
        assert len(meas.items) == 2  # play + record
        assert main_schedule.items[3].ref_pt == RefPt.End

    def test_sub_schedule_outside_schedule_raises_error(self):
        """Test that sub_schedule outside a schedule context raises error."""
        with pytest.raises(RuntimeError, match="sub_schedule"):
            with experimental.sub_schedule(op_name="invalid"):
                experimental.play("ch1", square_pulse(duration="10us", amplitude="100mV"))

    def test_sub_schedule_in_sequence_raises_error(self):
        """Test that sub_schedule in a sequence context raises error."""
        with pytest.raises(RuntimeError, match="can only be used within a build_schedule"):
            with build_sequence():
                with experimental.sub_schedule(op_name="invalid"):
                    experimental.play("ch1", square_pulse(duration="10us", amplitude="100mV"))

    def test_sub_sequence_in_schedule_raises_error(self):
        """Test that sub_sequence in a schedule context raises error."""
        with pytest.raises(RuntimeError, match="requires a build_sequence"):
            with experimental.build_schedule():
                with sequence_sub_sequence():
                    experimental.play("ch1", square_pulse(duration="10us", amplitude="100mV"))


class TestBasicOperations:
    """Tests for basic operations in schedule context."""

    def test_wait_single_channel_in_schedule(self):
        """Test that wait with single channel works in schedule."""
        with experimental.build_schedule() as sched:
            experimental.wait("ch1", duration="5us")

        assert len(sched.items) == 1

    def test_wait_multiple_channels_in_schedule_raises_error(self):
        """Test that wait with multiple channels raises error in schedule."""
        with (
            pytest.raises(RuntimeError, match=r"Wait with multiple channels .* is not allowed in schedule context"),
            experimental.build_schedule(),
        ):
            experimental.wait("ch1", "ch2", duration="5us")

    def test_barrier_not_in_schedule(self):
        """Test that barrier raises error in schedule."""
        with (
            pytest.raises(RuntimeError, match="is not supported in schedule contexts"),
            experimental.build_schedule(),
        ):
            experimental.barrier("ch1", "ch2")


class TestVariables:
    """Tests for variable operations in schedule context."""

    def test_var_decl_in_schedule(self):
        """Test variable declaration in schedule context."""
        with experimental.build_schedule() as sched:
            experimental.var_decl("result", "complex", unit="mV")

        assert len(sched.items) == 1
        assert isinstance(sched.items[0].op, VariableDecl)
        assert sched.items[0].op.name == "result"
        assert sched.items[0].op.dtype == "complex"
        assert sched.items[0].op.unit == "mV"

    def test_var_decl_in_schedule_with_timing(self):
        """Test variable declaration in schedule with timing parameters."""
        with experimental.build_schedule() as sched:
            # Create a reference operation
            token = experimental.play("ch1", square_pulse(duration="10us", amplitude="100mV"), op_name="pulse1")

            # Declare variable positioned after the pulse
            var_token = experimental.var_decl(
                "data", "float", ref_op=token, ref_pt="end", rel_time="5us", op_name="var1"
            )

        assert len(sched.items) == 2
        assert isinstance(sched.items[1].op, VariableDecl)
        assert sched.items[1].op.name == "data"
        assert sched.items[1].name == "var1"
        assert sched.items[1].ref_op == "pulse1"
        assert sched.items[1].ref_pt == RefPt.End
        assert var_token is not None
        assert var_token.name == "var1"

    def test_var_decl_in_schedule_returns_token(self):
        """Test that var_decl returns a token in schedule context."""
        with experimental.build_schedule():
            token = experimental.var_decl("test", "int", op_name="my_var")

        assert token is not None
        assert isinstance(token, OperationToken)
        assert token.name == "my_var"

    def test_pulse_decl_in_schedule(self):
        """Test pulse declaration in schedule context."""
        with experimental.build_schedule() as sched:
            experimental.pulse_decl("my_pulse", square_pulse(duration="100ns", amplitude="200mV"))

        assert len(sched.items) == 1
        assert isinstance(sched.items[0].op, PulseDecl)
        assert sched.items[0].op.name == "my_pulse"
        assert isinstance(sched.items[0].op.pulse, SquarePulse)

    def test_pulse_decl_in_schedule_with_timing(self):
        """Test pulse declaration in schedule with timing parameters."""
        with experimental.build_schedule() as sched:
            # Create a reference operation
            token = experimental.play("ch1", square_pulse(duration="10us", amplitude="100mV"), op_name="pulse1")

            # Declare pulse positioned after the play
            pulse_token = experimental.pulse_decl(
                "my_pulse",
                sine_pulse(duration="5us", amplitude="50mV", frequency="5GHz"),
                ref_op=token,
                ref_pt="end",
                rel_time="2us",
                op_name="pulse_def",
            )

        assert len(sched.items) == 2
        assert isinstance(sched.items[1].op, PulseDecl)
        assert sched.items[1].op.name == "my_pulse"
        assert sched.items[1].name == "pulse_def"
        assert sched.items[1].ref_op == "pulse1"
        assert sched.items[1].ref_pt == RefPt.End
        assert pulse_token is not None
        assert pulse_token.name == "pulse_def"

    def test_pulse_decl_in_schedule_returns_token(self):
        """Test that pulse_decl returns a token in schedule context."""
        with experimental.build_schedule():
            token = experimental.pulse_decl(
                "test_pulse", square_pulse(duration="100ns", amplitude="200mV"), op_name="my_pulse_def"
            )

        assert token is not None
        assert isinstance(token, OperationToken)
        assert token.name == "my_pulse_def"


class TestDataOperations:
    """Tests for data operations in schedule context."""

    def test_store_in_schedule(self):
        """Test store operation in schedule context."""
        with experimental.build_schedule() as sched:
            experimental.var_decl("result", "complex", unit="mV")
            experimental.var_decl("stored", "complex", unit="mV")
            experimental.store("stored", "result", mode="last")

        assert len(sched.items) == 3
        assert isinstance(sched.items[2].op, Store)

    def test_store_in_schedule_with_timing(self):
        """Test store operation in schedule with timing parameters."""
        with experimental.build_schedule() as sched:
            experimental.var_decl("result", "complex", unit="mV")
            experimental.var_decl("stored", "complex", unit="mV")

            # Create a reference operation
            token = experimental.play("ch1", square_pulse(duration="10us", amplitude="100mV"), op_name="pulse1")

            # Store positioned after the pulse
            store_token = experimental.store(
                "stored", "result", mode="last", ref_op=token, ref_pt="end", rel_time="2us", op_name="store1"
            )

        assert len(sched.items) == 4
        assert isinstance(sched.items[3].op, Store)
        assert sched.items[3].name == "store1"
        assert sched.items[3].ref_op == "pulse1"
        assert sched.items[3].ref_pt == RefPt.End
        assert store_token is not None
        assert store_token.name == "store1"

    def test_store_in_schedule_returns_token(self):
        """Test that store returns a token in schedule context."""
        with experimental.build_schedule():
            experimental.var_decl("result", "complex", unit="mV")
            experimental.var_decl("stored", "complex", unit="mV")
            token = experimental.store("stored", "result", mode="last", op_name="my_store")

        assert token is not None
        assert isinstance(token, OperationToken)
        assert token.name == "my_store"

    def test_discriminate_in_schedule(self):
        """Test discriminate operation in schedule context."""
        with experimental.build_schedule() as sched:
            experimental.var_decl("raw", "complex", unit="mV")
            experimental.var_decl("state", "bool")
            experimental.discriminate(target="state", source="raw", threshold="0.5mV")

        assert len(sched.items) == 3
        assert isinstance(sched.items[2].op, Discriminate)

    def test_discriminate_in_schedule_with_timing(self):
        """Test discriminate operation in schedule with timing parameters."""
        with experimental.build_schedule() as sched:
            experimental.var_decl("raw", "complex", unit="mV")
            experimental.var_decl("state", "bool")

            # Create a measurement operation
            meas_token = experimental.measure(
                "readout",
                result_var="raw",
                duration="1us",
                amplitude="50mV",
                integration=experimental.demod_integration(),
                op_name="measurement",
            )

            # Discriminate positioned after measurement
            disc_token = experimental.discriminate(
                target="state",
                source="raw",
                threshold="0.5mV",
                ref_op=meas_token,
                ref_pt="end",
                rel_time="100ns",
                op_name="discrimination",
            )

        # Should have: 2 var_decls + play + record + discriminate = 5 items
        assert len(sched.items) == 5
        assert isinstance(sched.items[4].op, Discriminate)
        assert sched.items[4].name == "discrimination"
        assert sched.items[4].ref_op == "measurement"
        assert sched.items[4].ref_pt == RefPt.End
        assert disc_token is not None
        assert disc_token.name == "discrimination"

    def test_discriminate_in_schedule_returns_token(self):
        """Test that discriminate returns a token in schedule context."""
        with experimental.build_schedule():
            experimental.var_decl("raw", "complex", unit="mV")
            experimental.var_decl("state", "bool")
            token = experimental.discriminate(target="state", source="raw", threshold="0.5mV", op_name="my_disc")

        assert token is not None
        assert isinstance(token, OperationToken)
        assert token.name == "my_disc"


class TestExternalBlock:
    """Tests for external_block() rejection in schedule context."""

    def test_rejected_in_schedule_context(self):
        """Test that external_block raises inside a schedule context."""
        with pytest.raises(RuntimeError, match="requires a build_sequence"), experimental.build_schedule():
            external_block("q0", program="eq1.cal.cz")


class TestScheduleSpecific:
    """Tests for schedule-specific features."""

    def test_schedule_with_timing(self):
        """Test schedule with relative timing."""
        with experimental.build_schedule() as sched:
            op1 = experimental.play("ch1", square_pulse(duration="10us", amplitude="100mV"), op_name="op1")
            experimental.play(
                "ch2",
                square_pulse(duration="10us", amplitude="100mV"),
                ref_op=op1,
                ref_pt="start",
                rel_time="5us",
                op_name="op2",
            )

        assert len(sched.items) == 2

    def test_schedule_operations_return_tokens(self):
        """Test that schedule operations return tokens."""
        with experimental.build_schedule():
            token = experimental.play("ch1", square_pulse(duration="10us", amplitude="100mV"), op_name="pulse1")

        assert token is not None
        assert token.name == "pulse1"


class TestErrorHandling:
    """Tests for error handling in schedule context."""

    def test_barrier_in_schedule_raises_error(self):
        """Test that barrier in schedule raises error."""
        with pytest.raises(RuntimeError, match="not supported in schedule"), experimental.build_schedule():
            experimental.barrier("ch1")


class TestSerialization:
    """Tests for schedule serialization."""

    def test_schedule_serialization(self):
        """Test that schedules can be serialized and deserialized."""
        with experimental.build_schedule() as sched:
            experimental.play("ch1", square_pulse(duration="10us", amplitude="100mV"), op_name="op1")

        # Serialize to JSON
        json_str = sched.model_dump_json()
        assert json_str is not None

        # Deserialize
        restored = Schedule.model_validate_json(json_str)
        assert len(restored.items) == len(sched.items)


class TestNestedDecorators:
    """Tests for the @nested_schedule decorator."""

    def test_nested_schedule_decorator_in_schedule(self):
        """Test @nested_schedule decorator creates sub_schedule in schedule context."""
        from eq1_pulse.builder.experimental import nested_schedule

        @nested_schedule
        def measurement_block(drive_ch: str, readout_ch: str, result_var: str):
            """Perform readout measurement."""
            experimental.play(drive_ch, square_pulse(duration="1us", amplitude="50mV"))
            experimental.record(readout_ch, var=result_var, duration="1us", integration=full_integration())

        with experimental.build_schedule() as sched:
            experimental.var_decl("result", "complex", unit="mV")
            op1 = experimental.play("qubit", square_pulse(duration="20ns", amplitude="100mV"))
            experimental.add_block(
                measurement_block("drive0", "readout0", "result"), ref_op=op1, ref_pt="end", rel_time="100ns"
            )

        # Should have 3 items: var_decl + play + sub-schedule
        assert len(sched.items) == 3
        assert isinstance(sched.items[0].op, VariableDecl)
        assert isinstance(sched.items[1].op, Play)
        assert isinstance(sched.items[2].op, Schedule)  # sub_schedule

        # Check the sub-schedule contains 2 operations
        sub_sched = sched.items[2].op
        assert isinstance(sub_sched, Schedule)
        assert len(sub_sched.items) == 2

    def test_nested_schedule_returns_token(self):
        """Test @nested_schedule decorator returns operation token in schedule context."""
        from eq1_pulse.builder.experimental import nested_schedule

        @nested_schedule
        def gate_sequence(qubit: str):
            """Apply gate sequence."""
            experimental.play(qubit, square_pulse(duration="20ns", amplitude="100mV"))

        with experimental.build_schedule() as sched:
            token1 = experimental.add_block(gate_sequence("qubit0"), op_name="gate1")
            experimental.add_block(gate_sequence("qubit1"), ref_op=token1, ref_pt="end", rel_time="50ns")

        assert len(sched.items) == 2

    def test_nested_schedule_without_context(self):
        """Test @nested_schedule decorator raises error outside building context."""
        from eq1_pulse.builder.experimental import nested_schedule

        @nested_schedule
        def test_func(x: int) -> int:
            """Test function."""
            return x * 2

        # Should raise error when called without context
        with pytest.raises(RuntimeError, match=r"No active building context"):
            test_func(5)

    def test_nested_sequence_in_schedule_raises_error(self):
        """Test @nested_sequence raises error in schedule context."""
        from eq1_pulse.builder import nested_sequence, play

        @nested_sequence
        def sequence_func(qubit: str):
            """Function for sequences only."""
            play(qubit, square_pulse(duration="20ns", amplitude="100mV"))

        with (
            pytest.raises(RuntimeError, match=r"@nested_sequence decorator cannot be used in schedule context"),
            experimental.build_schedule(),
        ):
            sequence_func("qubit0")

    def test_nested_schedule_in_sequence_raises_error(self):
        """Test @nested_schedule raises error in sequence context."""
        from eq1_pulse.builder.experimental import nested_schedule

        @nested_schedule
        def schedule_func(qubit: str):
            """Function for schedules only."""
            experimental.play(qubit, square_pulse(duration="20ns", amplitude="100mV"))

        # ScheduleBlock can only be added in schedule contexts
        with (
            pytest.raises(RuntimeError, match=r"add_block\(\) can only be used within a build_schedule\(\) context"),
            build_sequence(),
        ):
            block = schedule_func("qubit0")
            experimental.add_block(block)

    def test_unconsumed_schedule_block_raises_error(self):
        """Test that unconsumed ScheduleBlock raises error on context close."""
        from eq1_pulse.builder.experimental import nested_schedule

        @nested_schedule
        def test_block(qubit: str):
            """Test block."""
            experimental.play(qubit, square_pulse(duration="20ns", amplitude="100mV"))

        # Should raise error when block is created but not added
        with pytest.raises(
            RuntimeError,
            match=r"Schedule context closed with 1 unconsumed ScheduleBlock\(s\).*add_block\(\)",
        ):
            with experimental.build_schedule():
                test_block("qubit0")  # Created but not added with add_block()

    def test_multiple_unconsumed_blocks_raises_error(self):
        """Test that multiple unconsumed ScheduleBlocks are detected."""
        from eq1_pulse.builder.experimental import nested_schedule

        @nested_schedule
        def test_block(qubit: str):
            """Test block."""
            experimental.play(qubit, square_pulse(duration="20ns", amplitude="100mV"))

        # Should report count of unconsumed blocks
        with pytest.raises(
            RuntimeError,
            match=r"Schedule context closed with 2 unconsumed ScheduleBlock\(s\)",
        ):
            with experimental.build_schedule():
                test_block("qubit0")
                test_block("qubit1")

    @pytest.mark.parametrize(
        "open_control_flow",
        [
            lambda: experimental.repeat(2),
            lambda: experimental.for_("sweep", range(2)),
            lambda: experimental.if_("flag"),
        ],
        ids=["repeat", "for_", "if_"],
    )
    def test_unconsumed_schedule_block_raises_error_inside_control_flow(self, open_control_flow):
        """Test that a block left unconsumed inside repeat()/for_()/if_() is still detected."""
        from eq1_pulse.builder.experimental import nested_schedule

        @nested_schedule
        def test_block(qubit: str):
            """Test block."""
            experimental.play(qubit, square_pulse(duration="20ns", amplitude="100mV"))

        with (
            pytest.raises(RuntimeError, match=r"unconsumed ScheduleBlock\(s\).*add_block\(\)"),
            experimental.build_schedule(),
        ):
            experimental.var_decl("sweep", "int")
            experimental.var_decl("flag", "bool")
            with open_control_flow():
                test_block("qubit0")  # Created but not added with add_block()
                # Neither added with add_block()
