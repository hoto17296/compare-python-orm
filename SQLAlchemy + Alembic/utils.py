import subprocess
from tempfile import NamedTemporaryFile
from typing import Any


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
