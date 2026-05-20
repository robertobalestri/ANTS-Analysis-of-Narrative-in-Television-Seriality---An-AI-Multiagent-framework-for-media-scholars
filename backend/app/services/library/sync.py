import os
from pathlib import Path
from sqlmodel import select
from app.models.narrative import EpisodeMetadata, SeasonMetadata
from app.repositories import DatabaseSessionManager
from app.core.logging import setup_logging

logger = setup_logging(__name__)

async def sync_episode_statuses(base_dir: str = "data"):
    """Synchronize database episode statuses with the filesystem."""
    db_manager = DatabaseSessionManager()
    logger.info("Starting episode status synchronization...")
    
    try:
        from app.services.library.ingestion import SeriesIngestionService
        ingestion_svc = SeriesIngestionService(base_dir=base_dir)
        ingestion_svc.sync_posters()
        
        with db_manager.session_scope() as session:
            # Load all episodes with their seasons
            episodes = session.exec(select(EpisodeMetadata)).all()
            updated_count = 0
            
            for ep in episodes:
                if not ep.season:
                    continue
                
                series_code = ep.season.series_code
                season_code = ep.season.season_code
                episode_code = ep.episode_code
                
                # Check files
                from app.services.filesystem.path_handler import PathHandler
                path_handler = PathHandler(series_code, season_code, episode_code, base_dir=base_dir)
                plot_path = Path(path_handler.get_raw_plot_file_path())
                
                episode_dir = Path(base_dir) / series_code / season_code / episode_code
                
                # Check for any .srt files
                has_srt = False
                if episode_dir.exists():
                    has_srt = any(episode_dir.glob("*.srt"))
                
                has_files = plot_path.exists() or has_srt
                
                # Check database progressions
                from app.models.narrative import ArcProgression
                progressions = session.exec(
                    select(ArcProgression).where(
                        ArcProgression.series == series_code,
                        ArcProgression.season == season_code,
                        ArcProgression.episode == episode_code
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
                            {"series": series_code},
                            {"season": season_code},
                            {"episode": episode_code}
                        ]}
                    )
                    has_vector_docs = len(chroma_results.get("ids", [])) > 0
                except Exception as e:
                    logger.warning(f"Error checking vector store in sync: {e}")
                
                # Check for event analysis
                has_event_analysis = False
                event_snapshot_file = Path(base_dir) / series_code / "event_driven_analysis_snapshot.json"
                if event_snapshot_file.exists():
                    try:
                        import json
                        data = json.loads(event_snapshot_file.read_text(encoding="utf-8"))
                        for event_data in data.get("events", []):
                            if event_data.get("episode_ref") == f"{season_code}{episode_code}":
                                has_event_analysis = True
                                break
                    except Exception:
                        pass
                
                current_status = ep.narrative_arc_extraction_status
                new_status = current_status
                
                if has_db_progressions or has_vector_docs:
                    new_status = "completed"
                elif not has_files:
                    new_status = "missing_files"
                else:
                    new_status = "pending"
                
                current_event_status = ep.event_driven_video_analysis_status
                new_event_status = current_event_status
                
                if has_event_analysis:
                    new_event_status = "completed"
                elif current_event_status == "completed" or current_event_status is None:
                    new_event_status = "not_processed"
                
                status_changed = False
                if new_status != current_status:
                    ep.narrative_arc_extraction_status = new_status
                    status_changed = True
                if new_event_status != current_event_status:
                    ep.event_driven_video_analysis_status = new_event_status
                    status_changed = True
                
                if status_changed:
                    session.add(ep)
                    updated_count += 1
            
            session.commit()
            logger.info(f"Synchronized {len(episodes)} episodes. Updated {updated_count} statuses.")
            
    except Exception as e:
        logger.error(f"Error during episode status synchronization: {e}")
