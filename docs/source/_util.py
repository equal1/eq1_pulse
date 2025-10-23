import os


def to_bool(s: str | int | bool | None, default: bool = False) -> bool:
    if s is None:
        return default
    if isinstance(s, bool):
        return s
    if isinstance(s, int):
        return bool(s)
    assert isinstance(s, str)
    s = s.strip().lower()
    if not len(s):
        return default
    if s in {"1", "y", "yes", "true", "on"}:
        return True
    if s in {"0", "n", "no", "false", "off"}:
        return False
    try:
        return bool(int(s))
    except Exception:
        return default


def git_version(*, long: bool = False) -> str:
    args = ["git", "describe"]

    if long:
        args += ["--long"]

    args += ["--tags", "--dirty", "--always"]

    cmd = " ".join(args)

    return os.popen(cmd).read().strip().removeprefix("v")
