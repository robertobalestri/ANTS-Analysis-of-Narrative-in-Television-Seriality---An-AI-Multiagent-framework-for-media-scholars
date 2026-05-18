"""Narrative event model for temporal graph."""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class EventType(str, Enum):
    ATOMIC = "atomic"
    SYNTHESIS = "synthesis"
    JUNCTION = "junction"


@dataclass
class NarrativeEvent:
    id: str
    episode_ref: str
    content: str
    characters: List[str]
    event_type: EventType
    srt_start_index: int
    srt_end_index: int
    srt_start_time: str  # "HH:MM:SS,mmm"
    srt_end_time: str
    video_start: Optional[float] = None
    video_end: Optional[float] = None
    clip_path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    arc_ids: List[str] = field(default_factory=list)  # arcs this event belongs to
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "episode_ref": self.episode_ref,
            "content": self.content,
            "characters": self.characters,
            "event_type": self.event_type.value if isinstance(self.event_type, EventType) else self.event_type,
            "srt_start_index": self.srt_start_index,
            "srt_end_index": self.srt_end_index,
            "srt_start_time": self.srt_start_time,
            "srt_end_time": self.srt_end_time,
            "video_start": self.video_start,
            "video_end": self.video_end,
            "clip_path": self.clip_path,
            "metadata": self.metadata,
            "arc_ids": self.arc_ids,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NarrativeEvent":
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        return cls(
            id=data["id"],
            episode_ref=data["episode_ref"],
            content=data["content"],
            characters=data["characters"],
            event_type=EventType(data["event_type"]) if isinstance(data["event_type"], str) else data["event_type"],
            srt_start_index=data["srt_start_index"],
            srt_end_index=data["srt_end_index"],
            srt_start_time=data["srt_start_time"],
            srt_end_time=data["srt_end_time"],
            video_start=data.get("video_start"),
            video_end=data.get("video_end"),
            clip_path=data.get("clip_path"),
            metadata=data.get("metadata", {}),
            arc_ids=data.get("arc_ids", []),
            created_at=created_at or datetime.utcnow(),
        )