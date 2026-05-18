"""Shared Pydantic schemas for ANTS API — consumed by backend only.
Import this to align with frontend shared/types.ts.
"""
from typing import Optional, List
from pydantic import BaseModel


class ArcProgressionSchema(BaseModel):
    id: str
    content: str
    series: str
    season: str
    episode: str
    ordinal_position: int
    interfering_characters: List[str]

    class Config:
        from_attributes = True


class NarrativeArcSchema(BaseModel):
    id: str
    title: str
    description: str
    arc_type: str
    main_characters: List[str]
    series: str
    progressions: List[ArcProgressionSchema]

    class Config:
        from_attributes = True


class CharacterSchema(BaseModel):
    entity_name: str
    best_appellation: str
    series: str
    appellations: List[str]

    class Config:
        from_attributes = True


class EpisodeSchema(BaseModel):
    season: str
    episode: str


class LibraryEpisodeStatusSchema(BaseModel):
    season: str
    episode: str
    has_plot: bool


class LibraryUploadSchema(BaseModel):
    upload_id: str
    filename: str


class LibrarySeriesSummarySchema(BaseModel):
    code: str
    display_name: str
    analysis_state: str
    expected_episode_count: int
    uploaded_episode_count: int
    unmatched_upload_count: int


class LibrarySeriesStatusSchema(LibrarySeriesSummarySchema):
    episodes: List[LibraryEpisodeStatusSchema]
    unmatched_uploads: List[LibraryUploadSchema]
    auto_matched_uploads: Optional[List[dict]] = None


class ExplorerEpisodeStatusSchema(BaseModel):
    series: str
    season: str
    episode: str
    has_plot_file: bool
    has_srt_file: bool
    has_video_file: bool
    video_filename: Optional[str] = None
    has_dialogue_json: bool
    has_analysis_artifacts: bool
    has_clips: bool
    has_event_analysis: bool
    progression_count: int
    analysis_status: str


class ExplorerSeasonSchema(BaseModel):
    season: str
    episodes: List[ExplorerEpisodeStatusSchema]


class ExplorerSeriesSchema(BaseModel):
    code: str
    display_name: str
    poster_url: Optional[str] = None
    seasons: Optional[List[ExplorerSeasonSchema]] = None


class VectorStoreEntrySchema(BaseModel):
    id: str
    content: str
    metadata: dict
    embedding: Optional[List[float]] = None
    distance: Optional[float] = None


class ApiErrorResponseSchema(BaseModel):
    error: str
    code: Optional[str] = None
    details: Optional[dict] = None


class ApiSuccessResponseSchema(BaseModel):
    data: dict
    meta: Optional[dict] = None