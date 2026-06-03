"""Logging utilities — TensorBoard writer stub.

A thin wrapper so engine/app code stays decoupled from the logging backend.
Full implementation (TensorBoard SummaryWriter) added in P9 when RL training starts.
"""

from __future__ import annotations

from typing import Any


class MetricWriter:
    """Stub metric writer. Silently discards all values until P9."""

    def __init__(self, log_dir: str = "logs") -> None:
        self.log_dir = log_dir
        self._step: int = 0

    def scalar(self, tag: str, value: float, step: int | None = None) -> None:
        self._step = step if step is not None else self._step + 1

    def histogram(self, tag: str, values: Any, step: int | None = None) -> None:
        self._step = step if step is not None else self._step + 1

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass

    def __enter__(self) -> MetricWriter:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
