"""Example demonstrating the step pulse, digital trigger pulse, and wait_for_trigger.

Shows the three additions from issue #5:

- ``step_pulse``: moves a channel's DC bias to a new operating point and leaves it there.
- ``trigger_pulse`` + ``wait_for_trigger``: one channel signals external instrumentation with a
  digital pulse, another channel blocks until it sees that trigger go high.
"""

from eq1_pulse.builder import (
    build_sequence,
    play,
    square_pulse,
    step_pulse,
    trigger_pulse,
    wait_for_trigger,
)


def example_step_and_trigger():
    """Example combining a step pulse with a trigger pulse / wait_for_trigger pair."""
    print("\n=== Step Pulse and Trigger ===")

    with build_sequence() as seq:
        # Move the DC bias to a new operating point and leave it there.
        play("plunger", step_pulse(duration="1us", amplitude="150mV"))

        # Tell external instrumentation to start, then block until it acknowledges.
        play("trig_out", trigger_pulse(duration="100ns"))
        wait_for_trigger("trig_in")

        play("q0_drive", square_pulse(duration="25ns", amplitude="80mV"))

    print(f"Sequence has {len(seq.items)} items")
    print("Structure:")
    print("  1. Step pulse on 'plunger' -- new base level persists past the pulse")
    print("  2. Trigger pulse on 'trig_out' -- signals external instrumentation")
    print("  3. wait_for_trigger on 'trig_in' -- blocks until the trigger line goes high")
    print("  4. Square pulse on 'q0_drive'")

    return seq


if __name__ == "__main__":
    example_step_and_trigger()

    print("\n✓ Step pulse and trigger example completed successfully!")
