# The following is a list of problematic files
# which prevent autoapi from processing the source tree
# the reason is always something like
#
# Handler <function run_autoapi at ...> for event 'builder-inited' threw an exception
# (exception: Relative import with too many levels (...) for module '...')
from __future__ import annotations

from typing import TYPE_CHECKING, Any

_SKIP_FILES_WITH_RELATIVE_IMPORTS = False

autoapi_ignore: list[str] = [
    # "*/lib-src/eq1x/tno/drivers/qblox/_qrm_lockin.orig.py",
]


_autoapi_skip: dict[str, set[str] | dict[str, Any]] = {
    "data": {},
    "function": {},
    "class": {},
    "package": {"eq1_pulse.models"},
}

autoapi_skip_file = open("./.autoapi-skip-member.log", mode="w", buffering=1)  # noqa: SIM115

if TYPE_CHECKING:
    import sphinx.application


def autoapi_skip_member(
    app: sphinx.application.Sphinx,
    what,
    name: str,
    obj,
    skip: bool,
    options: list[str],
) -> bool | None:
    # print(f"{app=!r}, {what=!r} {name=!r} {obj=!r} {skip=!r}", file=autoapi_skip_file)
    print(f"{what=!r} {name=!r} {obj=!r} {skip=!r}", file=autoapi_skip_file)
    if not skip:
        if (what in _autoapi_skip and name in _autoapi_skip[what]) or (
            "*" in _autoapi_skip and name in _autoapi_skip["*"]
        ):
            skip = True

        if skip:
            print(f">>>> skipping: {what} {name}", file=autoapi_skip_file)
            return (skip := True)

    if isinstance(docstring := obj.docstring, str):
        if ":meta public:" in docstring:
            print(f">>>> :meta public: {what} {name}", file=autoapi_skip_file)
            return (skip := False)
        elif ":meta private:" in docstring:
            print(f">>>> :meta private: {what} {name}", file=autoapi_skip_file)
            return (skip := ("private-members" in options))

    return None
