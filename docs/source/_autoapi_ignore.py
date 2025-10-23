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


_autoapi_skip: dict[str, dict[str, Any]] = {
    "data": {
        # "eq1x.framework.sweep.typedefs.ConfigValue",
        # "eq1x.framework.sweep.typedefs.Parameter_Config",
        # "eq1x.framework.sweep.typedefs.Multi_Parameter_Config",
        # "eq1x.framework.sweep.typedefs.Scalar",
        # "eq1x.eq1_magnet_control_driver._dirs.EXPERIMENTS_DIR",
    },
    "function": {
        # "eq1x.yaml.get_config_item",
    },
    "class": {
        # "eq1x.framework.sweep.typedefs.MultiIndex",
    },
}

autoapi_skip_file = open("./.autoapi-skip-member.log", mode="w", buffering=1)  # noqa: SIM115

if TYPE_CHECKING:
    import sphinx.application


def autoapi_skip_member(app: sphinx.application.Sphinx, what, name: str, obj, skip: bool, options: list[str]) -> bool:
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

    return skip
