from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RunTelemetryCounter:
    """Optional helper. Use it or replace it with your own observability."""
    llm_calls: int = 0
    tool_calls: int = 0
    tool_names: list[str] = field(default_factory=list)
    llm_model: str | None = None
    llm_errors: list[str] = field(default_factory=list)

    def record_llm_call(self, model: str) -> None:
        self.llm_calls += 1
        self.llm_model = model

    def record_llm_error(self, message: str) -> None:
        self.llm_errors.append(message)

    def record_tool_call(self, name: str) -> None:
        self.tool_calls += 1
        self.tool_names.append(name)
