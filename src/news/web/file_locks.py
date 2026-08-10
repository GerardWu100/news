"""Hold process-shared locks while reading or replacing state files.

Two processes can serve this application at once: uvicorn may run several
workers, and an operator may run the command line beside the server. A lock
file next to each state file keeps one writer at a time, so a half-written
session file is never read.
"""

from __future__ import annotations

import fcntl
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TextIO


@contextmanager
def locked_text_file(path: Path, mode: str, lock_type: int) -> Iterator[TextIO]:
    """Open a text file and hold its ``fcntl`` lock for the duration.

    Parameters
    ----------
    path : Path
        File to open. Missing parent directories are created first.
    mode : str
        Standard Python file mode, such as ``"r"``, ``"a+"``, or ``"r+"``.
    lock_type : int
        ``fcntl.LOCK_SH`` for shared reads or ``fcntl.LOCK_EX`` for exclusive
        writes.

    Yields
    ------
    typing.TextIO
        Open UTF-8 text handle with the requested lock held.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open(mode, encoding="utf-8") as file_handle:
        fcntl.flock(file_handle.fileno(), lock_type)
        try:
            yield file_handle
        finally:
            # Publish buffered writes before another process can take the lock
            # and read this file.
            try:
                file_handle.flush()
            finally:
                fcntl.flock(file_handle.fileno(), fcntl.LOCK_UN)
