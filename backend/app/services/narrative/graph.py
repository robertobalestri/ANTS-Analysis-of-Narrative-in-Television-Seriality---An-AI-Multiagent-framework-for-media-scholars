"""Narrative arc extraction using LangGraph StateGraph."""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, TypedDict, Any, Optional, Union
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field

from app.core.logging import setup_logging
from app.utils.text import save_json, load_text
from app.models.processing import EntityLink
from app.models.narrative import Character
from app.repositories import DatabaseSessionManager

from app.services.narrative.state import (
    NarrativeArcsExtractionState, 
    IntermediateNarrativeArc, 
    ExtractedArcBase
)

# Node Imports
from app.services.narrative.nodes.identify_present import identify_present_season_arcs
from app.services.narrative.nodes.extract_arcs import extract_and_optimize_arcs
from app.services.narrative.nodes.enhance_arcs import enhance_and_verify_arcs
from app.services.narrative.nodes.sync_nodes import (
    search_candidates_node,
    deduplicate_arc_node,
    evolve_metadata_node,
    persist_arc_node,
)

logger = setup_logging(__name__)


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
# Graph Construction
# ==============================

def create_narrative_arc_graph():
    """Create and compile the narrative arcs extraction graph."""
    workflow = StateGraph(NarrativeArcsExtractionState)

    # Register nodes
    workflow.add_node("initialize_state_node", initialize_state)
    workflow.add_node("identify_present_season_arcs_node", identify_present_season_arcs)
    workflow.add_node("extract_and_optimize_arcs_node", extract_and_optimize_arcs)
    workflow.add_node("enhance_and_verify_arcs_node", enhance_and_verify_arcs)
    workflow.add_node("search_candidates_node", search_candidates_node)
    workflow.add_node("deduplicate_arc_node", deduplicate_arc_node)
    workflow.add_node("evolve_metadata_node", evolve_metadata_node)
    workflow.add_node("persist_arc_node", persist_arc_node)

    # Set entry point
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
        {"sync": "search_candidates_node", "end": END}
    )

    # Deduplication Loop Logic
    def should_continue_dedup(state: NarrativeArcsExtractionState):
        if state['matched_arc_id']:
            return "evolve"
        if state['candidate_index'] < len(state['dedup_candidates']):
            return "continue"
        return "evolve"

    workflow.add_conditional_edges(
        "deduplicate_arc_node",
        should_continue_dedup,
        {"continue": "deduplicate_arc_node", "evolve": "evolve_metadata_node"}
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
        {"next": "search_candidates_node", "end": END}
    )

    return workflow.compile()


def initialize_state(state: NarrativeArcsExtractionState) -> NarrativeArcsExtractionState:
    """Initialize the state by loading necessary data."""
    logger.info("Initializing state.")

    state['current_sync_index'] = 0
    state['dedup_candidates'] = []
    state['candidate_index'] = 0
    state['matched_arc_id'] = None
    state['sync_results'] = []

    # Fetch characters from DB instead of JSON file
    db_manager = DatabaseSessionManager()
    try:
        with db_manager.session_scope() as session:
            # We use session.query here or select() if preferred. SQLModel supports both.
            from sqlmodel import select
            query = select(Character).where(Character.series == state['series'])
            characters = session.exec(query).all()
            
            state['existing_season_entities'] = [
                EntityLink(
                    entity_name=c.entity_name,
                    best_appellation=c.best_appellation,
                    appellations=[a.appellation for a in c.appellations],
                    presence_episodes=[p.episode_code for p in c.presence_episodes]
                )
                for c in characters
            ]
            logger.info(f"Loaded {len(state['existing_season_entities'])} characters from database for series {state['series']}.")
    except Exception as e:
        logger.error(f"Error loading characters from DB: {e}")
        state['existing_season_entities'] = []

    if os.path.exists(state['file_paths']['episode_plot_path']):
        state['episode_plot'] = load_text(state['file_paths']['episode_plot_path'])

    return state


# ==============================
# Entry Point
# ==============================

async def extract_narrative_arcs(file_paths: Dict[str, str], series: str, season: str, episode: str):
    """Entry point for extracting narrative arcs using LangGraph."""
    logger.info("Starting extract_narrative_arcs function")

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

    suggested_arcs = [arc.model_dump() for arc in result['episode_arcs']]
    output_data = {"arcs": suggested_arcs}
    save_json(output_data, file_paths['suggested_episode_arc_path'])
    logger.info(f"Suggested episode arcs saved to {file_paths['suggested_episode_arc_path']}")

    return result.get('sync_results', [])