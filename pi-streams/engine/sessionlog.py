from __future__ import annotations

import json
import os
from pathlib import Path
from typing import BinaryIO

from engine import StreamsError

CHUNK = 65536


def last_assistant(path: Path) -> dict[str, object] | None:
    try:
        with open(path, "rb") as handle:
            return _scan_back(handle)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise StreamsError(f"could not read {path}: {exc}") from exc


def _scan_back(handle: BinaryIO) -> dict[str, object] | None:
    end = handle.seek(0, os.SEEK_END)
    pieces: list[bytes] = []
    while end > 0:
        start = max(0, end - CHUNK)
        handle.seek(start)
        data = handle.read(end - start)
        end = start
        stop = len(data)
        cut = data.rfind(b"\n", 0, stop)
        while cut >= 0:
            pieces.append(data[cut + 1 : stop])
            message = _assistant(b"".join(reversed(pieces)))
            if message is not None:
                return message
            pieces = []
            stop = cut
            cut = data.rfind(b"\n", 0, stop)
        pieces.append(data[:stop])
    return _assistant(b"".join(reversed(pieces)))


def _assistant(line: bytes) -> dict[str, object] | None:
    # A line pi is still appending does not parse yet; the one before it counts.
    try:
        entry = json.loads(line)
    except ValueError:
        return None
    if not isinstance(entry, dict) or entry.get("type") != "message":
        return None
    message = entry.get("message")
    if isinstance(message, dict) and message.get("role") == "assistant":
        return message
    return None
