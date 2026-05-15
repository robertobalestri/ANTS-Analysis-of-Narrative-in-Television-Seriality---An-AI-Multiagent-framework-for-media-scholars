from typing import Dict, List, TypedDict, Any, Optional, Union
from pydantic import BaseModel, Field

# ==============================
# Models (shared state definitions)
# ==============================

class IntermediateNarrativeArc(BaseModel):
    """Model representing an intermediate narrative arc during extraction process."""
    title: str = Field(..., description="The title of the narrative arc")
    arc_type: str = Field(..., description="Type of the arc such as 'Soap Arc'/'Genre-Specific Arc'/'Anthology Arc'")
    description: str = Field(..., description="A brief description of the narrative arc")
    main_characters: str = Field("", description="Main characters involved in this arc")
    interfering_episode_characters: str = Field("", description="Interfering characters involved in this arc")
    single_episode_progression_string: str = Field("", description="The progression of this arc within the episode")
    matched_id: Optional[str] = Field(None, description="ID of the matching existing arc if already identified")

    model_config = {"populate_by_name": True}


class ExtractedArcBase(BaseModel):
    """Model representing a base extracted arc (title + description + type)."""
    title: str = Field(..., description="The title of the narrative arc")
    description: str = Field(..., description="A brief description of the narrative arc")
    arc_type: str = Field(..., description="Type of the arc such as 'Soap Arc'/'Genre-Specific Arc'/'Anthology Arc'")
    matched_id: Optional[str] = Field(None, description="ID of the matching existing arc if already identified")
    main_characters: str = Field("", description="Main characters involved in this arc")
    interfering_episode_characters: str = Field("", description="Interfering characters involved in this arc")
    single_episode_progression_string: str = Field("", description="The progression of this arc within the episode")


class NarrativeArcsExtractionState(TypedDict):
    """State schema for the narrative arcs extraction graph."""
    episode_arcs: List[Union[IntermediateNarrativeArc, ExtractedArcBase]]
    present_season_arcs: List[Dict]
    season_arcs: List[Dict]
    file_paths: Dict[str, str]
    series: str
    season: str
    episode: str
    existing_season_entities: List[Any]
    episode_plot: str
    current_sync_index: int
    dedup_candidates: List[Any]
    candidate_index: int
    matched_arc_id: str | None
    sync_results: List[Dict]
