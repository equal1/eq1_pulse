from importlib.metadata import PackageNotFoundError  # noqa: D104
from importlib.metadata import version as _get_version

try:
    __version__ = _get_version(__name__)
except PackageNotFoundError:
    # Package is not installed, set a default version
    __version__ = "0.0.0"
finally:
    del _get_version, PackageNotFoundError
