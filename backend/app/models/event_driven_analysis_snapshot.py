"""Event-driven analysis snapshot model for event-driven narrative analysis."""
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
from .narrative_event import NarrativeEvent


@dataclass
class ArcInfo:
    """Lightweight arc info for event timeline visualization."""
    id: str
    title: str
    color: str

    def to_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "color": self.color}

    @classmethod
    def from_dict(cls, data: dict) -> "ArcInfo":
        return cls(id=data["id"], title=data.get("title", ""), color=data.get("color", "#888"))


@dataclass
class EventDrivenAnalysisSnapshot:
    series: str
    events: List[NarrativeEvent]
    active_terminal_nodes: List[str]
    arcs: List[ArcInfo] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "series": self.series,
            "events": [e.to_dict() for e in self.events],
            "active_terminal_nodes": self.active_terminal_nodes,
            "arcs": [a.to_dict() for a in self.arcs],
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EventDrivenAnalysisSnapshot":
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        arcs = [ArcInfo.from_dict(a) for a in data.get("arcs", [])]
        return cls(
            series=data["series"],
            events=[NarrativeEvent.from_dict(e) for e in data["events"]],
            active_terminal_nodes=data.get("active_terminal_nodes", []),
            arcs=arcs,
            created_at=created_at or datetime.utcnow(),
        )