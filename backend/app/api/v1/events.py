"""Event API routes for event-driven narrative analysis."""
from typing import List
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import os

from app.models.narrative_event import NarrativeEvent
from app.models.event_driven_analysis_snapshot import EventDrivenAnalysisSnapshot, ArcInfo
from app.models.schemas import EventDrivenVideoAnalysisRequest
from app.core.logging import setup_logging
from app.services.event_driven.event_driven_store import EventDrivenStoreService
from app.services.event_driven.event_extraction import extract_events_from_srt
from app.services.event_driven.arc_assignment import assign_arcs_to_events, update_events_with_arcs
from app.services.processing.video_clip_service import extract_event_clips
from app.repositories import DatabaseSessionManager, NarrativeArcRepository

logger = setup_logging(__name__)
router = APIRouter(prefix="/api/events", tags=["events"])
db_manager = DatabaseSessionManager()
DATA_DIR = os.getenv("DATA_DIR", "data")

_event_stores: dict = {}


def get_event_store(series: str) -> EventDrivenStoreService:
    """Get or create event store for series."""
    if series not in _event_stores:
        _event_stores[series] = EventDrivenStoreService(series=series)
    return _event_stores[series]


@router.get("/{series}/snapshot")
async def get_snapshot(series: str) -> EventDrivenAnalysisSnapshot:
    """Get full snapshot with arc info."""
    store = get_event_store(series)
    snapshot = store.get_snapshot()

    with db_manager.session_scope() as session:
        arc_repo = NarrativeArcRepository(session)
        arcs = arc_repo.get_all(series=series)
        if arcs:
            ARC_COLORS = ['#E32017', '#FFD300', '#003688', '#008150', '#F3A9BB', '#A0A5A9', '#EE7C0E', '#B36305']
            snapshot.arcs = [
                ArcInfo(id=str(arc.id), title=arc.title, color=ARC_COLORS[i % len(ARC_COLORS)])
                for i, arc in enumerate(arcs)
            ]
    return snapshot


@router.get("/{series}/events/{event_id}")
async def get_event(series: str, event_id: str) -> NarrativeEvent:
    """Get single event by ID."""
    store = get_event_store(series)
    event = store.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
    return event


@router.post("/{series}/events")
async def add_events(series: str, events: List[NarrativeEvent]) -> dict:
    """Add event(s)."""
    store = get_event_store(series)
    store.add_events(events)
    return {"added": len(events)}


@router.post("/{series}/analyze")
async def analyze_episode(series: str, body: EventDrivenVideoAnalysisRequest) -> dict:
    """Analyze episode: extract events, assign arcs, extract clips."""
    store = get_event_store(series)

    from app.services.library.ingestion import SeriesIngestionService
    from app.services.library.video_service import VideoService
    
    ingestion_svc = SeriesIngestionService(base_dir=DATA_DIR)
    video_svc = VideoService(base_dir=DATA_DIR)
    
    srt_content = ingestion_svc.get_episode_srt_content(series, body.season, body.episode)
    if not srt_content:
        raise HTTPException(status_code=400, detail="SRT content not found for this episode")
        
    video_path = video_svc.get_video_path(series, body.season, body.episode)
    episode_ref = f"{body.season}{body.episode}"

    # 1. Extract events from SRT
    events = await extract_events_from_srt(srt_content, episode_ref, series)
    if not events:
        raise HTTPException(status_code=400, detail="Failed to extract events from SRT")

    # 2. Add events to store
    store.add_events(events)

    # 3. Assign arcs to events using LLM
    with db_manager.session_scope() as session:
        arc_repo = NarrativeArcRepository(session)
        arcs = arc_repo.get_all(series=series)
        if arcs:
            arc_dicts = [
                {
                    "id": str(arc.id),
                    "title": arc.title,
                    "description": arc.description,
                    "main_characters": [char.best_appellation for char in arc.main_characters]
                }
                for arc in arcs
            ]
            assignments = await assign_arcs_to_events(events, arc_dicts)
            update_events_with_arcs(events, assignments)
            for event in events:
                store.add_event(event)
            logger.info(f"Assigned arcs to {len(events)} events")
        else:
            logger.info(f"No arcs for series {series}, skipping arc assignment")

    # 4. Extract video clips
    if video_path:
        import re
        match = re.match(r'^(S\d+)(E\d+)$', episode_ref)
        if match:
            season_folder = match.group(1)
            episode_folder = match.group(2)
            clip_output_dir = os.path.join(DATA_DIR, series, season_folder, episode_folder, "clips")
            events = extract_event_clips(events, video_path, clip_output_dir, srt_content)
            for event in events:
                store.add_event(event)

    # 5. Save
    store.save()

    return {
        "episode_ref": episode_ref,
        "events_extracted": len(events),
        "active_terminals": store.get_active_terminals(),
    }


@router.post("/{series}/save")
async def save_events(series: str) -> dict:
    """Persist events to disk."""
    store = get_event_store(series)
    store.save()
    return {"saved": True}


@router.post("/{series}/clear")
async def clear_events(series: str) -> dict:
    """Clear all events."""
    store = get_event_store(series)
    store.clear()
    return {"cleared": True}


@router.post("/{series}/{season}/{episode}/reset")
async def reset_episode_events(series: str, season: str, episode: str) -> dict:
    """Reset event analysis for a specific episode."""
    store = get_event_store(series)
    episode_ref = f"{season}{episode}"
    
    # 1. Filter out the events matching episode_ref
    nodes_to_remove = []
    for node_id in store._graph.nodes:
        node_data = store._graph.nodes[node_id]
        if node_data.get("episode_ref") == episode_ref:
            nodes_to_remove.append(node_id)
            
    for node_id in nodes_to_remove:
        store._graph.remove_node(node_id)
        
    store.save()
    logger.info(f"Removed {len(nodes_to_remove)} events for episode {episode_ref} in series {series}")
    
    # 2. Remove the clips directory if it exists
    clip_output_dir = os.path.join(DATA_DIR, series, season, episode, "clips")
    if os.path.exists(clip_output_dir):
        import shutil
        try:
            shutil.rmtree(clip_output_dir)
            logger.info(f"Deleted event clips folder: {clip_output_dir}")
        except Exception as e:
            logger.warning(f"Failed to delete event clips folder {clip_output_dir}: {e}")
            
    return {"reset": True, "episode_ref": episode_ref, "removed_events_count": len(nodes_to_remove)}


@router.get("/{series}/clips/{season}/{episode}/clips/{clip_filename:path}")
async def get_clip(series: str, season: str, episode: str, clip_filename: str) -> FileResponse:
    """Stream a video clip."""
    full_path = os.path.join(DATA_DIR, series, season, episode, "clips", clip_filename)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail=f"Clip not found: {clip_filename}")
    return FileResponse(full_path)
