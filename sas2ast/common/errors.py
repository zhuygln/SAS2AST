"""Error types for sas2ast."""

from __future__ import annotations

from dataclasses import dataclass, field

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"


@dataclass
class ParseError:
    """Structured parse error with source location."""

    message: str
    line: int = 0
    col: int = 0
    snippet: str = ""
    severity: str = SEVERITY_ERROR

    def to_dict(self) -> dict:
        return {
            "message": self.message,
            "line": self.line,
            "col": self.col,
            "snippet": self.snippet,
            "severity": self.severity,
        }

    def __str__(self) -> str:
        loc = f"line {self.line}, col {self.col}" if self.line else "unknown location"
        return f"[{self.severity}] {self.message} ({loc})"
