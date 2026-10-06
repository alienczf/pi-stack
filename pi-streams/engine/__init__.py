from pathlib import Path


class StreamsError(RuntimeError):
    pass


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]
