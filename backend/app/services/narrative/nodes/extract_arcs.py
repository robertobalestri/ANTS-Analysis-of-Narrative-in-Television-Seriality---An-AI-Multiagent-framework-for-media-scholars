"""Node 2: Extract and Optimize Arcs."""
import json
from app.utils.llm import clean_llm_json_response
from app.core.logging import setup_logging
from app.services.ai.models import get_llm
from app.services.narrative.graph import ExtractedArcBase
from app.services.narrative.prompts import (
    EXTRACT_AND_OPTIMIZE_ARCS_PROMPT,
    DETAILED_OUTPUT_JSON_FORMAT,
    NARRATIVE_ARC_GUIDELINES,
)

logger = setup_logging(__name__)
llm = get_llm()


async def extract_and_optimize_arcs(state: "NarrativeArcsExtractionState") -> "NarrativeArcsExtractionState":
    """Extract and optimize all arcs in a single comprehensive pass."""
    logger.info("Extracting and optimizing all arcs in single pass.")

    existing_arcs_str = "No existing season arcs found in this episode."
    if state['present_season_arcs']:
        existing_arcs_str = json.dumps(state['present_season_arcs'], indent=2)

    response = await llm.ainvoke(EXTRACT_AND_OPTIMIZE_ARCS_PROMPT.format_messages(
        episode_plot=state['episode_plot'],
        present_season_arcs=existing_arcs_str,
        guidelines=NARRATIVE_ARC_GUIDELINES,
        output_json_format=DETAILED_OUTPUT_JSON_FORMAT,
    ))

    try:
        arcs_data = clean_llm_json_response(response.content)
        extracted_arcs = []

        present_arcs_map = {arc['title'].strip().lower(): arc['id'] for arc in state['present_season_arcs']}

        for arc in arcs_data:
            arc_title = arc['title'].strip()
            matched_id = present_arcs_map.get(arc_title.lower())
            
            extracted_arcs.append(ExtractedArcBase(
                title=arc_title,
                description=arc['description'],
                arc_type=arc.get('arc_type', 'Genre-Specific Arc'),
                matched_id=matched_id
            ))

        state['episode_arcs'] = extracted_arcs
        logger.info(f"Extracted and optimized {len(extracted_arcs)} arcs in single pass.")
    except Exception as e:
        logger.error(f"Error extracting arcs: {e}")
        state['episode_arcs'] = []

    return state