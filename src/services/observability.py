from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import time
import uuid
from typing import Any


@dataclass
class ExecutionLogger:
    model: str = "rule_based"
    task_id: str = field(default_factory=lambda: f"task_{uuid.uuid4().hex[:10]}")
    started_at: float = field(default_factory=time.perf_counter)
    events: list[dict[str, Any]] = field(default_factory=list)

    def log(
        self,
        event_type: str,
        *,
        step_id: str = "",
        component: str = "orchestrator",
        status: str = "success",
        details: dict[str, Any] | None = None,
    ) -> None:
        self.events.append(
            {
                "task_id": self.task_id,
                "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                "event_type": event_type,
                "step_id": step_id,
                "component": component,
                "model": self.model,
                "status": status,
                "elapsed_ms": round((time.perf_counter() - self.started_at) * 1000, 2),
                "details": details or {},
            }
        )

    def to_records(self) -> list[dict[str, Any]]:
        return list(self.events)
