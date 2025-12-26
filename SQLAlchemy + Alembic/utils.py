import subprocess
from tempfile import NamedTemporaryFile
from typing import Any, overload

from sqlalchemy import inspect
from sqlalchemy.orm import DeclarativeBase


def ruff_format(
    code: str,
    *,
    ruff_command: str = "ruff",
    isort: bool = True,
    line_length: int | None = None,
) -> str:
    run_options: dict[str, Any] = {"text": True, "capture_output": True, "check": True}

    # isort
    if isort:
        with NamedTemporaryFile("w+", suffix=".py") as f:
            f.write(code)
            f.flush()
            cmd = [ruff_command, "check", "--isolated", "--fix"]
            cmd += ["--select", "I"]  # isort
            subprocess.run(cmd + [f.name], **run_options)
            f.seek(0)
            code = f.read()

    # format
    cmd = [ruff_command, "format", "--isolated"]
    if line_length:
        cmd += ["--line-length", str(line_length)]
    code = subprocess.run(cmd + ["-"], input=code, **run_options).stdout

    return code


@overload
def sa_to_dict(obj: DeclarativeBase) -> dict[str, Any]: ...


@overload
def sa_to_dict(obj: None) -> None: ...


def sa_to_dict(obj: DeclarativeBase | None) -> dict[str, Any] | None:
    """SQLAlchemy オブジェクトを dict に変換する"""
    if obj is None:
        return None

    info = inspect(obj)
    data: dict[str, Any] = {}

    for col in info.mapper.column_attrs:
        data[col.key] = getattr(obj, col.key)

    for rel in info.mapper.relationships:
        if rel.key in info.unloaded:
            continue
        value = getattr(obj, rel.key)
        if value is None:
            data[rel.key] = None
        elif rel.uselist:
            data[rel.key] = [sa_to_dict(x) for x in value]
        else:
            data[rel.key] = sa_to_dict(value)

    return data
