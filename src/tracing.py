from __future__ import annotations

import json
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .guardrails import mask_pii
from .schemas import TraceItem


class TraceRecorder:
    """응답용 trace와 운영용 JSONL trace를 동시에 만든다."""

    _lock = threading.Lock()

    def __init__(self, path: Path, session_id: str):
        self.path = path
        self.session_id = session_id
        self.run_id = str(uuid.uuid4())
        self.items: list[TraceItem] = []

    def add(self, step: str, input_: Any, output: Any, elapsed_ms: float = 0.0) -> None:
        item = TraceItem(
            step=step,
            input=self._sanitize(input_),
            output=self._sanitize(output),
            elapsed_ms=round(elapsed_ms, 2),
        )
        self.items.append(item)
        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "run_id": self.run_id,
            "session_id": self.session_id,
            **item.model_dump(),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    @contextmanager
    def span(self, step: str, input_: Any) -> Iterator[dict[str, Any]]:
        started = time.perf_counter()
        carrier: dict[str, Any] = {}
        try:
            yield carrier
        except Exception as exc:
            carrier["output"] = {"error": type(exc).__name__}
            raise
        finally:
            self.add(
                step,
                input_,
                carrier.get("output"),
                (time.perf_counter() - started) * 1000,
            )

    @staticmethod
    def _sanitize(value: Any) -> Any:
        if isinstance(value, str):
            return mask_pii(value)[:4000]
        if isinstance(value, dict):
            return {key: TraceRecorder._sanitize(val) for key, val in value.items()}
        if isinstance(value, list):
            return [TraceRecorder._sanitize(item) for item in value[:20]]
        return value

