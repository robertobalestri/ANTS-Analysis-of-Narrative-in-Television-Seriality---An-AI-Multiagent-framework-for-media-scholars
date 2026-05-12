"""Database models for ANTS narrative storage."""
from __future__ import annotations
from typing import List, Optional
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy.orm import relationship
import uuid

from app.models import Base


class ArcMainCharacterLink(Base, table=True):
    """Junction table for main characters in narrative arcs."""
    __tablename__ = "arc_main_characters"

    arc_id: str = Field(foreign_key="narrativearc.id", primary_key=True)
    character_id: str = Field(foreign_key="character.entity_name", primary_key=True)


class ProgressionInterferingCharacterLink(Base, table=True):
    """Junction table for interfering characters in arc progressions."""
    __tablename__ = "progression_interfering_characters"

    progression_id: str = Field(foreign_key="arcprogression.id", primary_key=True)
    character_id: str = Field(foreign_key="character.entity_name", primary_key=True)


class CharacterEpisodePresence(Base, table=True):
    """Model representing a character's presence in a specific episode."""
    __tablename__ = "character_episode_presence"

    character_id: str = Field(foreign_key="character.entity_name", primary_key=True)
    episode_code: str = Field(primary_key=True)
    series: str = Field(index=True)

    character: Optional["Character"] = Relationship(
        back_populates="presence_episodes",
        sa_relationship=relationship(
            "Character",
            back_populates="presence_episodes",
            lazy="selectin"
        )
    )


class CharacterAppellation(Base, table=True):
    """Model representing a character's appellation."""
    __tablename__ = "character_appellation"

    appellation: str = Field(primary_key=True)
    character_id: str = Field(foreign_key="character.entity_name")
    character: Optional["Character"] = Relationship(
        back_populates="appellations",
        sa_relationship=relationship(
            "Character",
            back_populates="appellations",
            lazy="selectin"
        )
    )


class Character(Base, table=True):
    """Model representing a character in the series."""
    __tablename__ = "character"

    entity_name: str = Field(primary_key=True)
    best_appellation: str
    series: str = Field(index=True)

    appellations: List["CharacterAppellation"] = Relationship(
        back_populates="character",
        sa_relationship=relationship(
            "CharacterAppellation",
            back_populates="character",
            cascade="all, delete-orphan"
        )
    )

    presence_episodes: List["CharacterEpisodePresence"] = Relationship(
        back_populates="character",
        sa_relationship=relationship(
            "CharacterEpisodePresence",
            back_populates="character",
            cascade="all, delete-orphan",
            lazy="selectin"
        )
    )

    main_narrative_arcs: List["NarrativeArc"] = Relationship(
        back_populates="main_characters",
        sa_relationship=relationship(
            "NarrativeArc",
            secondary="arc_main_characters",
            back_populates="main_characters",
            lazy="selectin"
        )
    )

    interfering_progressions: List["ArcProgression"] = Relationship(
        back_populates="interfering_characters",
        sa_relationship=relationship(
            "ArcProgression",
            secondary="progression_interfering_characters",
            back_populates="interfering_characters",
            lazy="selectin"
        )
    )


class NarrativeArc(Base, table=True):
    """Model representing a narrative arc."""
    __tablename__ = "narrativearc"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    title: str
    arc_type: str
    description: str
    series: str

    main_characters: List["Character"] = Relationship(
        back_populates="main_narrative_arcs",
        sa_relationship=relationship(
            "Character",
            secondary="arc_main_characters",
            back_populates="main_narrative_arcs",
            lazy="selectin"
        )
    )

    progressions: List["ArcProgression"] = Relationship(
        back_populates="narrative_arc",
        sa_relationship=relationship(
            "ArcProgression",
            back_populates="narrative_arc",
            cascade="all, delete-orphan",
            lazy="selectin"
        )
    )


class ArcProgression(Base, table=True):
    """Model representing a progression within a narrative arc."""
    __tablename__ = "arcprogression"

    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    main_arc_id: str = Field(foreign_key="narrativearc.id")
    content: str
    series: str
    season: str
    episode: str
    ordinal_position: int = Field(default=1, nullable=False)

    interfering_characters: List["Character"] = Relationship(
        back_populates="interfering_progressions",
        sa_relationship=relationship(
            "Character",
            secondary="progression_interfering_characters",
            back_populates="interfering_progressions",
            lazy="selectin"
        )
    )

    narrative_arc: Optional["NarrativeArc"] = Relationship(
        back_populates="progressions",
        sa_relationship=relationship(
            "NarrativeArc",
            back_populates="progressions",
            lazy="selectin"
        )
    )


class SeriesMetadata(Base, table=True):
    """Series metadata stored in SQLite."""
    __tablename__ = "series_metadata"

    code: str = Field(primary_key=True)
    display_name: str
    analysis_state: str = Field(default="not_started")
    analysis_error: Optional[str] = Field(default=None)
    created_at: Optional[str] = Field(default=None)
    updated_at: Optional[str] = Field(default=None)
    poster_url: Optional[str] = Field(default=None)

    seasons: List["SeasonMetadata"] = Relationship(
        back_populates="series",
        sa_relationship=relationship(
            "SeasonMetadata",
            back_populates="series",
            cascade="all, delete-orphan",
            lazy="selectin"
        )
    )

    unmatched_uploads: List["UnmatchedUpload"] = Relationship(
        back_populates="series",
        sa_relationship=relationship(
            "UnmatchedUpload",
            back_populates="series",
            cascade="all, delete-orphan",
            lazy="selectin"
        )
    )


class SeasonMetadata(Base, table=True):
    """Season metadata for a series."""
    __tablename__ = "season_metadata"

    id: Optional[int] = Field(default=None, primary_key=True)
    series_code: str = Field(foreign_key="series_metadata.code", index=True)
    season_code: str = Field(index=True)

    __table_args__ = (
        {"sqlite_autoincrement": True},
    )

    series: Optional["SeriesMetadata"] = Relationship(
        back_populates="seasons",
        sa_relationship=relationship(
            "SeriesMetadata",
            back_populates="seasons",
            lazy="selectin"
        )
    )

    episodes: List["EpisodeMetadata"] = Relationship(
        back_populates="season",
        sa_relationship=relationship(
            "EpisodeMetadata",
            back_populates="season",
            cascade="all, delete-orphan",
            lazy="selectin"
        )
    )


class EpisodeMetadata(Base, table=True):
    """Episode metadata for a season."""
    __tablename__ = "episode_metadata"

    id: Optional[int] = Field(default=None, primary_key=True)
    season_id: int = Field(foreign_key="season_metadata.id", index=True)
    episode_code: str = Field(index=True)
    analysis_status: Optional[str] = Field(default="missing_files", index=True)

    __table_args__ = (
        {"sqlite_autoincrement": True},
    )

    season: Optional["SeasonMetadata"] = Relationship(
        back_populates="episodes",
        sa_relationship=relationship(
            "SeasonMetadata",
            back_populates="episodes",
            lazy="selectin"
        )
    )


class UnmatchedUpload(Base, table=True):
    """Uploaded files not yet assigned to a season or episode."""
    __tablename__ = "unmatched_upload"

    id: Optional[int] = Field(default=None, primary_key=True)
    upload_id: Optional[str] = Field(default=None, index=True)
    series_code: str = Field(foreign_key="series_metadata.code", index=True)
    filename: str
    content: Optional[str] = Field(default=None)
    media_type: str = Field(default="plot")

    series: Optional["SeriesMetadata"] = Relationship(
        back_populates="unmatched_uploads",
        sa_relationship=relationship(
            "SeriesMetadata",
            back_populates="unmatched_uploads",
            lazy="selectin"
        )
    )