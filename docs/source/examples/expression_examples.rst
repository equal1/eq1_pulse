Expression Examples
====================

.. note::

   These examples are provided for **illustration purposes only** and may not represent realistic experimental parameters or physical hardware configurations. They demonstrate the API usage patterns rather than actual quantum device specifications.

Expressions let a sequence compute a value from variables and external constants instead of
writing a fixed literal, using ordinary Python operators via :func:`~eq1_pulse.builder.expr`. See
:doc:`/user_guide/builder_guide` for the conceptual introduction (why ``expr()`` is required, what
is and is not evaluated) -- this page collects worked examples and the wire-format reference.

Arithmetic Expressions
-----------------------

Combine a variable and an external constant, or scale a literal quantity by a parameter:

.. code-block:: python

    from eq1_pulse.builder import *
    from eq1_pulse.models import Amplitude

    with build_sequence() as seq:
        extern_decl("q0.f01", "float", unit="GHz")
        param_decl("detuning", "float", unit="MHz", default=0.0)
        var_decl("scale", "float")

        # External constant plus a parameter
        set_frequency("q0_drive", expr(ext("q0.f01")) + expr(var("detuning")))

        # A variable scaling a literal quantity
        play("q0_drive", square_pulse(duration="25ns", amplitude=expr(var("scale")) * Amplitude("80mV")))

Comparison and Conditionals
-----------------------------

``<``, ``<=``, ``>``, ``>=`` build a predicate directly; ``==``/``!=`` are not overloaded (see
:doc:`/user_guide/builder_guide`), so equality and inequality go through ``.eq()``/``.ne()``:

.. code-block:: python

    from eq1_pulse.builder import *

    with build_sequence() as seq:
        var_decl("amplitude", "float", unit="mV")
        var_decl("state", "int")

        with if_(expr(var("amplitude")) > 50):
            play("readout", square_pulse(duration="1us", amplitude="30mV"))

        with if_(expr(var("state")).eq(1)):
            play("qubit", square_pulse(duration="50ns", amplitude="80mV"))

Logical Connectives
---------------------

``and``, ``or`` and ``not`` cannot be overloaded in Python, so combining predicates uses
``.and_()``, ``.or_()`` and ``.not_()`` instead:

.. code-block:: python

    from eq1_pulse.builder import *

    with build_sequence() as seq:
        var_decl("armed", "bool")
        var_decl("amplitude", "float", unit="mV")

        condition = expr(var("armed")).and_(expr(var("amplitude")) > 50)
        with if_(condition):
            play("readout", square_pulse(duration="1us", amplitude="30mV"))

        with if_(expr(var("armed")).not_()):
            play("readout", square_pulse(duration="200ns", amplitude="10mV"))

Function Calls
----------------

``abs(expr)`` is the one function with its own operator sugar, via Python's own ``abs()``. Every
other :data:`~eq1_pulse.models.expressions.ExpressionFunction` -- including ``abs`` again, if you
prefer spelling it out -- goes through the single free function
``call_expr_(function, *operands)``. It is a free function rather than an ``Expr`` method: a
function call has no operand that reads naturally as "self" the way ``+``/``-``/... prefer their
left one, so ``call_expr_("min", a, b, c)`` treats its operands symmetrically. There is no free
``min()``/``max()``, to avoid shadowing the Python builtins under ``from eq1_pulse.builder import
*``. ``CallExpr`` validates the resulting argument count against *function*'s arity --
``"min"``/``"max"`` need at least 2, every other function exactly 1:

.. code-block:: python

    from eq1_pulse.builder import *

    with build_sequence() as seq:
        var_decl("a", "float")
        var_decl("b", "float")
        var_decl("power", "float")

        fastest = call_expr_("min", var("a"), var("b"), 0)
        scaled = call_expr_("sqrt", var("power")) * 2

Storing a Computed Value
--------------------------

An ``Expr`` built with ``expr()``/``call_expr_()`` is not itself a variable -- it is recorded at the
site that uses it. ``assign(target, value)`` writes an expression's value into an already-declared
variable, so it can be computed once and reused by name instead of rebuilding the same tree at
every use site:

.. code-block:: python

    from eq1_pulse.builder import *

    with build_sequence() as seq:
        var_decl("scale", "float")
        var_decl("scale_clamped", "float")

        assign("scale_clamped", call_expr_("min", var("scale"), 1.0))

Wire Format Reference
------------------------

Every expression node serializes as a JSON array, ``[<tag>, <operand>, ...]``, not an object. For
the six operator nodes ``<tag>`` is the operator itself; ``LiteralExpr`` and ``SymbolExpr`` have no
operator, so ``<tag>`` there is that field's own name instead:

.. list-table::
   :header-rows: 1
   :widths: 20 20 60

   * - Node
     - Wire tag
     - Example
   * - :class:`~eq1_pulse.models.expressions.LiteralExpr`
     - ``value``
     - ``["value", {"mV": 80}]``
   * - :class:`~eq1_pulse.models.expressions.SymbolExpr`
     - ``symbol``
     - ``["symbol", {"var": "scale"}]``
   * - :class:`~eq1_pulse.models.expressions.UnaryExpr`
     - ``-``
     - ``["-", ["...", "..."]]``
   * - :class:`~eq1_pulse.models.expressions.BinaryExpr`
     - ``+``, ``-``, ``*``, ``/``, ``%``
     - ``["*", ["...", "..."], ["...", "..."]]``
   * - :class:`~eq1_pulse.models.expressions.CompareExpr`
     - ``<``, ``<=``, ``>``, ``>=``, ``==``, ``!=``
     - ``["<", ["...", "..."], ["...", "..."]]``
   * - :class:`~eq1_pulse.models.expressions.NotExpr`
     - ``not``
     - ``["not", ["...", "..."]]``
   * - :class:`~eq1_pulse.models.expressions.LogicalExpr`
     - ``and``, ``or``
     - ``["and", ["...", "..."], ["...", "..."]]``
   * - :class:`~eq1_pulse.models.expressions.CallExpr`
     - the function name
     - ``["sqrt", ["...", "..."]]``, or ``["min", op, op, ...]`` for a variadic function

No discriminator field is needed: the array's first element (and, for ``"-"``, the array's
length -- 2 for negation, 3 for subtraction) is itself the discriminator, both for pydantic's
validator and for reading a document by hand.

Expression Depth Limit
--------------------------

:data:`~eq1_pulse.models.expressions.MAX_EXPRESSION_DEPTH` (32) caps how deeply an expression tree
may nest. The cap exists to protect the *serializer*, not the validator -- pydantic-core already
has its own recursion guard while validating, but past its recursion limit
``model_dump_json()`` degrades into warnings and wrong output rather than an error, so a tree that
could not be serialized correctly is rejected on the way in instead. Hand-written expressions do
not come close to this limit; it matters mainly for expressions assembled programmatically (e.g.
generated in a loop).

Complete Example
------------------

A full Ramsey interferometry sequence using expressions throughout -- for the frequency offset, the
pulse amplitude, and the swept delay:

.. literalinclude:: ../../../examples/expression_ramsey.py
   :language: python

Running the Example
-----------------------

Execute the complete example script:

.. code-block:: bash

    python examples/expression_ramsey.py

See Also
--------

* :doc:`/user_guide/builder_guide` - Expressions section, with the full operator/function reference and authoring-form details
* :doc:`/autoapi/eq1_pulse/models/expressions/index` - Expression node model API reference
* :doc:`/autoapi/eq1_pulse/builder/index` - Builder API reference, including :func:`~eq1_pulse.builder.expr`
