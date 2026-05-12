"""Pydantic schemas for API request/response."""
from typing import List, Optional, Dict, Union
from pydantic import BaseModel


class ArcProgressionResponse(BaseModel):
    id: str
    content: str
    series: str
    season: str
    episode: str
    ordinal_position: int
    interfering_characters: List[str]

    class Config:
        from_attributes = True

    @classmethod
    def from_progression(cls, prog):
        return cls(
            id=prog.id,
            content=prog.content,
            series=prog.series,
            season=prog.season,
            episode=prog.episode,
            ordinal_position=prog.ordinal_position,
            interfering_characters=[char.best_appellation for char in prog.interfering_characters]
        )


class NarrativeArcResponse(BaseModel):
    id: str
    title: str
    description: str
    arc_type: str
    main_characters: List[str]
    series: str
    progressions: List[ArcProgressionResponse]

    class Config:
        from_attributes = True

    @classmethod
    def from_arc(cls, arc):
        return cls(
            id=arc.id,
            title=arc.title,
            description=arc.description,
            arc_type=arc.arc_type,
            main_characters=[char.best_appellation for char in arc.main_characters],
            series=arc.series,
            progressions=[ArcProgressionResponse.from_progression(prog) for prog in arc.progressions]
        )


class ArcUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    arc_type: Optional[str] = None
    main_characters: Optional[List[str]] = None


class ProgressionUpdateRequest(BaseModel):
    content: str
    interfering_characters: List[str]


class ProgressionCreateRequest(BaseModel):
    content: str
    arc_id: str
    series: str
    season: str
    episode: str
    interfering_characters: Union[str, List[str]]


class VectorStoreEntry(BaseModel):
    id: str
    content: str
    metadata: dict
    embedding: Optional[List[float]] = None
    distance: Optional[float] = None


class ProgressionMapping(BaseModel):
    season: str
    episode: str
    content: str
    interfering_characters: List[str]


class ArcMergeRequest(BaseModel):
    arc_id_1: str
    arc_id_2: str
    merged_title: str
    merged_description: str
    merged_arc_type: str
    main_characters: List[str]
    progression_mappings: List[ProgressionMapping]


class InitialProgressionData(BaseModel):
    content: str
    season: str
    episode: str
    interfering_characters: List[str]


class InitialProgressionRequest(BaseModel):
    content: str
    season: str
    episode: str
    interfering_characters: str


class ArcCreateRequest(BaseModel):
    title: str
    description: str
    arc_type: str
    main_characters: str
    series: str
    initial_progression: Optional[InitialProgressionData] = None


class CharacterResponse(BaseModel):
    entity_name: str
    best_appellation: str
    series: str
    appellations: List[str]

    class Config:
        from_attributes = True


class CharacterCreateRequest(BaseModel):
    entity_name: str
    best_appellation: str
    series: str
    appellations: List[str]

    class Config:
        from_attributes = True


class CharacterMergeRequest(BaseModel):
    character1_id: str
    character2_id: str
    keep_character: str