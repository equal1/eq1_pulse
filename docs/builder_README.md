# Builder Interface for Equal1 Pulse

A fluent builder API for constructing pulse sequences and schedules with an intuitive, pythonic interface.

## Overview

The builder interface provides a high-level API for creating pulse programs through:

- **Global Context**: Enter a building context (sequence or schedule) to start constructing
- **Context Managers**: Use Python's `with` statement for control flow structures
- **Function Calls**: Add operations like playing pulses, waiting, and recording
- **Token-Based References**: Reference scheduled operations for relative positioning
- **Shorthand Functions**: Convenient helpers for common pulse types
- **Measure Operation**: Simplified simultaneous play + record

## Quick Start

```python
from eq1_pulse.builder import build

# Create a simple sequence
with build.sequence() as seq:
    build.play("drive_ch", build.square(duration={"us": 10}, amplitude={"mV": 100}))
    build.wait("drive_ch", duration={"us": 5})
    build.play("drive_ch", build.sine(duration={"us": 20}, amplitude={"mV": 50}, frequency={"GHz": 5}))
```

## Key Concepts

### Building Contexts

There are two main building contexts:

1. **Sequence** - Operations execute in order (earliest possible start time)
2. **Schedule** - Operations have explicit timing relationships

```python
# Sequence context
with build.sequence() as seq:
    build.play("ch1", pulse)
    build.wait("ch1", duration={"us": 10})

# Schedule context
with build.schedule() as sched:
    op1 = build.play("ch1", pulse)
    op2 = build.play("ch2", pulse, ref_op=op1, ref_pt="end", rel_time={"us": 5})
```

### Operation Tokens

In schedules, operations return tokens that can be used for relative positioning:

```python
with build.schedule() as sched:
    # First operation
    first = build.play("ch1", pulse, name="first_pulse")

    # Second operation starts 10us after first ends
    second = build.play(
        "ch2",
        pulse,
        ref_op=first,  # Reference the token
        ref_pt="end",   # Reference point on first operation
        ref_pt_new="start",  # Reference point on new operation
        rel_time={"us": 10}  # Relative time offset
    )
```

### Control Flow

Control flow uses context managers:

```python
with build.sequence():
    # Repetition
    with build.repeat(10):
        build.play("ch1", pulse)

    # Iteration
    with build.for_loop("freq", range(4000, 6000, 100)):
        build.set_frequency("ch1", build.var("freq"))
        build.play("ch1", pulse)

    # Conditional
    build.measure("drive", "readout", "result", duration={"us": 1}, amplitude={"mV": 50})
    with build.if_condition("result"):
        build.play("ch1", correction_pulse)
```

## API Reference

### Context Managers

#### `build.sequence()`
Create an operation sequence context.

```python
with build.sequence() as seq:
    # Add operations
    pass
```

#### `build.schedule()`
Create a schedule context with explicit timing.

```python
with build.schedule() as sched:
    # Add operations with timing
    pass
```

#### `build.repeat(count)`
Create a repetition block.

**Parameters:**
- `count` (int): Number of repetitions

```python
with build.repeat(10):
    # Operations to repeat
    pass
```

#### `build.for_loop(var, items)`
Create an iteration (for loop).

**Parameters:**
- `var` (str | VariableRef): Loop variable name(s)
- `items`: Range, LinSpace, or iterable to iterate over

```python
with build.for_loop("i", range(0, 100, 10)):
    # Operations using variable "i"
    pass
```

#### `build.if_condition(var)`
Create a conditional block.

**Parameters:**
- `var` (str | VariableRef): Condition variable name

```python
with build.if_condition("result"):
    # Conditional operations
    pass
```

### Pulse Creation

#### `build.square(duration, amplitude, rise_time=None, fall_time=None)`
Create a square pulse.

```python
pulse = build.square(
    duration={"us": 10},
    amplitude={"mV": 100},
    rise_time={"ns": 5},
    fall_time={"ns": 5}
)
```

#### `build.sine(duration, amplitude, frequency, to_frequency=None)`
Create a sine pulse (optionally with chirp).

```python
pulse = build.sine(
    duration={"us": 20},
    amplitude={"mV": 50},
    frequency={"GHz": 5},
    to_frequency={"GHz": 6}  # Optional chirp
)
```

#### `build.external_pulse(function, duration, amplitude, params=None)`
Reference an externally defined pulse.

```python
pulse = build.external_pulse(
    "my_lib.gaussian",
    duration={"us": 10},
    amplitude={"mV": 100},
    params={"sigma": 2.0}
)
```

#### `build.arbitrary_pulse(samples, duration, amplitude, ...)`
Create a pulse from arbitrary samples.

```python
pulse = build.arbitrary_pulse(
    [0, 0.5, 1, 0.5, 0],
    duration={"us": 10},
    amplitude={"mV": 100}
)
```

### Reference Helpers

#### `build.var(name)`
Create a variable reference.

```python
freq_var = build.var("frequency")
```

#### `build.channel(name)`
Create a channel reference.

```python
ch = build.channel("qubit_1")
```

#### `build.pulse_ref(name)`
Create a pulse reference.

```python
p = build.pulse_ref("pi_pulse")
```

### Channel Operations

#### `build.play(channel, pulse, **kwargs)`
Play a pulse on a channel.

**Parameters:**
- `channel`: Channel name or reference
- `pulse`: Pulse to play
- `scale_amp`: Optional amplitude scaling
- `cond`: Optional condition variable
- `**kwargs`: Scheduling parameters (for schedules)

**Returns:** Operation token (in schedule) or None (in sequence)

```python
# In sequence
build.play("ch1", pulse)

# In schedule with positioning
op = build.play("ch1", pulse, ref_op=prev_op, ref_pt="end")
```

#### `build.wait(*channels, duration, **kwargs)`
Add wait on channel(s).

```python
build.wait("ch1", duration={"us": 5})
build.wait("ch1", "ch2", duration={"us": 10})
```

#### `build.barrier(*channels, **kwargs)`
Synchronize channels.

```python
build.barrier("ch1", "ch2", "ch3")
```

#### `build.set_frequency(channel, frequency, **kwargs)`
Set channel frequency.

```python
build.set_frequency("qubit", {"GHz": 5})
```

#### `build.shift_frequency(channel, frequency, **kwargs)`
Shift channel frequency.

```python
build.shift_frequency("qubit", {"MHz": 100})
```

#### `build.set_phase(channel, phase, **kwargs)`
Set channel phase.

```python
build.set_phase("qubit", {"deg": 90})
```

#### `build.shift_phase(channel, phase, **kwargs)`
Shift channel phase.

```python
build.shift_phase("qubit", {"deg": 45})
```

#### `build.record(channel, var, duration, integration="full", **kwargs)`
Record (acquire) data from channel.

**Parameters:**
- `channel`: Channel to record from
- `var`: Variable to store result
- `duration`: Recording duration
- `integration`: Integration type ("full" or "demod")
- `phase`: Phase for demod integration
- `scale_cos`, `scale_sin`: Scaling for demod
- `**kwargs`: Scheduling parameters

```python
build.record(
    "readout",
    "result",
    duration={"us": 1},
    integration="demod",
    phase={"deg": 90}
)
```

#### `build.measure(drive_channel, readout_channel, result_var, duration, amplitude, **kwargs)`
Perform measurement (simultaneous play + record).

**Parameters:**
- `drive_channel`: Channel to play measurement pulse
- `readout_channel`: Channel to record from
- `result_var`: Variable for measurement result
- `duration`: Measurement duration
- `amplitude`: Measurement pulse amplitude
- `integration`: Integration type
- `phase`, `scale_cos`, `scale_sin`: Demod parameters
- `**kwargs`: Scheduling parameters

```python
build.measure(
    "qubit",
    "readout",
    "result",
    duration={"us": 1},
    amplitude={"mV": 50},
    integration="demod"
)
```

## Complete Examples

### Basic Sequence

```python
from eq1_pulse.builder import build

with build.sequence() as seq:
    # Prepare
    build.set_frequency("qubit", {"GHz": 5})
    build.set_phase("qubit", {"deg": 0})

    # Drive
    build.play("qubit", build.square(duration={"ns": 50}, amplitude={"mV": 100}))

    # Measure
    build.measure("qubit", "readout", "result", duration={"us": 1}, amplitude={"mV": 50})

# Use the sequence
print(seq.model_dump_json(indent=2))
```

### Schedule with Positioning

```python
with build.schedule() as sched:
    # Pulse on channel 1
    op1 = build.play(
        "ch1",
        build.square(duration={"us": 10}, amplitude={"mV": 100}),
        name="drive_pulse"
    )

    # Pulse on channel 2, starting when ch1 ends
    op2 = build.play(
        "ch2",
        build.square(duration={"us": 10}, amplitude={"mV": 50}),
        ref_op=op1,
        ref_pt="end",
        rel_time=0
    )

    # Simultaneous readout
    build.wait(
        "readout",
        duration={"us": 10},
        ref_op=op2,
        ref_pt="start",
        ref_pt_new="start"
    )
```

### Parameterized Sweep

```python
with build.sequence() as seq:
    # Frequency sweep
    with build.for_loop("freq", range(4000, 6000, 100)):
        build.set_frequency("qubit", build.var("freq"))
        build.play("qubit", build.square(duration={"ns": 100}, amplitude={"mV": 50}))
        build.measure("qubit", "readout", "result", duration={"us": 1}, amplitude={"mV": 50})
        build.wait("qubit", "readout", duration={"us": 10})
```

### Active Reset

```python
with build.sequence() as seq:
    # Measure
    build.measure("qubit", "readout", "state", duration={"us": 1}, amplitude={"mV": 50})

    # Reset if in excited state
    with build.if_condition("state"):
        build.play("qubit", build.square(duration={"us": 1}, amplitude={"mV": 200}))

    # Wait for reset
    build.wait("qubit", duration={"us": 5})
```

## Tips and Best Practices

1. **Use Context Managers**: Always use `with` statements for building contexts
2. **Name Important Operations**: In schedules, name key operations for easier debugging
3. **Reference Tokens**: Store operation tokens when you need to reference them later
4. **Type Safety**: Use proper type constructors (Duration, Amplitude, etc.) for production code
5. **Nested Control Flow**: Control flow can be nested arbitrarily deep
6. **Schedule vs Sequence**: Use sequences for simple programs, schedules for complex timing

## See Also

- [Model Documentation](../docs/) - Details on the underlying models
- [Examples](../examples/builder_example.py) - Comprehensive examples
- [API Reference](../docs/api/) - Complete API documentation
