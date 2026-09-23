"""Install or remove only JevBrow's owned MCP block in Codex config."""

import argparse
import json
import os
import shutil
import stat
import tempfile
from pathlib import Path

BEGIN = "# BEGIN JEVBROW MCP"
END = "# END JEVBROW MCP"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
BODY = (
    '[mcp_servers.jevbrow]\ncommand = "uv"\n'
    f'args = ["run", "--directory", {json.dumps(str(PROJECT_ROOT))}, "jevbrow"]\n'
    'startup_timeout_sec = 30\n\n[mcp_servers.jevbrow.env]\nBU_CDP_URL = "http://127.0.0.1:9222"'
)
UNMARKED = "\n" + BODY + "\n"
BASELINE_SUFFIX = ".jevbrow.baseline"
SNAPSHOT_SUFFIX = ".jevbrow.installed"


def atomic_write(path: Path, data: bytes, mode: int) -> None:
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def install(path: Path) -> None:
    current = path.read_bytes()
    mode = stat.S_IMODE(path.stat().st_mode)
    baseline = Path(str(path) + BASELINE_SUFFIX)
    snapshot = Path(str(path) + SNAPSHOT_SUFFIX)
    if BEGIN in current.decode():
        return
    if UNMARKED.encode() not in current:
        if "[mcp_servers.jevbrow]" in current.decode():
            raise RuntimeError(
                "A JevBrow config entry exists but is not the expected block; preserve and inspect it manually."
            )
        before = current
        separator = b"" if not before or before.endswith(b"\n\n") else b"\n"
        updated = before + separator + BEGIN.encode() + b"\n" + BODY.encode() + b"\n" + END.encode() + b"\n"
        baseline_bytes = before
    else:
        baseline_bytes = current.replace(UNMARKED.encode(), b"\n", 1)
        updated = current.replace(
            UNMARKED.encode(), b"\n" + BEGIN.encode() + b"\n" + BODY.encode() + b"\n" + END.encode() + b"\n", 1
        )
    if not baseline.exists():
        atomic_write(baseline, baseline_bytes, mode)
    atomic_write(path, updated, mode)
    if not snapshot.exists():
        shutil.copy2(path, snapshot)


def uninstall(path: Path) -> None:
    baseline = Path(str(path) + BASELINE_SUFFIX)
    snapshot = Path(str(path) + SNAPSHOT_SUFFIX)
    if not path.exists():
        raise RuntimeError("Codex config is missing; kept the baseline for recovery.")
    current = path.read_bytes()
    mode = stat.S_IMODE(path.stat().st_mode)
    if snapshot.exists() and baseline.exists() and current == snapshot.read_bytes():
        atomic_write(path, baseline.read_bytes(), mode)
    else:
        text = current.decode()
        if (BEGIN in text) != (END in text):
            raise RuntimeError("JevBrow config markers are incomplete; kept recovery files.")
        if BEGIN in text:
            start = text.index(BEGIN)
            end = text.index(END, start) + len(END)
            if end < len(text) and text[end] == "\n":
                end += 1
            if start and text[start - 1] == "\n":
                start -= 1
            text = text[:start] + text[end:]
            atomic_write(path, text.encode(), mode)
    baseline.unlink(missing_ok=True)
    snapshot.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "uninstall"))
    parser.add_argument(
        "--config", type=Path, default=Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser() / "config.toml"
    )
    args = parser.parse_args()
    (install if args.action == "install" else uninstall)(args.config)
    print(f"JevBrow Codex config {args.action} complete: {args.config}")


if __name__ == "__main__":
    main()
