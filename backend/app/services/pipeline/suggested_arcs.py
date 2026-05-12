"""Process suggested narrative arcs from JSON output."""
import logging
import json
from typing import List, Optional

from app.repositories import (
    DatabaseSessionManager,
    NarrativeArcRepository,
    ArcProgressionRepository,
    CharacterRepository,
)
from app.services.narrative import CharacterService, NarrativeArcService
from app.services.ai import LLMService, VectorStoreService
from app.models.processing import EntityLink
from app.utils.text import load_text
from app.core.logging import setup_logging

logger = setup_logging(__name__)


def process_suggested_arcs(
    suggested_arcs_path: str,
    series: str,
    season: str,
    episode: str,
    entity_substituted_plot_path: Optional[str] = None,
    season_entities_path: Optional[str] = None
):
    """Process suggested arcs from JSON, creating arc entries in the database.

    Args:
        suggested_arcs_path: Path to the suggested arcs JSON file.
        series: Series name.
        season: Season number.
        episode: Episode number.
        entity_substituted_plot_path: Optional path to entity-substituted plot JSON.
        season_entities_path: Optional path to season-level entities JSON.
    """
    # Initialize services
    db_manager = DatabaseSessionManager()
    llm_service = LLMService()
    vector_store_service = VectorStoreService()

    with db_manager.session_scope() as session:
        # Initialize repositories and services
        arc_repository = NarrativeArcRepository(session)
        progression_repository = ArcProgressionRepository(session)
        character_repository = CharacterRepository(session)
        character_service = CharacterService(character_repository)
        narrative_arc_service = NarrativeArcService(
            arc_repository=arc_repository,
            progression_repository=progression_repository,
            character_service=character_service,
            llm_service=llm_service,
            vector_store_service=vector_store_service,
            session=session,
        )

        # Load suggested arcs
        suggested_arcs_text = load_text(suggested_arcs_path)
        suggested_arcs = json.loads(suggested_arcs_text)

        arcs_to_process = suggested_arcs.get("arcs", []) if isinstance(suggested_arcs, dict) else suggested_arcs

        if not arcs_to_process:
            logger.warning(f"No suggested arcs found at {suggested_arcs_path}")
            return []

        # Load entity-substituted plot if provided
        # entity_substituted_plot_path is plain text, not used in processing
        pass

        # Load season entities if provided
        season_entities: List[EntityLink] = []
        if season_entities_path:
            try:
                entities_text = load_text(season_entities_path)
                entities_data = json.loads(entities_text)
                season_entities = [EntityLink(**e) for e in entities_data]
            except Exception as e:
                logger.warning(f"Failed to load season entities: {e}")

        # Process each suggested arc
        for arc_data in arcs_to_process:
            arc_data["series"] = series
            arc_data["season"] = season
            arc_data["episode"] = episode
            narrative_arc_service.add_arc(
                arc_data=arc_data,
                series=series,
                season=season,
                episode=episode,
            )

        return []