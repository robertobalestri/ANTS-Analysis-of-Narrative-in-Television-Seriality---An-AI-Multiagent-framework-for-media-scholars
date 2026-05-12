"""Episodes API routes - simple episode listing."""
from fastapi import APIRouter, HTTPException

from app.core.logging import setup_logging
from app.repositories import DatabaseSessionManager
from app.models.narrative import SeriesMetadata

logger = setup_logging(__name__)
router = APIRouter(prefix="/api/episodes", tags=["episodes"])
db_manager = DatabaseSessionManager()


@router.get("/{series}")
async def get_episodes(series: str):
    """Get all episodes for a series."""
    try:
        with db_manager.session_scope() as session:
            from sqlmodel import select
            series_meta = session.exec(
                select(SeriesMetadata).where(SeriesMetadata.code == series)
            ).first()
            if not series_meta:
                raise HTTPException(status_code=404, detail=f"Series {series} not found")

            episodes = []
            for season in (series_meta.seasons or []):
                for episode in (season.episodes or []):
                    episodes.append({
                        "series": series,
                        "season": season.season_code,
                        "episode": episode.episode_code,
                    })

            return episodes
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting episodes: {e}")
        raise HTTPException(status_code=500, detail=str(e))
