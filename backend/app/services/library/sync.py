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
                
                current_status = ep.analysis_status
                new_status = current_status
                
                if not has_files:
                    new_status = "missing_files"
                elif current_status == "missing_files" or current_status is None:
                    # If it was missing but now has files, set to pending
                    new_status = "pending"
                
                if new_status != current_status:
                    ep.analysis_status = new_status
                    session.add(ep)
                    updated_count += 1
            
            session.commit()
            logger.info(f"Synchronized {len(episodes)} episodes. Updated {updated_count} statuses.")
            
    except Exception as e:
        logger.error(f"Error during episode status synchronization: {e}")
