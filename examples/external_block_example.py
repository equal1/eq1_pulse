"""Example demonstrating external_block() for opaque, externally defined operations.

An :class:`~eq1_pulse.models.ExternalBlock` reserves a set of channels for the duration of an
externally defined program -- a calibrated gate, a vendor routine, a hand-written OpenPulse
``defcal`` -- without describing its contents in this IR. See the class docstring for the full
reservation and timing semantics.
"""

from eq1_pulse.builder import build_sequence, external_block, var, var_decl


def example_named_channel_roles():
    """Reference an external two-qubit gate with named channel roles and input parameters."""
    print("\n=== Named Channel Roles ===")

    with build_sequence() as seq:
        # The referenced program distinguishes drive from readout, so roles are named.
        external_block(
            program="eq1.cal.measure",
            channels={"drive": "q0", "readout": "q0_ro"},
            params={"amp": "50mV"},
        )

    print(f"Sequence has {len(seq.items)} item(s)")
    return seq


def example_positional_channels():
    """Reference an external routine where the channel roles do not matter."""
    print("\n=== Positional Channels ===")

    with build_sequence() as seq:
        # Roles do not matter here, so channels are passed positionally.
        external_block("q0", "q1", program="eq1.cal.cz")

    print(f"Sequence has {len(seq.items)} item(s)")
    return seq


def example_timed_vs_flex():
    """Contrast a hard duration constraint with a flex (natural-duration) block."""
    print("\n=== Timed vs. Flex Duration ===")

    with build_sequence() as seq:
        # Timed: the referenced program must fit within 500ns.
        external_block("q0", program="eq1.cal.x90", duration="500ns")

        # Flex: duration is whatever eq1.cal.x90 naturally takes.
        external_block("q0", program="eq1.cal.x90")

    print(f"Sequence has {len(seq.items)} item(s)")
    return seq


def example_pure_reservation():
    """Reserve channels for an externally driven interval with no referenced program."""
    print("\n=== Pure Reservation ===")

    with build_sequence() as seq:
        # program=None with a duration: "this channel is busy for this long."
        external_block("q1", duration="1us")

    print(f"Sequence has {len(seq.items)} item(s)")
    return seq


def example_results_binding():
    """Bind an external program's output to a declared variable."""
    print("\n=== Results Binding ===")

    with build_sequence() as seq:
        var_decl("iq", "complex", unit="mV")

        external_block(
            program="eq1.cal.measure",
            channels={"drive": "q0", "readout": "q0_ro"},
            results={"iq": var("iq")},
        )

    print(f"Sequence has {len(seq.items)} item(s)")
    return seq


if __name__ == "__main__":
    example_named_channel_roles()
    example_positional_channels()
    example_timed_vs_flex()
    example_pure_reservation()
    example_results_binding()

    print("\n✓ All external_block examples completed successfully!")
