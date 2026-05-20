"""Library API routes - series management, ingestion, and exploration."""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File
from pydantic import BaseModel
import os
from pathlib import Path
import uuid

from app.core.logging import setup_logging
from app.repositories import DatabaseSessionManager
from app.services.ai import VectorStoreService
from app.services.analysis import NarrativeArcExtractionPipelineService, EpisodeResetService, SeasonResetService
from app.services.library.video_service import VideoService
from app.models.narrative import SeriesMetadata, SeasonMetadata, EpisodeMetadata
import os

DATA_DIR = os.getenv("DATA_DIR", "data")

logger = setup_logging(__name__)
router = APIRouter(prefix="/api/library", tags=["library"])
db_manager = DatabaseSessionManager()


class SeriesCreateRequest(BaseModel):
    code: str
    display_name: str


class SeasonBatchCreateRequest(BaseModel):
    seasons: List[str]


class EpisodeBatchCreateRequest(BaseModel):
    episodes: List[str]


class UploadAssignmentRequest(BaseModel):
    upload_id: str
    season: str
    episode: str


class PlotUpdateRequest(BaseModel):
    content: str


# Legacy/simple endpoints
@router.get("/series")
async def get_series():
    """Get all series."""
    try:
        with db_manager.session_scope() as session:
            from sqlmodel import select
            series_list = session.exec(select(SeriesMetadata)).all()
            return [s.code for s in series_list]
    except Exception as e:
        logger.error(f"Error getting series: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/series")
async def create_series(request: SeriesCreateRequest):
    """Create a new series."""
    try:
        with db_manager.session_scope() as session:
            from sqlmodel import select
            existing = session.exec(
                select(SeriesMetadata).where(SeriesMetadata.code == request.code)
            ).first()
            if existing:
                raise HTTPException(status_code=400, detail="Series already exists")

            new_series = SeriesMetadata(
                code=request.code,
                display_name=request.display_name,
                analysis_state="not_started",
            )
            session.add(new_series)
            session.commit()
            session.refresh(new_series)
            return {
                "code": new_series.code,
                "display_name": new_series.display_name,
                "analysis_state": new_series.analysis_state,
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating series: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Full library explorer endpoints
@router.get("/explorer")
async def get_library_explorer():
    """Get library overview - series with season/episode counts."""
    try:
        from app.services.library.ingestion import SeriesIngestionService
        ingestion_svc = SeriesIngestionService(base_dir=DATA_DIR)
        ingestion_svc.sync_posters()
        
        from app.services.library.explorer import LibraryExplorerService
        svc = LibraryExplorerService(base_dir=DATA_DIR)
        return svc.get_library_overview()
    except Exception as e:
        logger.error(f"Error getting library explorer: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/explorer/{series}")
async def get_series_explorer(series: str):
    """Get series detail with seasons and episodes."""
    try:
        from app.services.library.explorer import LibraryExplorerService
        svc = LibraryExplorerService(base_dir=DATA_DIR)
        return svc.get_series_overview(series)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting series explorer: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Season/Episode management
@router.post("/series/{series}/seasons")
async def create_seasons(series: str, request: SeasonBatchCreateRequest):
    """Create seasons for a series."""
    try:
        with db_manager.session_scope() as session:
            from sqlmodel import select
            series_meta = session.exec(
                select(SeriesMetadata).where(SeriesMetadata.code == series)
            ).first()
            if not series_meta:
                raise HTTPException(status_code=404, detail="Series not found")

            created = 0
            for season_code in request.seasons:
                existing = session.exec(
                    select(SeasonMetadata).where(
                        SeasonMetadata.series_code == series,
                        SeasonMetadata.season_code == season_code
                    )
                ).first()
                if not existing:
                    season = SeasonMetadata(series_code=series, season_code=season_code)
                    session.add(season)
                    created += 1

            session.commit()
            return {"message": f"Created {created} seasons"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating seasons: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/series/{series}/{season}/episodes")
async def create_episodes(series: str, season: str, request: EpisodeBatchCreateRequest):
    """Create episodes for a season."""
    try:
        with db_manager.session_scope() as session:
            from sqlmodel import select
            season_meta = session.exec(
                select(SeasonMetadata).where(
                    SeasonMetadata.series_code == series,
                    SeasonMetadata.season_code == season
                )
            ).first()
            if not season_meta:
                raise HTTPException(status_code=404, detail="Season not found")

            created = 0
            for ep_code in request.episodes:
                existing = session.exec(
                    select(EpisodeMetadata).where(
                        EpisodeMetadata.season_id == season_meta.id,
                        EpisodeMetadata.episode_code == ep_code
                    )
                ).first()
                if not existing:
                    ep = EpisodeMetadata(
                        season_id=season_meta.id, 
                        episode_code=ep_code,
                        narrative_arc_extraction_status="missing_files"
                    )
                    session.add(ep)
                    created += 1

            session.commit()
            return {"message": f"Created {created} episodes"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating episodes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Upload management
@router.post("/series/{series}/uploads")
async def upload_plots(series: str, files: List[UploadFile] = File(...)):
    """Upload plot files for a series."""
    try:
        # Create uploads directory if it doesn't exist
        upload_dir = os.path.join("narrative_storage", "uploads", series)
        os.makedirs(upload_dir, exist_ok=True)

        upload_ids = []
        for file in files:
            upload_id = str(uuid.uuid4())
            file_path = os.path.join(upload_dir, f"{upload_id}_{file.filename}")
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
            upload_ids.append({"upload_id": upload_id, "filename": file.filename})

        return {"uploads": upload_ids}
    except Exception as e:
        logger.error(f"Error uploading files: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/series/{series}/uploads/assign")
async def assign_upload(series: str, request: UploadAssignmentRequest):
    """Assign an uploaded file to a season/episode."""
    try:
        with db_manager.session_scope() as session:
            from sqlmodel import select
            season_meta = session.exec(
                select(SeasonMetadata).where(
                    SeasonMetadata.series_code == series,
                    SeasonMetadata.season_code == request.season
                )
            ).first()
            if not season_meta:
                raise HTTPException(status_code=404, detail="Season not found")

            episode_meta = session.exec(
                select(EpisodeMetadata).where(
                    EpisodeMetadata.season_id == season_meta.id,
                    EpisodeMetadata.episode_code == request.episode
                )
            ).first()
            if not episode_meta:
                raise HTTPException(status_code=404, detail="Episode not found")

            return {"message": f"Assigned upload {request.upload_id} to {series}/{request.season}/{request.episode}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assigning upload: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/series/{series}/{season}/{episode}/upload")
async def upload_episode_file(series: str, season: str, episode: str, file: UploadFile = File(...)):
    """Upload a file directly to an episode and update its status."""
    try:
        from app.services.library.ingestion import SeriesIngestionService
        from app.services.library.explorer import LibraryExplorerService
        
        svc = SeriesIngestionService(base_dir=DATA_DIR)
        explorer_svc = LibraryExplorerService(base_dir=DATA_DIR)
        video_svc = VideoService(base_dir=DATA_DIR)
        
        content = await file.read()
        
        if video_svc.is_video_file(file.filename):
            # Save as binary for video
            result = svc.save_episode_source_file(series, season, episode, file.filename, content)
        else:
            # Save as text for plot/srt
            text_content = content.decode("utf-8")
            result = svc.save_episode_source_file(series, season, episode, file.filename, text_content)
        
        # If it's an SRT, automatically trigger plot generation
        if file.filename.lower().endswith('.srt'):
            logger.info(f"Auto-generating plot for {series} {season} {episode} from uploaded SRT")
            try:
                await explorer_svc.generate_plot_from_srt(series, season, episode)
            except Exception as e:
                logger.error(f"Failed to auto-generate plot: {e}")
        
        # Update DB status
        with db_manager.session_scope() as session:
            from sqlmodel import select
            from app.models.narrative import SeasonMetadata
            
            # Find the episode
            ep_meta = session.exec(
                select(EpisodeMetadata)
                .join(SeasonMetadata)
                .where(
                    SeasonMetadata.series_code == series.upper(),
                    SeasonMetadata.season_code == svc._normalize_season(season),
                    EpisodeMetadata.episode_code == svc._normalize_episode(episode)
                )
            ).first()
            
            if ep_meta:
                # Refresh status from filesystem to be accurate
                from app.services.library.episode_status import LibraryEpisodeStatusBuilder
                status_builder = LibraryEpisodeStatusBuilder(base_dir=DATA_DIR)
                
                # We need the actual paths to check
                normalized_series = svc._normalize_series_code(series)
                normalized_season = svc._normalize_season(season)
                normalized_episode = svc._normalize_episode(episode)
                episode_dir = Path(DATA_DIR) / normalized_series / normalized_season / normalized_episode
                
                current_status = status_builder.build(normalized_series, normalized_season, normalized_episode, 0)
                
                # Check database progressions
                from app.models.narrative import ArcProgression
                progressions = session.exec(
                    select(ArcProgression).where(
                        ArcProgression.series == normalized_series,
                        ArcProgression.season == normalized_season,
                        ArcProgression.episode == normalized_episode
                    )
                ).all()
                has_db_progressions = len(progressions) > 0
                
                # Check vector store
                has_vector_docs = False
                try:
                    from app.services.ai.vector import VectorStoreService
                    vector_svc = VectorStoreService()
                    chroma_results = vector_svc.collection.get(
                        where={"$and": [
                            {"series": normalized_series},
                            {"season": normalized_season},
                            {"episode": normalized_episode}
                        ]}
                    )
                    has_vector_docs = len(chroma_results.get("ids", [])) > 0
                except Exception as e:
                    logger.warning(f"Error checking vector store in upload: {e}")
                
                # Check event snapshot
                has_event_analysis = False
                event_snapshot_file = Path(DATA_DIR) / normalized_series / "event_driven_analysis_snapshot.json"
                if event_snapshot_file.exists():
                    try:
                        import json
                        data = json.loads(event_snapshot_file.read_text(encoding="utf-8"))
                        for event_data in data.get("events", []):
                            if event_data.get("episode_ref") == f"{normalized_season}{normalized_episode}":
                                has_event_analysis = True
                                break
                    except Exception:
                        pass
                
                # Set narrative status
                if has_db_progressions or has_vector_docs:
                    ep_meta.narrative_arc_extraction_status = "completed"
                else:
                    if current_status["has_plot_file"] or current_status["has_srt_file"]:
                        ep_meta.narrative_arc_extraction_status = "pending"
                    else:
                        ep_meta.narrative_arc_extraction_status = "missing_files"
                
                # Set event status
                if has_event_analysis:
                    ep_meta.event_driven_video_analysis_status = "completed"
                else:
                    if ep_meta.event_driven_video_analysis_status is None:
                        ep_meta.event_driven_video_analysis_status = "not_processed"
                
                session.add(ep_meta)
                session.commit()
                
        return result
    except Exception as e:
        logger.error(f"Error uploading episode file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/series/{series}/{season}/{episode}/plot")
async def get_episode_plot(series: str, season: str, episode: str):
    """Get the plot content for an episode."""
    try:
        from app.services.library.ingestion import SeriesIngestionService
        svc = SeriesIngestionService(base_dir=DATA_DIR)
        content = svc.get_episode_plot_content(series, season, episode)
        if content is None:
            raise HTTPException(status_code=404, detail="Plot file not found")
        return {"content": content}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting plot content: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/series/{series}/{season}/{episode}/plot")
async def save_episode_plot(series: str, season: str, episode: str, request: PlotUpdateRequest):
    """Save/update the plot content for an episode and update its database status."""
    try:
        from app.services.library.ingestion import SeriesIngestionService
        svc = SeriesIngestionService(base_dir=DATA_DIR)
        
        # Save the content to the plot file
        result = svc.save_plot_file(series, season, episode, request.content)
        
        # Update database status
        with db_manager.session_scope() as session:
            from sqlmodel import select
            from app.models.narrative import SeasonMetadata
            
            # Find the episode
            ep_meta = session.exec(
                select(EpisodeMetadata)
                .join(SeasonMetadata)
                .where(
                    SeasonMetadata.series_code == series.upper(),
                    SeasonMetadata.season_code == svc._normalize_season(season),
                    EpisodeMetadata.episode_code == svc._normalize_episode(episode)
                )
            ).first()
            
            if ep_meta:
                normalized_series = svc._normalize_series_code(series)
                normalized_season = svc._normalize_season(season)
                normalized_episode = svc._normalize_episode(episode)
                
                # Check database progressions
                from app.models.narrative import ArcProgression
                progressions = session.exec(
                    select(ArcProgression).where(
                        ArcProgression.series == normalized_series,
                        ArcProgression.season == normalized_season,
                        ArcProgression.episode == normalized_episode
                    )
                ).all()
                has_db_progressions = len(progressions) > 0
                
                # Check vector store
                has_vector_docs = False
                try:
                    from app.services.ai.vector import VectorStoreService
                    vector_svc = VectorStoreService()
                    chroma_results = vector_svc.collection.get(
                        where={"$and": [
                            {"series": normalized_series},
                            {"season": normalized_season},
                            {"episode": normalized_episode}
                        ]}
                    )
                    has_vector_docs = len(chroma_results.get("ids", [])) > 0
                except Exception as e:
                    logger.warning(f"Error checking vector store in plot update: {e}")
                
                # Set narrative status
                if has_db_progressions or has_vector_docs:
                    ep_meta.narrative_arc_extraction_status = "completed"
                else:
                    ep_meta.narrative_arc_extraction_status = "pending"
                
                session.add(ep_meta)
                session.commit()
                
        return result
    except Exception as e:
        logger.error(f"Error saving plot content: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/series/{series}/{season}/{episode}/file/{file_type}")
async def get_episode_file(series: str, season: str, episode: str, file_type: str):
    """Get episode file content (srt, plot, etc)."""
    try:
        from app.services.library.ingestion import SeriesIngestionService
        svc = SeriesIngestionService(base_dir=DATA_DIR)

        if file_type == 'srt':
            content = svc.get_episode_srt_content(series, season, episode)
            if content is None:
                raise HTTPException(status_code=404, detail="SRT file not found")
            return {"content": content}
        elif file_type == 'plot':
            content = svc.get_episode_plot_content(series, season, episode)
            if content is None:
                raise HTTPException(status_code=404, detail="Plot file not found")
            return {"content": content}
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_type}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting episode file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/series/{series}/{season}/{episode}/file/{file_type}")
async def delete_episode_file(series: str, season: str, episode: str, file_type: str):
    """Delete a plot or srt file from an episode."""
    try:
        from app.services.library.ingestion import SeriesIngestionService
        svc = SeriesIngestionService(base_dir=DATA_DIR)
        result = svc.delete_episode_file(series, season, episode, file_type)
        
        # Update DB status after deletion
        with db_manager.session_scope() as session:
            from sqlmodel import select
            from app.models.narrative import SeasonMetadata
            
            # Find the episode
            ep_meta = session.exec(
                select(EpisodeMetadata)
                .join(SeasonMetadata)
                .where(
                    SeasonMetadata.series_code == series.upper(),
                    SeasonMetadata.season_code == svc._normalize_season(season),
                    EpisodeMetadata.episode_code == svc._normalize_episode(episode)
                )
            ).first()
            
            if ep_meta:
                # After deletion, check what's left
                from app.services.library.episode_status import LibraryEpisodeStatusBuilder
                status_builder = LibraryEpisodeStatusBuilder(base_dir=DATA_DIR)
                
                normalized_series = svc._normalize_series_code(series)
                normalized_season = svc._normalize_season(season)
                normalized_episode = svc._normalize_episode(episode)
                
                current_status = status_builder.build(normalized_series, normalized_season, normalized_episode, 0)
                
                # Check database progressions
                from app.models.narrative import ArcProgression
                progressions = session.exec(
                    select(ArcProgression).where(
                        ArcProgression.series == normalized_series,
                        ArcProgression.season == normalized_season,
                        ArcProgression.episode == normalized_episode
                    )
                ).all()
                has_db_progressions = len(progressions) > 0
                
                # Check vector store
                has_vector_docs = False
                try:
                    from app.services.ai.vector import VectorStoreService
                    vector_svc = VectorStoreService()
                    chroma_results = vector_svc.collection.get(
                        where={"$and": [
                            {"series": normalized_series},
                            {"season": normalized_season},
                            {"episode": normalized_episode}
                        ]}
                    )
                    has_vector_docs = len(chroma_results.get("ids", [])) > 0
                except Exception as e:
                    logger.warning(f"Error checking vector store in delete: {e}")
                
                # Check event snapshot
                has_event_analysis = False
                event_snapshot_file = Path(DATA_DIR) / normalized_series / "event_driven_analysis_snapshot.json"
                if event_snapshot_file.exists():
                    try:
                        import json
                        data = json.loads(event_snapshot_file.read_text(encoding="utf-8"))
                        for event_data in data.get("events", []):
                            if event_data.get("episode_ref") == f"{normalized_season}{normalized_episode}":
                                has_event_analysis = True
                                break
                    except Exception:
                        pass
                
                # Set narrative status
                if has_db_progressions or has_vector_docs:
                    ep_meta.narrative_arc_extraction_status = "completed"
                else:
                    if not current_status["has_plot_file"] and not current_status["has_srt_file"]:
                        ep_meta.narrative_arc_extraction_status = "missing_files"
                    else:
                        ep_meta.narrative_arc_extraction_status = "pending"
                
                # Set event status
                if has_event_analysis:
                    ep_meta.event_driven_video_analysis_status = "completed"
                else:
                    if ep_meta.event_driven_video_analysis_status is None:
                        ep_meta.event_driven_video_analysis_status = "not_processed"
                    
                session.add(ep_meta)
                session.commit()
                
        return result
    except Exception as e:
        logger.error(f"Error deleting episode file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/series/{series}/{season}/{episode}/video")
async def stream_episode_video(series: str, season: str, episode: str):
    """Stream the video file for an episode."""
    try:
        from fastapi.responses import FileResponse
        video_svc = VideoService(base_dir=DATA_DIR)
        video_path = video_svc.get_video_path(series, season, episode)
        
        if video_path and os.path.exists(video_path):
            return FileResponse(video_path)
            
        raise HTTPException(status_code=404, detail="Video file not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error streaming video: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Analysis endpoints
@router.post("/series/{series}/analyze")
async def analyze_series(series: str, background_tasks: BackgroundTasks):
    """Trigger series analysis."""
    try:
        with db_manager.session_scope() as session:
            from sqlmodel import select
            series_meta = session.exec(
                select(SeriesMetadata).where(SeriesMetadata.code == series)
            ).first()
            if not series_meta:
                raise HTTPException(status_code=404, detail="Series not found")

            series_meta.analysis_state = "in_progress"
            session.commit()

        pipeline = NarrativeArcExtractionPipelineService()

        async def run():
            result = await pipeline.analyze_series(series)
            with db_manager.session_scope() as session:
                from sqlmodel import select
                series_meta = session.exec(
                    select(SeriesMetadata).where(SeriesMetadata.code == series)
                ).first()
                if series_meta:
                    series_meta.analysis_state = "completed"
                    session.commit()
            return result

        result = await run()
        if result.get("status") == "error":
            with db_manager.session_scope() as session:
                from sqlmodel import select
                series_meta = session.exec(
                    select(SeriesMetadata).where(SeriesMetadata.code == series)
                ).first()
                if series_meta:
                    series_meta.analysis_state = "failed"
                    session.commit()
            raise HTTPException(status_code=500, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))





@router.post("/series/{series}/{season}/{episode}/transcribe-video")
async def transcribe_video(series: str, season: str, episode: str):
    """Trigger video transcription for an episode."""
    try:
        from app.services.analysis.pipeline import NarrativeArcExtractionPipelineService
        pipeline = NarrativeArcExtractionPipelineService()
        result = await pipeline.transcribe_episode_video(series, season, episode)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting video transcription: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/series/{series}/{season}/{episode}/plot-from-srt")
async def plot_from_srt(series: str, season: str, episode: str):
    """Generate plot summary from an existing SRT file."""
    try:
        from app.services.analysis.pipeline import NarrativeArcExtractionPipelineService
        pipeline = NarrativeArcExtractionPipelineService()
        result = await pipeline.generate_plot_from_srt(series, season, episode)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating plot from SRT: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/series/{series}/{season}/{episode}/full-video-to-plot")
async def full_video_to_plot(series: str, season: str, episode: str):
    """Transcribe video and generate plot summary."""
    try:
        from app.services.analysis.pipeline import NarrativeArcExtractionPipelineService
        pipeline = NarrativeArcExtractionPipelineService()
        result = await pipeline.generate_dialogues_and_plot_from_video(series, season, episode)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in full video-to-plot: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/series/{series}/status")
async def get_series_status(series: str):
    """Get detailed status for a series (full episode status with file availability)."""
    try:
        from app.services.library.explorer import LibraryExplorerService
        svc = LibraryExplorerService(base_dir=DATA_DIR)
        return svc.get_series_overview(series)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting series status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Analysis/generation endpoints
@router.post("/explorer/{series}/{season}/{episode}/narrative-arc-extraction")
async def narrative_arc_extraction(series: str, season: str, episode: str):
    """Run narrative arc extraction for a single episode."""
    try:
        pipeline = NarrativeArcExtractionPipelineService()
        result = await pipeline.run_narrative_arc_extraction_pipeline(series, season, episode)
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in narrative arc extraction: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/explorer/{series}/{season}/analyze-ready")
async def analyze_season_ready(series: str, season: str, background_tasks: BackgroundTasks):
    """Analyze all plot-ready episodes in a season."""
    try:
        pipeline = NarrativeArcExtractionPipelineService()

        async def run():
            return await pipeline.analyze_season(series, season)

        result = await run()
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing season: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/explorer/{series}/{season}/{episode}/generate-plot")
async def generate_plot(series: str, season: str, episode: str, background_tasks: BackgroundTasks):
    """Generate plot from uploaded files for an episode."""
    try:
        from app.services.library.explorer import LibraryExplorerService
        svc = LibraryExplorerService(base_dir=DATA_DIR)
        result = await svc.generate_plot_from_srt(series.upper(), season.upper(), episode.upper())
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating plot: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/explorer/{series}/{season}/{episode}/reset")
async def reset_episode(series: str, season: str, episode: str):
    """Reset an episode's analysis state."""
    try:
        reset_svc = EpisodeResetService()
        result = reset_svc.reset_episode(series, season, episode)
        return result
    except Exception as e:
        logger.error(f"Error resetting episode: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/explorer/{series}/{season}/{episode}/reset-narrative")
async def reset_narrative(series: str, season: str, episode: str):
    """Reset only narrative arc extraction state."""
    try:
        reset_svc = EpisodeResetService()
        result = reset_svc.reset_narrative_arc_extraction(series, season, episode)
        return result
    except Exception as e:
        logger.error(f"Error resetting narrative: {e}")
        raise HTTPException(status_code=500, detail=str(e))





@router.post("/explorer/{series}/{season}/reset")
async def reset_season(series: str, season: str):
    """Reset all episodes in a season."""
    try:
        reset_svc = SeasonResetService()
        result = reset_svc.reset_season(series, season)
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting season: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/series/{series}/poster")
async def get_series_poster(series: str):
    """Get the poster image for a series."""
    try:
        from fastapi.responses import FileResponse
        # Check for poster image in the series directory
        poster_path = os.path.join(DATA_DIR, series.upper(), f"poster_{series.lower()}.jpg")
        if os.path.exists(poster_path):
            return FileResponse(poster_path)
        
        # Try generic poster.jpg
        poster_path_alt = os.path.join(DATA_DIR, series.upper(), "poster.jpg")
        if os.path.exists(poster_path_alt):
            return FileResponse(poster_path_alt)
            
        raise HTTPException(status_code=404, detail="Poster not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting series poster: {e}")
        raise HTTPException(status_code=500, detail=str(e))
