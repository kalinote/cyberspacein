from __future__ import annotations

import io
import os
import sys
import threading
from typing import TextIO

from .transport import LogTransport


class _Tee(io.TextIOBase):
    def __init__(self, original: TextIO, transport: LogTransport, source: str, level: str):
        self.original = original
        self.transport = transport
        self.source = source
        self.level = level
        self._partial = ""

    def write(self, value: str) -> int:
        self.original.write(value)
        self.original.flush()
        self._partial += value
        while "\n" in self._partial:
            line, self._partial = self._partial.split("\n", 1)
            if line:
                self.transport.emit(self.level, self.source, line)
        return len(value)

    def flush(self) -> None:
        self.original.flush()

    def finish(self) -> None:
        if self._partial:
            self.transport.emit(self.level, self.source, self._partial)
            self._partial = ""


class OutputCapture:
    def __init__(self, transport: LogTransport):
        self.transport = transport
        self.original_stdout_fd: int | None = None
        self.original_stderr_fd: int | None = None
        self._pipes: list[tuple[int, int, str, str]] = []
        self._threads: list[threading.Thread] = []
        self._fallback: tuple[TextIO, TextIO, _Tee, _Tee] | None = None

    def start(self) -> None:
        if os.name == "posix":
            self._start_fd_capture()
        else:
            try:
                self.original_stderr_fd = os.dup(sys.stderr.fileno())
            except (AttributeError, io.UnsupportedOperation, OSError):
                self.original_stderr_fd = None
            stdout = _Tee(sys.stdout, self.transport, "stdout", "INFO")
            stderr = _Tee(sys.stderr, self.transport, "stderr", "ERROR")
            self._fallback = (sys.stdout, sys.stderr, stdout, stderr)
            sys.stdout = stdout
            sys.stderr = stderr

    def _start_fd_capture(self) -> None:
        self.original_stdout_fd = os.dup(1)
        self.original_stderr_fd = os.dup(2)
        for fd, original_fd, source, level in (
            (1, self.original_stdout_fd, "stdout", "INFO"),
            (2, self.original_stderr_fd, "stderr", "ERROR"),
        ):
            read_fd, write_fd = os.pipe()
            os.dup2(write_fd, fd)
            os.close(write_fd)
            self._pipes.append((fd, read_fd, source, level))
            thread = threading.Thread(
                target=self._read_pipe,
                args=(read_fd, original_fd, source, level),
                daemon=True,
            )
            thread.start()
            self._threads.append(thread)

    def _read_pipe(self, read_fd: int, original_fd: int, source: str, level: str) -> None:
        partial = b""
        try:
            while True:
                chunk = os.read(read_fd, 4096)
                if not chunk:
                    break
                os.write(original_fd, chunk)
                partial += chunk
                while b"\n" in partial:
                    raw, partial = partial.split(b"\n", 1)
                    if raw:
                        self.transport.emit(level, source, raw.decode("utf-8", errors="replace"))
            if partial:
                self.transport.emit(level, source, partial.decode("utf-8", errors="replace"))
        finally:
            os.close(read_fd)

    def stop(self) -> None:
        if self._fallback:
            original_stdout, original_stderr, stdout, stderr = self._fallback
            stdout.finish()
            stderr.finish()
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            self._fallback = None
            return
        if self.original_stdout_fd is not None:
            os.dup2(self.original_stdout_fd, 1)
        if self.original_stderr_fd is not None:
            os.dup2(self.original_stderr_fd, 2)
        for thread in self._threads:
            thread.join(timeout=1)

    def close_original_fds(self) -> None:
        for fd in (self.original_stdout_fd, self.original_stderr_fd):
            if fd is not None:
                os.close(fd)
