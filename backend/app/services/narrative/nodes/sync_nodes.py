"""Sync Phase Nodes: Search, Dedup, Evolve, Persist."""
import uuid
from typing import Dict
from app.core.logging import setup_logging
from app.repositories import DatabaseSessionManager, NarrativeArcRepository, ArcProgressionRepository, CharacterRepository
from app.services.ai.llm import LLMService
from app.services.ai.vector import VectorStoreService
from app.services.narrative.arc import NarrativeArcService
from app.services.narrative.character import CharacterService
from app.models.narrative import NarrativeArc
from app.utils.text import save_json
from app.services.narrative.state import NarrativeArcsExtractionState

logger = setup_logging(__name__)


def _arc_to_dict(arc: NarrativeArc) -> Dict:
    """Convert a NarrativeArc model to a plain dict."""
    return {
        "id": arc.id,
        "title": arc.title,
        "arc_type": arc.arc_type,
        "description": arc.description,
        "series": arc.series,
    }


async def search_candidates_node(state: NarrativeArcsExtractionState) -> NarrativeArcsExtractionState:
    """Find potential matching arcs for the current extracted arc."""
    if state['current_sync_index'] >= len(state['episode_arcs']):
        return state

    current_arc = state['episode_arcs'][state['current_sync_index']]
    series = state['series']

    logger.info(f"Syncing arc {state['current_sync_index'] + 1}/{len(state['episode_arcs'])}: '{current_arc.title}'")

    # Bypass search if already matched in previous nodes
    if current_arc.matched_id:
        logger.info(f"Arc '{current_arc.title}' already matched with ID {current_arc.matched_id}. Bypassing search.")
        state['matched_arc_id'] = current_arc.matched_id
        state['dedup_candidates'] = [] # No candidates needed
        state['candidate_index'] = 0
        return state

    db_manager = DatabaseSessionManager()
    existing_arc_by_title = None
    try:
        with db_manager.session_scope() as session:
            repo = NarrativeArcRepository(session)
            found = repo.get_by_title(current_arc.title.strip().lower(), series)
            if found:
                existing_arc_by_title = _arc_to_dict(found)
    except Exception as e:
        logger.error(f"Error searching for title match: {e}")

    vector_store = VectorStoreService()
    similar_arcs_raw = vector_store.find_similar_arcs(
        query=f"{current_arc.title}\n{current_arc.description}",
        n_results=5,
        series=series,
        exclude_anthology=True
    )

    threshold = 0.4
    candidates = [
        arc for arc in similar_arcs_raw
        if arc['cosine_distance'] < threshold
    ]

    final_candidates = []
    if existing_arc_by_title:
        ids = [c['metadata'].get('id') for c in candidates if 'metadata' in c]
        if existing_arc_by_title['id'] not in ids:
            final_candidates.append({
                'metadata': existing_arc_by_title,
                'cosine_distance': 0.0
            })

    final_candidates.extend(candidates)

    state['dedup_candidates'] = final_candidates
    state['candidate_index'] = 0
    state['matched_arc_id'] = None

    return state


async def deduplicate_arc_node(state: NarrativeArcsExtractionState) -> NarrativeArcsExtractionState:
    """Evaluate a single candidate for merging."""
    if state['candidate_index'] >= len(state['dedup_candidates']):
        return state

    candidate = state['dedup_candidates'][state['candidate_index']]
    matched_arc_id = candidate['metadata'].get('id')
    current_arc = state['episode_arcs'][state['current_sync_index']]

    db_manager = DatabaseSessionManager()
    vector_existing_arc = None
    try:
        with db_manager.session_scope() as session:
            repo = NarrativeArcRepository(session)
            found = repo.get_by_id(matched_arc_id)
            if found:
                vector_existing_arc = _arc_to_dict(found)
    except Exception as e:
        logger.error(f"Error fetching arc by ID: {e}")

    if not vector_existing_arc:
        logger.warning(f"Vector match found ID {matched_arc_id} but it does not exist in DB. Cleaning up orphaned vector entry.")
        vector_store = VectorStoreService()
        vector_store.delete_documents_by_arc(matched_arc_id)
        state['candidate_index'] += 1
        return state

    llm_service = LLMService()
    merge_decision = llm_service.decide_arc_merging(
        new_arc=current_arc,
        existing_arc=vector_existing_arc
    )

    is_same = merge_decision.get('same_arc', False)
    decision_str = "MERGE" if is_same else "NO MERGE"
    logger.info(f"LLM Decision: {decision_str} (Confidence: {merge_decision.get('confidence', 'N/A')}) - Reasoning: {merge_decision.get('reasoning', 'N/A')}")

    if is_same:
        state['matched_arc_id'] = matched_arc_id
    else:
        state['candidate_index'] += 1

    return state


async def evolve_metadata_node(state: NarrativeArcsExtractionState) -> NarrativeArcsExtractionState:
    """Decide on the final Title and Description for the arc."""
    current_arc = state['episode_arcs'][state['current_sync_index']]
    matched_arc_id = state['matched_arc_id']

    if not matched_arc_id:
        state['sync_results'].append({
            'type': 'new',
            'arc': current_arc,
            'matched_id': None
        })
        return state

    db_manager = DatabaseSessionManager()
    existing_arc_dict = None
    progressions_history = []

    try:
        with db_manager.session_scope() as session:
            repo = NarrativeArcRepository(session)
            found = repo.get_by_id(matched_arc_id)
            if found:
                existing_arc_dict = _arc_to_dict(found)
                progs = sorted(found.progressions, key=lambda x: (x.season, x.episode))
                progressions_history = [p.content for p in progs[-10:]]
    except Exception as e:
        logger.error(f"Error fetching arc history for evolution: {e}")

    if not existing_arc_dict:
        return state

    llm_service = LLMService()
    evolution = llm_service.evolve_arc_metadata(
        current_title=existing_arc_dict['title'],
        current_description=existing_arc_dict['description'],
        progressions=progressions_history,
        new_progression=current_arc.single_episode_progression_string
    )

    state['sync_results'].append({
        'type': 'merge',
        'arc': current_arc,
        'matched_id': matched_arc_id,
        'evolved_metadata': evolution
    })

    return state


async def persist_arc_node(state: NarrativeArcsExtractionState) -> NarrativeArcsExtractionState:
    """Commit the arc and its progression to the database and vector store."""
    if state['current_sync_index'] >= len(state['episode_arcs']) or not state['sync_results']:
        return state

    last_result = state['sync_results'][-1]
    arc_data = last_result['arc']
    series = state['series']
    season = state['season']
    episode = state['episode']

    db_manager = DatabaseSessionManager()
    with db_manager.session_scope() as session:
        arc_repo = NarrativeArcRepository(session)
        prog_repo = ArcProgressionRepository(session)
        char_repo = CharacterRepository(session)
        char_service = CharacterService(char_repo)
        llm_service = LLMService()
        vector_service = VectorStoreService()

        arc_service = NarrativeArcService(
            arc_repository=arc_repo,
            progression_repository=prog_repo,
            character_service=char_service,
            llm_service=llm_service,
            vector_store_service=vector_service,
            session=session
        )

        if last_result['type'] == 'new':
            new_arc = NarrativeArc(
                id=str(uuid.uuid4()),
                title=arc_data.title,
                description=arc_data.description,
                arc_type=arc_data.arc_type,
                series=series
            )
            session.add(new_arc)
            session.flush()

            if arc_data.main_characters:
                main_char_names = [n.strip() for n in arc_data.main_characters.split(';') if n.strip()]
                main_chars = char_service.get_characters_by_appellations(main_char_names, series)
                if main_chars:
                    char_service.link_characters_to_arc(main_chars, new_arc)
                    logger.info(f"Linked {len(main_chars)} main characters to new arc '{new_arc.title}'")

            arc_repo.add_or_update(new_arc)
            session.commit()

            arc_service.add_progression(
                arc_id=new_arc.id,
                content=arc_data.single_episode_progression_string,
                series=series,
                season=season,
                episode=episode,
                interfering_characters=arc_data.interfering_episode_characters
            )
            logger.info(f"Added new arc '{new_arc.title}' to the database.")
        else:
            matched_id = last_result['matched_id']
            existing_arc = arc_repo.get_by_id(matched_id)

            evolution = last_result.get('evolved_metadata', {})
            if evolution:
                new_title = evolution.get('title', '').strip()
                new_desc = evolution.get('description', '').strip()

                if new_title and new_title != existing_arc.title:
                    logger.info(f"Arc title evolving: '{existing_arc.title}' -> '{new_title}'")
                    existing_arc.title = new_title
                if new_desc and new_desc != existing_arc.description:
                    logger.info(f"Arc description updated for '{existing_arc.title}'")
                    existing_arc.description = new_desc

            if arc_data.main_characters:
                main_char_names = [n.strip() for n in arc_data.main_characters.split(';') if n.strip()]
                main_chars = char_service.get_characters_by_appellations(main_char_names, series)
                if main_chars:
                    char_service.link_characters_to_arc(main_chars, existing_arc)

            arc_repo.add_or_update(existing_arc)
            session.commit()

            arc_service.add_progression(
                arc_id=existing_arc.id,
                content=arc_data.single_episode_progression_string,
                series=series,
                season=season,
                episode=episode,
                interfering_characters=arc_data.interfering_episode_characters
            )
            logger.info(f"Updated existing arc '{existing_arc.title}' with new progression.")

    state['current_sync_index'] += 1
    return state