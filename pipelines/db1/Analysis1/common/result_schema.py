from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class AnalysisResult:
    """Common machine-readable contract for AI Agent / Orchestrator."""
    analysis_id: str
    status: str
    data_period: str | None = None
    data_version: str | None = None
    validation: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    outputs: dict[str, str] = field(default_factory=dict)
    previous_version: str | None = None
    change_summary: dict[str, Any] = field(default_factory=dict)
    requires_human_review: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
