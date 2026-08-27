# Decision: array wire format for expressions -- abandoned

**Status:** abandoned -- branch `hp-peti/s-expressions` parked, not merged
**Date:** 2026-08-22

## What was explored

This branch reworked `Expression`'s wire form from an object keyed on the operator/payload field
(e.g. `{"binary_op": "+", "left": ..., "right": ...}`) to a JSON array, S-expression style:
`["+", left, right]`. `ExprBase` implemented the encoding generically over each node's declared
fields (`_from_wire` / `_to_wire`), the callable `Discriminator` was changed to key off the array's
first element (with `"-"` disambiguated between negation and subtraction by array length), and
`ExprBase.__get_pydantic_json_schema__` was rewritten to describe the array shape -- walking the
node's own in-progress core schema rather than building a fresh `TypeAdapter`, which recurses
indefinitely on `Expression`'s self-reference.

The implementation reached a working state: full test suite green, `mypy`/`pyright`/`ruff` clean,
and the generated OpenAPI schema verified against real serialized trees with `jsonschema`.

## Why abandoned

Decided against on readability/ambiguity grounds: a bare JSON array with no field names makes an
expression node's shape illegible without cross-referencing which position means what for which
operator, and introduces exactly the kind of positional ambiguity the object-keyed form (landed in
#13, "Operator-keyed expression serialization") was written to avoid -- e.g. `"-"` needing
arity-based disambiguation between `UnaryExpr` and `BinaryExpr`, and a plain numeric list already
colliding with `ExternalParamValue`'s `complex` `(real, imag)` representation. The tradeoff was not
worth it.

## Disposition

The branch is parked as-is, not reverted and not merged. `main` keeps the object-keyed wire format
from #13.
