"""Narrative arc extraction using LangGraph StateGraph."""

import json
import uuid
from typing import Dict, List, TypedDict, Optional, Any
from datetime import datetime
from pathlib import Path
import os

from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field

from app.utils.llm import clean_llm_json_response
from app.core.logging import setup_logging
from app.utils.text import load_text, save_json
from app.services.ai.models import get_llm
from app.models.processing import EntityLink
from app.repositories import DatabaseSessionManager, NarrativeArcRepository, ArcProgressionRepository, CharacterRepository
from app.services.ai.llm import LLMService
from app.services.ai.vector import VectorStoreService
from app.models.narrative import NarrativeArc, ArcProgression
from app.services.narrative.character import CharacterService
from .arc import NarrativeArcService

from .prompts import (
    NARRATIVE_ARC_GUIDELINES,
    DETAILED_OUTPUT_JSON_FORMAT,
    EXTRACTOR_OUTPUT_JSON_FORMAT,
    IDENTIFY_PRESENT_ARCS_PROMPT,
    EXTRACT_AND_OPTIMIZE_ARCS_PROMPT,
    ENHANCE_AND_VERIFY_ARCS_PROMPT,
)

logger = setup_logging(__name__)
llm = get_llm()


# ==============================
# Models
# ==============================

class IntermediateNarrativeArc(BaseModel):
    """Model representing an intermediate narrative arc during extraction process."""
    title: str = Field(..., description="The title of the narrative arc")
    arc_type: str = Field(..., description="Type of the arc such as 'Soap Arc'/'Genre-Specific Arc'/'Anthology Arc'")
    description: str = Field(..., description="A brief description of the narrative arc")
    main_characters: str = Field("", description="Main characters involved in this arc")
    interfering_episode_characters: str = Field("", description="Interfering characters involved in this arc")
    single_episode_progression_string: str = Field("", description="The progression of the arc for the current episode")

    model_config = {"populate_by_name": True}


class ExtractedArcBase(BaseModel):
    """Basic model for initially extracted arcs before enhancement."""
    title: str = Field(..., description="The title of the narrative arc")
    description: str = Field(..., description="A brief description of the narrative arc")
    arc_type: str = Field(..., description="Type of the arc")


# ==============================
# State
# ==============================

class NarrativeArcsExtractionState(TypedDict):
    """State representation for the narrative analysis process."""
    episode_arcs: List[IntermediateNarrativeArc]
    present_season_arcs: List[Dict]
    season_arcs: List[Dict]
    file_paths: Dict[str, str]
    series: str
    season: str
    episode: str
    existing_season_entities: List[EntityLink]
    episode_plot: str

    # Sync Tracking
    current_sync_index: int
    dedup_candidates: List[Dict]
    candidate_index: int
    matched_arc_id: Optional[str]
    sync_results: List[Dict]


# ==============================
# Logging utility
# ==============================

def log_agent_output(agent_name: str, output_data: dict, log_dir: str = "agent_logs") -> None:
    """Log agent output to a file with timestamp."""
    log_dir_path = Path(log_dir)
    log_dir_path.mkdir(parents=True, exist_ok=True)

    timestamp_file = log_dir_path / "current_run_timestamp.txt"
    if not timestamp_file.exists():
        current_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        timestamp_file.write_text(current_timestamp)
    else:
        current_timestamp = timestamp_file.read_text().strip()

    log_file = log_dir_path / f"run_{current_timestamp}.jsonl"

    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "agent": agent_name,
        "output": output_data
    }

    formatted_json = json.dumps(
        log_entry,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        default=str
    )

    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(formatted_json + "\n\n")

    logger.info(f"Logged output from {agent_name}")


# ==============================
# Node 0: Initialize State
# ==============================

def initialize_state(state: NarrativeArcsExtractionState) -> NarrativeArcsExtractionState:
    """Initialize the state by loading necessary data from files."""
    logger.info("Initializing state with data from files.")

    # Initialize sync tracking
    state['current_sync_index'] = 0
    state['dedup_candidates'] = []
    state['candidate_index'] = 0
    state['matched_arc_id'] = None
    state['sync_results'] = []

    if os.path.exists(state['file_paths']['season_entities_path']):
        with open(state['file_paths']['season_entities_path'], 'r') as f:
            season_entities_data = json.load(f)
            state['existing_season_entities'] = [EntityLink(**entity) for entity in season_entities_data]

    if os.path.exists(state['file_paths']['episode_plot_path']):
        state['episode_plot'] = load_text(state['file_paths']['episode_plot_path'])

    logger.info(f"Loaded {len(state['existing_season_entities'])} existing entities from season file.")
    return state


# ==============================
# Node 1: Identify Present Season Arcs (1 LLM call)
# ==============================

async def identify_present_season_arcs(state: NarrativeArcsExtractionState) -> NarrativeArcsExtractionState:
    """Identify which existing season arcs are present in the current episode — single LLM call."""
    logger.info("Identifying present season arcs in the episode (batch).")

    db_manager = DatabaseSessionManager()

    try:
        with db_manager.session_scope() as session:
            arc_repository = NarrativeArcRepository(session)
            season_arcs = arc_repository.get_all(series=state['series'])

            # Filter arcs that have progressions in the current season
            filtered_arcs = []
            for arc in season_arcs:
                progressions_in_season = [prog for prog in arc.progressions if prog.season == state['season']]
                if progressions_in_season:
                    arc.progressions = progressions_in_season
                    filtered_arcs.append(arc)

            state['season_arcs'] = [_arc_to_dict(arc) for arc in filtered_arcs]
            logger.info(f"Retrieved {len(filtered_arcs)} arcs for {state['series']} season {state['season']}.")

    except Exception as e:
        logger.error(f"Error managing season arcs: {e}")
        state['season_arcs'] = []
        state['present_season_arcs'] = []
        return state

    if not state['season_arcs']:
        logger.warning("No existing season arcs found. Skipping present season arcs identification.")
        state['present_season_arcs'] = []
        return state

    # Filter out anthology arcs — they are self-contained and never "continue"
    non_anthology_arcs = [arc for arc in state['season_arcs'] if arc['arc_type'] != "Anthology Arc"]

    if not non_anthology_arcs:
        state['present_season_arcs'] = []
        return state

    # Build a compact summary of arcs to check
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
        state['present_season_arcs'] = present_arcs_data if isinstance(present_arcs_data, list) else []
        logger.info(f"Identified {len(state['present_season_arcs'])} season arcs present in the episode.")
    except Exception as e:
        logger.error(f"Error parsing present season arcs response: {e}")
        state['present_season_arcs'] = []

    log_agent_output("identify_present_season_arcs", {
        "present_season_arcs": state['present_season_arcs'],
        "total_season_arcs_checked": len(non_anthology_arcs),
    })

    return state


def _arc_to_dict(arc: NarrativeArc) -> Dict:
    """Convert a NarrativeArc model to a plain dict."""
    return {
        "id": arc.id,
        "title": arc.title,
        "arc_type": arc.arc_type,
        "description": arc.description,
        "series": arc.series,
    }


# ==============================
# Node 2: Extract & Optimize Arcs (1 LLM call)
# ==============================

async def extract_and_optimize_arcs(state: NarrativeArcsExtractionState) -> NarrativeArcsExtractionState:
    """Extract all narrative arcs (anthology, soap, genre), deduplicate, and optimize — single LLM call."""
    logger.info("Extracting and optimizing all narrative arcs (single pass).")

    response = await llm.ainvoke(EXTRACT_AND_OPTIMIZE_ARCS_PROMPT.format_messages(
        episode_plot=state['episode_plot'],
        present_season_arcs=json.dumps(state['present_season_arcs'], indent=2),
        guidelines=NARRATIVE_ARC_GUIDELINES,
        output_json_format=EXTRACTOR_OUTPUT_JSON_FORMAT,
    ))

    try:
        arcs_data = clean_llm_json_response(response.content)
        extracted_arcs = []

        for arc in arcs_data:
            extracted_arcs.append(ExtractedArcBase(
                title=arc['title'],
                description=arc['description'],
                arc_type=arc.get('arc_type', 'Genre-Specific Arc'),
            ))

        state['episode_arcs'] = extracted_arcs
        logger.info(f"Extracted and optimized {len(extracted_arcs)} arcs in single pass.")
    except Exception as e:
        logger.error(f"Error extracting arcs: {e}")
        state['episode_arcs'] = []

    log_agent_output("extract_and_optimize_arcs", {
        "extracted_arcs": [arc.model_dump() for arc in state['episode_arcs']],
    })

    return state


# ==============================
# Node 3: Enhance & Verify Arcs (1 LLM call)
# ==============================

async def enhance_and_verify_arcs(state: NarrativeArcsExtractionState) -> NarrativeArcsExtractionState:
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

        for arc_data in enhanced_data:
            try:
                enhanced_arcs.append(IntermediateNarrativeArc(
                    title=arc_data['title'],
                    arc_type=arc_data['arc_type'],
                    description=arc_data['description'],
                    main_characters=arc_data.get('main_characters', ''),
                    interfering_episode_characters=arc_data.get('interfering_episode_characters', ''),
                    single_episode_progression_string=arc_data.get('single_episode_progression_string', ''),
                ))
            except Exception as e:
                logger.error(f"Error processing enhanced arc: {e}")
                logger.error(f"Problematic arc data: {arc_data}")
                continue

        if enhanced_arcs:
            state['episode_arcs'] = enhanced_arcs
            logger.info(f"Successfully enhanced and verified {len(enhanced_arcs)} arcs.")
        else:
            logger.warning("No arcs were successfully enhanced. Keeping original arcs.")

    except Exception as e:
        logger.error(f"Error during arc enhancement and verification: {e}")
        logger.warning("Enhancement failed. Keeping original arcs.")

    log_agent_output("enhance_and_verify_arcs", {
        "final_arcs": [arc.model_dump() for arc in state['episode_arcs']],
    })

    return state


# ==============================
# Sync Phase Nodes
# ==============================

async def search_candidates_node(state: NarrativeArcsExtractionState) -> NarrativeArcsExtractionState:
    """Find potential matching arcs for the current extracted arc."""
    if state['current_sync_index'] >= len(state['episode_arcs']):
        return state

    current_arc = state['episode_arcs'][state['current_sync_index']]
    series = state['series']
    
    logger.info(f"Syncing arc {state['current_sync_index'] + 1}/{len(state['episode_arcs'])}: '{current_arc.title}'")

    # 1. Exact Title Search
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

    # 2. Vector Search
    vector_store = VectorStoreService()
    similar_arcs_raw = vector_store.find_similar_arcs(
        query=f"{current_arc.title}\n{current_arc.description}",
        n_results=5,
        series=series
    )
    
    # Filter by threshold (0.4)
    threshold = 0.4
    candidates = [
        arc for arc in similar_arcs_raw
        if arc['cosine_distance'] < threshold
    ]
    
    # Add exact title match as the first candidate if not already there
    final_candidates = []
    if existing_arc_by_title:
        ids = [c['metadata'].get('id') for c in candidates if 'metadata' in c]
        if existing_arc_by_title['id'] not in ids:
            final_candidates.append({
                'metadata': existing_arc_by_title,
                'cosine_distance': 0.0 # Force priority
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
    
    # Check if exists in DB (ghost cleanup)
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

    # LLM Comparison
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
    
    # If it's a new arc, we use the extracted metadata
    if not matched_arc_id:
        state['sync_results'].append({
            'type': 'new',
            'arc': current_arc,
            'matched_id': None
        })
        return state

    # If merged, we evolve
    db_manager = DatabaseSessionManager()
    existing_arc_dict = None
    progressions_history = []
    
    try:
        with db_manager.session_scope() as session:
            repo = NarrativeArcRepository(session)
            found = repo.get_by_id(matched_arc_id)
            if found:
                existing_arc_dict = _arc_to_dict(found)
                # Fetch recent progressions for context
                progs = sorted(found.progressions, key=lambda x: (x.season, x.episode))
                progressions_history = [p.content for p in progs[-10:]]
    except Exception as e:
        logger.error(f"Error fetching arc history for evolution: {e}")

    if not existing_arc_dict:
        return state

    # Evolution Agent
    llm_service = LLMService()
    evolution = llm_service.evolve_arc_metadata(
        current_title=existing_arc_dict['title'],
        current_description=existing_arc_dict['description'],
        progressions=progressions_history,
        new_progression=current_arc.single_episode_progression_string
    )

    # Store evolved metadata in sync_results
    state['sync_results'].append({
        'type': 'merge',
        'arc': current_arc,
        'matched_id': matched_arc_id,
        'evolved_metadata': evolution
    })
    
    return state


async def persist_arc_node(state: NarrativeArcsExtractionState) -> NarrativeArcsExtractionState:
    """Commit the arc and its progression to the database and vector store."""
    if state['current_sync_index'] >= len(state['episode_arcs']):
        return state

    if not state['sync_results']:
        return state
        
    last_result = state['sync_results'][-1]
    arc_data = last_result['arc']
    series = state['series']
    season = state['season']
    episode = state['episode']
    
    db_manager = DatabaseSessionManager()
    with db_manager.session_scope() as session:
        # Correctly instantiate NarrativeArcService with all dependencies
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
            # Create new arc
            new_arc = NarrativeArc(
                id=str(uuid.uuid4()),
                title=arc_data.title,
                description=arc_data.description,
                arc_type=arc_data.arc_type,
                series=series
            )

            # Link main characters
            if arc_data.main_characters:
                main_char_names = [n.strip() for n in arc_data.main_characters.split(';') if n.strip()]
                main_chars = char_service.get_characters_by_appellations(main_char_names, series)
                if main_chars:
                    char_service.link_characters_to_arc(main_chars, new_arc)
                    logger.info(f"Linked {len(main_chars)} main characters to new arc '{new_arc.title}'")

            arc_repo.add_or_update(new_arc)
            session.commit() # Commit to get it in DB for add_progression
            
            # Add progression
            arc_service.add_progression(
                arc_id=new_arc.id,
                content=arc_data.single_episode_progression_string,
                series=series,
                season=season,
                episode=episode,
                interfering_characters=arc_data.interfering_episode_characters
            )
            logger.info(f"Added new arc '{new_arc.title}' to the database.")
            final_arc = new_arc
        else:
            # Update existing arc
            matched_id = last_result['matched_id']
            existing_arc = arc_repo.get_by_id(matched_id)
            
            # Apply evolution
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
                
            # Update main characters if needed
            if arc_data.main_characters:
                main_char_names = [n.strip() for n in arc_data.main_characters.split(';') if n.strip()]
                main_chars = char_service.get_characters_by_appellations(main_char_names, series)
                if main_chars:
                    char_service.link_characters_to_arc(main_chars, existing_arc)
            
            arc_repo.add_or_update(existing_arc)
            session.commit()
            
            # Add progression
            arc_service.add_progression(
                arc_id=existing_arc.id,
                content=arc_data.single_episode_progression_string,
                series=series,
                season=season,
                episode=episode,
                interfering_characters=arc_data.interfering_episode_characters
            )
            logger.info(f"Updated existing arc '{existing_arc.title}' with new progression.")
            final_arc = existing_arc

        # Vector store is already synced inside arc_service.add_progression

    # Increment sync index for the next arc
    state['current_sync_index'] += 1
    
    return state


# ==============================
# Graph Construction
# ==============================

def create_narrative_arc_graph():
    """Create and configure the streamlined state graph for narrative arc extraction."""
    workflow = StateGraph(NarrativeArcsExtractionState)

    # Add nodes
    workflow.add_node("initialize_state_node", initialize_state)
    workflow.add_node("identify_present_season_arcs_node", identify_present_season_arcs)
    workflow.add_node("extract_and_optimize_arcs_node", extract_and_optimize_arcs)
    workflow.add_node("enhance_and_verify_arcs_node", enhance_and_verify_arcs)
    
    # Sync Phase Nodes
    workflow.add_node("search_candidates_node", search_candidates_node)
    workflow.add_node("deduplicate_arc_node", deduplicate_arc_node)
    workflow.add_node("evolve_metadata_node", evolve_metadata_node)
    workflow.add_node("persist_arc_node", persist_arc_node)

    # Linear workflow: Initialize -> Identify Present -> Extract & Optimize -> Enhance & Verify
    workflow.set_entry_point("initialize_state_node")
    workflow.add_edge("initialize_state_node", "identify_present_season_arcs_node")
    workflow.add_edge("identify_present_season_arcs_node", "extract_and_optimize_arcs_node")
    workflow.add_edge("extract_and_optimize_arcs_node", "enhance_and_verify_arcs_node")
    
    # Transition to Sync Phase
    def has_arcs_to_sync(state: NarrativeArcsExtractionState):
        if state['episode_arcs']:
            return "sync"
        return "end"

    workflow.add_conditional_edges(
        "enhance_and_verify_arcs_node",
        has_arcs_to_sync,
        {
            "sync": "search_candidates_node",
            "end": END
        }
    )

    # Deduplication Loop Logic
    def should_continue_dedup(state: NarrativeArcsExtractionState):
        if state['matched_arc_id']:
            return "evolve"
        if state['candidate_index'] < len(state['dedup_candidates']):
            return "continue"
        return "evolve" # No match found after all candidates

    workflow.add_conditional_edges(
        "deduplicate_arc_node",
        should_continue_dedup,
        {
            "continue": "deduplicate_arc_node",
            "evolve": "evolve_metadata_node"
        }
    )
    
    workflow.add_edge("search_candidates_node", "deduplicate_arc_node")
    workflow.add_edge("evolve_metadata_node", "persist_arc_node")

    # Arc Queue Loop Logic
    def should_sync_next(state: NarrativeArcsExtractionState):
        if state['current_sync_index'] < len(state['episode_arcs']):
            return "next"
        return "end"

    workflow.add_conditional_edges(
        "persist_arc_node",
        should_sync_next,
        {
            "next": "search_candidates_node",
            "end": END
        }
    )

    return workflow.compile()


# ==============================
# Entry Point
# ==============================

async def extract_narrative_arcs(file_paths: Dict[str, str], series: str, season: str, episode: str):
    """
    Entry point for extracting narrative arcs using LangGraph.
    """
    logger.info("Starting extract_narrative_arcs function")

    # Create a unique timestamp for this run
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = Path("agent_logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "current_run_timestamp.txt").write_text(timestamp)

    graph = create_narrative_arc_graph()

    initial_state = NarrativeArcsExtractionState(
        episode_arcs=[],
        present_season_arcs=[],
        season_arcs=[],
        file_paths=file_paths,
        series=series,
        season=season,
        episode=episode,
        existing_season_entities=[],
        episode_plot="",
        current_sync_index=0,
        dedup_candidates=[],
        candidate_index=0,
        matched_arc_id=None,
        sync_results=[]
    )
    logger.info("Invoking the graph")
    result = await graph.ainvoke(initial_state)
    logger.info("Graph execution completed")

    # Save the results to a JSON file (Suggestions)
    suggested_arcs = [arc.model_dump() for arc in result['episode_arcs']]
    output_data = {"arcs": suggested_arcs}
    save_json(output_data, file_paths['suggested_episode_arc_path'])
    logger.info(f"Suggested episode arcs saved to {file_paths['suggested_episode_arc_path']}")

    return result.get('sync_results', [])