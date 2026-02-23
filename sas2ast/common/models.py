"""Shared data models for sas2ast."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Location:
    """Source location (line/col)."""

    line: int = 0
    col: int = 0
    filename: Optional[str] = None

    def to_dict(self) -> dict:
        d: dict = {"line": self.line, "col": self.col}
        if self.filename:
            d["filename"] = self.filename
        return d


@dataclass
class SourceSpan:
    """A range in source code."""

    start: Location
    end: Location

    def to_dict(self) -> dict:
        return {"start": self.start.to_dict(), "end": self.end.to_dict()}


@dataclass
class DatasetRef:
    """Reference to a SAS dataset (lib.name)."""

    name: str
    libref: Optional[str] = None
    options: dict = field(default_factory=dict)
    # Plan B extensions
    is_symbolic: bool = False
    confidence: float = 0.9

    @property
    def qualified_name(self) -> str:
        if self.libref:
            return f"{self.libref}.{self.name}"
        return self.name

    def to_dict(self) -> dict:
        d: dict = {"name": self.name}
        if self.libref:
            d["libref"] = self.libref
        if self.options:
            d["options"] = self.options
        if self.is_symbolic:
            d["is_symbolic"] = True
            d["confidence"] = self.confidence
        return d
