"""Deprecated shim for the relocated schedule module.

.. deprecated::

    ``eq1_pulse.models.schedule`` has moved to
    :mod:`eq1_pulse.models.experimental.schedule` and is no longer part of the
    supported model set.
"""

import warnings
from typing import TYPE_CHECKING

from .experimental.schedule import *  # noqa: F403
from .experimental.schedule import __all__ as __all__

if TYPE_CHECKING:
    from .experimental.schedule import OpScheduleDict as OpScheduleDict
    from .experimental.schedule import RefPtLike as RefPtLike
    from .experimental.schedule import RelTimeLike as RelTimeLike

warnings.warn(
    "eq1_pulse.models.schedule has moved to eq1_pulse.models.experimental.schedule "
    "and is no longer part of the supported model set.",
    DeprecationWarning,
    stacklevel=2,
)
