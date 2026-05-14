"""Node 1: Identify Present Season Arcs."""
import json
from typing import Dict
from langgraph.graph import StateGraph, END

from app.utils.llm import clean_llm_json_response
from app.core.logging import setup_logging
from app.services.ai.models import get_llm
from app.repositories import DatabaseSessionManager, NarrativeArcRepository
from app.models.narrative import NarrativeArc
from app.services.narrative.prompts import IDENTIFY_PRESENT_ARCS_PROMPT

logger = setup_logging(__name__)
llm = get_llm()


def _arc_to_dict(arc: NarrativeArc) -> Dict:
    """Convert a NarrativeArc model to a plain dict."""
    return {
        "id": arc.id,
        "title": arc.title,
        "arc_type": arc.arc_type,
        "description": arc.description,
        "series": arc.series,
    }


async def identify_present_season_arcs(state: "NarrativeArcsExtractionState") -> "NarrativeArcsExtractionState":
    """Identify which existing season arcs are present in the current episode."""
    logger.info("Identifying present season arcs in the episode (batch).")

    db_manager = DatabaseSessionManager()

    try:
        with db_manager.session_scope() as session:
            arc_repository = NarrativeArcRepository(session)
            season_arcs = arc_repository.get_all(series=state['series'])

            filtered_arcs = []
            for arc in season_arcs:
                progressions_in_season = [prog for prog in arc.progressions if prog.season == state['season']]
                if progressions_in_season:
                    arc.progressions = progressions_in_season
                    filtered_arcs.append(arc)

            # Exclude Anthology Arcs from series context retrieval
            state['season_arcs'] = [
                _arc_to_dict(arc) for arc in filtered_arcs 
                if arc.arc_type != "Anthology Arc"
            ]
            logger.info(f"Retrieved {len(state['season_arcs'])} non-anthology arcs for {state['series']} season {state['season']}.")

    except Exception as e:
        logger.error(f"Error managing season arcs: {e}")
        state['season_arcs'] = []
        state['present_season_arcs'] = []
        return state

    if not state['season_arcs']:
        logger.warning("No existing season arcs found. Skipping present season arcs identification.")
        state['present_season_arcs'] = []
        return state

    non_anthology_arcs = [arc for arc in state['season_arcs'] if arc['arc_type'] != "Anthology Arc"]

    if not non_anthology_arcs:
        state['present_season_arcs'] = []
        return state

    arcs_summary = json.dumps(
        [{"title": arc["title"], "description": arc["description"]} for arc in non_anthology_arcs],
        indent=2
    )

    response = await llm.ainvoke(IDENTIFY_PRESENT_ARCS_PROMPT.format_messages(
        episode_plot=state['episode_plot'],
        season_arcs=arcs_summary,
    ))

    try:
        present_arcs_data = clean_llm_json_response(response.content)
        
        # Map the identified titles back to their original data including the ID
        season_arcs_map = {arc['title'].strip().lower(): arc for arc in state['season_arcs']}
        final_present_arcs = []
        
        if isinstance(present_arcs_data, list):
            for item in present_arcs_data:
                title = item.get('title', '').strip().lower()
                if title in season_arcs_map:
                    # Keep the original arc data (ID, title, description, etc.)
                    final_present_arcs.append(season_arcs_map[title])
                else:
                    logger.warning(f"LLM identified arc '{item.get('title')}' but it doesn't match any known season arc title.")

        state['present_season_arcs'] = final_present_arcs
        logger.info(f"Identified {len(state['present_season_arcs'])} season arcs present in the episode.")
    except Exception as e:
        logger.error(f"Error parsing present season arcs response: {e}")
        state['present_season_arcs'] = []

    return state