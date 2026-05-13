from typing import Dict, List

from app.services.pipeline.narrative_arc_extraction_pipeline import run_narrative_arc_extraction_pipeline as analyze_episode
from app.services.filesystem.path_handler import PathHandler
from app.services.library.ingestion import SeriesIngestionService
from app.core.logging import setup_logging

logger = setup_logging(__name__)


class NarrativeArcExtractionService:
    def __init__(self, base_dir: str = "data"):
        self.base_dir = base_dir
        self.ingestion_service = SeriesIngestionService(base_dir=base_dir)

    async def run_narrative_arc_extraction(self, series_code: str, season_code: str, episode_code: str) -> None:
        await analyze_episode(series_code, season_code, episode_code, base_dir=self.base_dir)

    async def analyze_series(self, series_code: str) -> Dict[str, List[str]]:
        expected_episodes = self.ingestion_service.list_expected_episodes(series_code)
        processed: List[str] = []
        for item in expected_episodes:
            plot_path = PathHandler.get_episode_plot_path(self.base_dir, series_code, item["season"], item["episode"])
            if not PathHandler.file_exists(plot_path):
                logger.warning(f"Skipping {item['season']} {item['episode']} because no plot file exists")
                continue
            await self.run_narrative_arc_extraction(series_code, item["season"], item["episode"])
            processed.append(f"{item['season']}{item['episode']}")
        return {"processed_episodes": processed}