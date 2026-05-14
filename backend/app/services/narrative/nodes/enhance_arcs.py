"""Node 3: Enhance and Verify Arcs."""
import json
from app.utils.llm import clean_llm_json_response
from app.core.logging import setup_logging
from app.services.ai.models import get_llm
from app.services.narrative.graph import IntermediateNarrativeArc
from app.services.narrative.prompts import (
    ENHANCE_AND_VERIFY_ARCS_PROMPT,
    DETAILED_OUTPUT_JSON_FORMAT,
    NARRATIVE_ARC_GUIDELINES,
)

logger = setup_logging(__name__)
llm = get_llm()


async def enhance_and_verify_arcs(state: "NarrativeArcsExtractionState") -> "NarrativeArcsExtractionState":
    """Enhance arcs with characters and progression, then verify — single LLM call."""
    logger.info("Enhancing and verifying all arcs (single pass).")

    if not state['episode_arcs']:
        logger.warning("No arcs to enhance. Skipping.")
        return state

    known_characters_info = "No known characters provided."
    if state.get('existing_season_entities'):
        known_characters_info = "\n".join([
            f"- {e.best_appellation} ({e.entity_name})"
            for e in state['existing_season_entities']
        ])

    response = await llm.ainvoke(ENHANCE_AND_VERIFY_ARCS_PROMPT.format_messages(
        episode_plot=state['episode_plot'],
        arcs_to_process=json.dumps([arc.model_dump() for arc in state['episode_arcs']], indent=2),
        present_season_arcs=json.dumps(state['present_season_arcs'], indent=2),
        known_characters=known_characters_info,
        guidelines=NARRATIVE_ARC_GUIDELINES,
        output_json_format=DETAILED_OUTPUT_JSON_FORMAT,
    ))

    try:
        enhanced_data = clean_llm_json_response(response.content)
        enhanced_arcs = []

        # Pre-match by title to carry forward matched_id from previous step
        original_arcs_map = {arc.title.strip().lower(): arc.matched_id for arc in state['episode_arcs']}

        for arc_data in enhanced_data:
            try:
                arc_title = arc_data['title'].strip()
                matched_id = original_arcs_map.get(arc_title.lower())

                enhanced_arcs.append(IntermediateNarrativeArc(
                    title=arc_title,
                    arc_type=arc_data['arc_type'],
                    description=arc_data['description'],
                    main_characters=arc_data.get('main_characters', ''),
                    interfering_episode_characters=arc_data.get('interfering_episode_characters', ''),
                    single_episode_progression_string=arc_data.get('single_episode_progression_string', ''),
                    matched_id=matched_id
                ))
            except Exception as e:
                logger.error(f"Error processing enhanced arc: {e}")
                logger.error(f"Problematic arc data: {arc_data}")
                continue

        if enhanced_arcs:
            # Sort arcs so that matched ones (existing arcs) are processed first
            # This ensures they are updated in DB/Vector before new arcs are checked against them
            enhanced_arcs.sort(key=lambda x: 0 if x.matched_id else 1)

            state['episode_arcs'] = enhanced_arcs
            logger.info(f"Successfully enhanced and verified {len(enhanced_arcs)} arcs.")
        else:
            logger.warning("No arcs were successfully enhanced. Keeping original arcs.")

    except Exception as e:
        logger.error(f"Error during arc enhancement and verification: {e}")
        logger.warning("Enhancement failed. Keeping original arcs.")

    return state