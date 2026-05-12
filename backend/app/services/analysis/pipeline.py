"""Analysis pipeline service - bridges FastAPI routes to the analysis pipeline."""
import asyncio
import json
import re
import os
from pathlib import Path
from typing import Dict, Any

from app.core.logging import setup_logging

logger = setup_logging(__name__)

DATA_DIR = os.getenv("DATA_DIR", "data")

# Project root
_ROOT = Path(__file__).resolve().parents[4]


class AnalysisPipelineService:
    """Bridges FastAPI routes to the analysis pipeline.

    Analysis runs inline (via import) since it writes results to disk and DB
    but doesn't cause table conflicts. Reset operations use in-process services
    from app.services.analysis.
    """

    async def analyze_episode(
        self,
        series: str,
        season: str,
        episode: str,
        base_dir: str = DATA_DIR,
    ) -> Dict[str, Any]:
        """Run the full narrative extraction pipeline for a single episode."""
        logger.info(f"Pipeline: analyzing {series}/{season}/{episode}")
        try:
            # Lazy import to avoid SQLModel conflicts at startup
            from app.services.filesystem.path_handler import PathHandler
            from app.services.pipeline.analysis_pipeline import analyze_episode as analyze_fn

            path_handler = PathHandler(series, season, episode, base_dir=base_dir)
            plot_path = path_handler.get_raw_plot_file_path()
            if not os.path.exists(plot_path):
                return {"status": "error", "message": f"Plot file not found: {plot_path}"}

            await analyze_fn(series, season, episode, base_dir=base_dir)
            logger.info(f"Pipeline: completed {series}/{season}/{episode}")
            return {"status": "success", "message": f"Analysis completed for {series}/{season}/{episode}"}
        except Exception as e:
            logger.error(f"Pipeline error for {series}/{season}/{episode}: {e}")
            return {"status": "error", "message": str(e)}

    async def analyze_season(
        self,
        series: str,
        season: str,
        base_dir: str = DATA_DIR,
    ) -> Dict[str, Any]:
        """Analyze all episodes in a season that have plot files."""
        logger.info(f"Pipeline: analyzing season {series}/{season}")
        from app.services.filesystem.path_handler import PathHandler

        episodes = PathHandler.list_episode_folders(base_dir, series, season)
        results = []
        for ep in episodes:
            ph = PathHandler(series, season, ep, base_dir=base_dir)
            if not os.path.exists(ph.get_raw_plot_file_path()):
                logger.info(f"Skipping {ep} - no plot file")
                continue
            result = await self.analyze_episode(series, season, ep, base_dir)
            results.append({"episode": ep, **result})
        return {"status": "success", "season": season, "episodes": results}

    async def analyze_series(
        self,
        series: str,
        base_dir: str = DATA_DIR,
    ) -> Dict[str, Any]:
        """Analyze all plot-ready episodes in a series."""
        logger.info(f"Pipeline: analyzing series {series}")
        try:
            from app.services.pipeline.analysis_service import AnalysisService

            svc = AnalysisService(base_dir=base_dir)
            result = await svc.analyze_series(series)
            return {"status": "success", "series": series, "processed": result}
        except Exception as e:
            logger.error(f"Series analysis error for {series}: {e}")
            return {"status": "error", "message": str(e)}


# ── Reset services — in-process ────────────────────────────────────────────────


class EpisodeResetService:
    """Reset an episode's analysis artifacts via in-process service."""

    def __init__(self, base_dir: str = DATA_DIR):
        self.base_dir = base_dir

    def reset_episode(self, series: str, season: str, episode: str) -> Dict[str, Any]:
        logger.info(f"Resetting episode {series}/{season}/{episode}")
        try:
            from app.services.analysis.episode_reset import EpisodeResetService as _Svc
            svc = _Svc(base_dir=self.base_dir)
            return svc.reset_episode(series, season, episode)
        except Exception as e:
            logger.error(f"Episode reset failed for {series} {season} {episode}: {e}")
            return {"status": "error", "message": str(e)}


class SeasonResetService:
    """Reset all episodes in a season via in-process service."""

    def __init__(self, base_dir: str = DATA_DIR):
        self.base_dir = base_dir

    def reset_season(self, series: str, season: str) -> Dict[str, Any]:
        logger.info(f"Resetting season {series}/{season}")
        try:
            from app.services.analysis.season_reset import SeasonResetService as _Svc
            svc = _Svc(base_dir=self.base_dir)
            return svc.reset_season(series, season)
        except Exception as e:
            logger.error(f"Season reset failed for {series} {season}: {e}")
            return {"status": "error", "message": str(e)}
