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
        
        target_season = body.season.upper().strip()
        target_episode = body.episode.upper().strip()
        
        logger.info(f"Retrieved {len(arcs)} total arcs for series '{series}'. Filtering for {target_season}{target_episode}...")
        
        valid_arcs = []
        for arc in arcs:
            if arc.arc_type == "Anthology Arc":
                # Check if it has a progression for the specific episode being analyzed
                progressions_in_episode = [
                    prog for prog in arc.progressions
                    if prog.season.upper().strip() == target_season and prog.episode.upper().strip() == target_episode
                ]
                is_part_of_episode = len(progressions_in_episode) > 0
                if not is_part_of_episode:
                    logger.info(f"Skipping Anthology Arc '{arc.title}' (ID: {arc.id}) - not part of {target_season}{target_episode}")
                    continue
                else:
                    logger.info(f"Keeping Anthology Arc '{arc.title}' (ID: {arc.id}) - has {len(progressions_in_episode)} progression(s) in {target_season}{target_episode}")
            else:
                logger.info(f"Keeping Series/Season Arc '{arc.title}' (ID: {arc.id}, Type: {arc.arc_type})")
            valid_arcs.append(arc)

        if valid_arcs:
            logger.info(f"Passing {len(valid_arcs)} valid arcs to assign_arcs_to_events: {[a.title for a in valid_arcs]}")
            arc_dicts = [
                {
                    "id": str(arc.id),
                    "title": arc.title,
                    "description": arc.description,
                    "main_characters": [char.best_appellation for char in arc.main_characters]
                }
                for arc in valid_arcs
            ]
            assignments = await assign_arcs_to_events(events, arc_dicts)
            update_events_with_arcs(events, assignments)
            for event in events:
                store.add_event(event)
            logger.info(f"Assigned arcs to {len(events)} events using {len(valid_arcs)} valid arcs")
        else:
            logger.info(f"No valid arcs for series {series} in episode {episode_ref}, skipping arc assignment")

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

    # 6. Update Database Status
    with db_manager.session_scope() as session:
        from app.models.narrative import EpisodeMetadata, SeasonMetadata
        from sqlmodel import select
        stmt = (
            select(EpisodeMetadata)
            .join(SeasonMetadata)
            .where(SeasonMetadata.series_code == series.upper())
            .where(SeasonMetadata.season_code == body.season.upper())
            .where(EpisodeMetadata.episode_code == body.episode.upper())
        )
        db_episode = session.exec(stmt).first()
        if db_episode:
            db_episode.event_driven_video_analysis_status = "completed"
            session.add(db_episode)

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
    # 3. Update Database Status
    with db_manager.session_scope() as session:
        from app.models.narrative import EpisodeMetadata, SeasonMetadata
        from sqlmodel import select
        stmt = (
            select(EpisodeMetadata)
            .join(SeasonMetadata)
            .where(SeasonMetadata.series_code == series.upper())
            .where(SeasonMetadata.season_code == season.upper())
            .where(EpisodeMetadata.episode_code == episode.upper())
        )
        db_episode = session.exec(stmt).first()
        if db_episode:
            db_episode.event_driven_video_analysis_status = "not_processed"
            session.add(db_episode)

    return {"reset": True, "episode_ref": episode_ref, "removed_events_count": len(nodes_to_remove)}

@router.get("/{series}/clips/{season}/{episode}/clips/{clip_filename:path}")
async def get_clip(series: str, season: str, episode: str, clip_filename: str) -> FileResponse:
    """Stream a video clip."""
    full_path = os.path.join(DATA_DIR, series, season, episode, "clips", clip_filename)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail=f"Clip not found: {clip_filename}")
    return FileResponse(full_path)
