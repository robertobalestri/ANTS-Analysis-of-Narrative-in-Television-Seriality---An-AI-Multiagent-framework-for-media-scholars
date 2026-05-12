import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlmodel import select

from app.services.ai import get_llm
from app.services.pipeline.analysis_service import AnalysisService
from app.services.library.episode_status import LibraryEpisodeStatusBuilder
from app.models.narrative import ArcProgression
from app.repositories import DatabaseSessionManager
from app.services.filesystem.path_handler import PathHandler
from app.services.processing.summarizing import summarize_plot
from app.core.logging import setup_logging

logger = setup_logging(__name__)


class LibraryExplorerService:
    def __init__(self, base_dir: str = "data"):
        self.base_dir = base_dir
        self.db_manager = DatabaseSessionManager()
        self.analysis_service = AnalysisService(base_dir=base_dir)
        self.status_builder = LibraryEpisodeStatusBuilder(base_dir=base_dir)
        self._db_statuses: Optional[Dict[tuple[str, str, str], str]] = None

    def _ensure_db_statuses(self):
        """Lazily load episode statuses from DB once per instance."""
        if self._db_statuses is None:
            self._db_statuses = self._load_episode_db_statuses()

    def get_library_overview(self) -> List[Dict[str, Any]]:
        self._ensure_db_statuses()
        progressions = self._load_progression_counts()
        
        with self.db_manager.session_scope() as session:
            from app.models.narrative import SeriesMetadata
            series_list = session.exec(select(SeriesMetadata)).all()
            
            result: List[Dict[str, Any]] = []
            for series in series_list:
                seasons_payload: List[Dict[str, Any]] = []
                for season in (series.seasons or []):
                    episodes_payload: List[Dict[str, Any]] = []
                    for episode in (season.episodes or []):
                        episodes_payload.append(
                            self._build_episode_status(
                                series.code,
                                season.season_code,
                                episode.episode_code,
                                progressions,
                                self._db_statuses,
                            )
                        )
                    seasons_payload.append(
                        {
                            "season": season.season_code,
                            "episodes": episodes_payload,
                        }
                    )
                result.append(
                    {
                        "code": series.code,
                        "display_name": series.display_name,
                        "poster_url": series.poster_url,
                        "analysis_state": series.analysis_state,
                        "seasons": seasons_payload,
                    }
                )
            return result

    def get_series_overview(self, series_code: str) -> Dict[str, Any]:
        normalized_series = series_code.upper()
        for series in self.get_library_overview():
            if series["code"] == normalized_series:
                return series
        raise ValueError(f"Series {normalized_series} not found")

    async def generate_plot_from_srt(self, series_code: str, season_code: str, episode_code: str) -> Dict[str, Any]:
        normalized_series = series_code.upper()
        normalized_season = season_code.upper()
        normalized_episode = episode_code.upper()
        episode_dir = Path(self.base_dir) / normalized_series / normalized_season / normalized_episode
        srt_path = self.status_builder.find_srt_path(episode_dir)
        if srt_path is None:
            raise ValueError("No SRT file found for this episode")

        from app.utils.text import load_text
        dialogue_text = load_text(str(srt_path))
        if dialogue_text is None or not dialogue_text.strip():
            raise ValueError("SRT file does not contain usable text")

        path_handler = PathHandler(normalized_series, normalized_season, normalized_episode, self.base_dir)
        output_path = path_handler.get_raw_plot_file_path()
        llm = get_llm()
        await summarize_plot(dialogue_text, llm, output_path)
        self._ensure_db_statuses()
        return self._build_episode_status(
            normalized_series,
            normalized_season,
            normalized_episode,
            self._load_progression_counts(),
            self._db_statuses,
        )

    def generate_missing_plots_for_season(self, series_code: str, season_code: str) -> Dict[str, Any]:
        normalized_series = series_code.upper()
        normalized_season = season_code.upper()
        season_path = Path(self.base_dir) / normalized_series / normalized_season
        if not season_path.exists():
            raise ValueError(f"Season {normalized_season} not found for {normalized_series}")

        generated_episodes: List[str] = []
        self._ensure_db_statuses()
        progression_counts = self._load_progression_counts()
        for episode_dir in sorted(path for path in season_path.iterdir() if path.is_dir() and path.name.startswith("E")):
            status = self._build_episode_status(
                normalized_series,
                normalized_season,
                episode_dir.name,
                progression_counts,
                self._db_statuses,
            )
            if status["analysis_status"] == "pending":
                # sync method, run synchronously
                self._generate_plot_sync(normalized_series, normalized_season, episode_dir.name)
                generated_episodes.append(episode_dir.name)

        return {
            "series": normalized_series,
            "season": normalized_season,
            "generated_episodes": generated_episodes,
        }

    def _generate_plot_sync(self, series_code: str, season_code: str, episode_code: str):
        """Synchronously generate plot from SRT."""
        episode_dir = Path(self.base_dir) / series_code / season_code / episode_code
        srt_path = self.status_builder.find_srt_path(episode_dir)
        if srt_path is None:
            return
        with open(srt_path, "r", encoding="utf-8") as f:
            dialogue_text = f.read()
        path_handler = PathHandler(series_code, season_code, episode_code, self.base_dir)
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            llm = get_llm()
            from app.services.ai.llm import summarize_plot
            loop.run_until_complete(summarize_plot(dialogue_text, llm, path_handler.get_raw_plot_file_path()))
        finally:
            loop.close()

    async def analyze_episode(self, series_code: str, season_code: str, episode_code: str) -> Dict[str, Any]:
        normalized_series = series_code.upper()
        normalized_season = season_code.upper()
        normalized_episode = episode_code.upper()
        self._ensure_db_statuses()
        status = self._build_episode_status(
            normalized_series,
            normalized_season,
            normalized_episode,
            self._load_progression_counts(),
            self._db_statuses,
        )
        if status["analysis_status"] not in ("pending", "error"):
            raise ValueError(f"Episode is not ready for analysis (status: {status['analysis_status']})")

        await self.analysis_service.analyze_episode(normalized_series, normalized_season, normalized_episode)
        return self._build_episode_status(
            normalized_series,
            normalized_season,
            normalized_episode,
            self._load_progression_counts(),
            self._db_statuses,
        )

    async def analyze_ready_episodes_for_season(self, series_code: str, season_code: str) -> Dict[str, Any]:
        normalized_series = series_code.upper()
        normalized_season = season_code.upper()
        season_path = Path(self.base_dir) / normalized_series / normalized_season
        if not season_path.exists():
            raise ValueError(f"Season {normalized_season} not found for {normalized_series}")

        processed_episodes: List[str] = []
        self._ensure_db_statuses()
        progression_counts = self._load_progression_counts()
        for episode_dir in sorted(path for path in season_path.iterdir() if path.is_dir() and path.name.startswith("E")):
            status = self._build_episode_status(
                normalized_series,
                normalized_season,
                episode_dir.name,
                progression_counts,
                self._db_statuses,
            )
            if status["analysis_status"] in ("pending", "error"):
                await self.analysis_service.analyze_episode(normalized_series, normalized_season, episode_dir.name)
                processed_episodes.append(episode_dir.name)

        return {
            "series": normalized_series,
            "season": normalized_season,
            "processed_episodes": processed_episodes,
        }

    def _load_episode_db_statuses(self) -> Dict[tuple[str, str, str], str]:
        """Load episode analysis_status from DB."""
        statuses: Dict[tuple[str, str, str], str] = {}
        with self.db_manager.session_scope() as session:
            from app.models.narrative import EpisodeMetadata, SeasonMetadata
            episodes = session.exec(select(EpisodeMetadata)).all()
            for ep in episodes:
                if ep.season:
                    series_code = ep.season.series_code
                    statuses[(series_code, ep.season.season_code, ep.episode_code)] = ep.analysis_status
        return statuses

    def _build_episode_status(
        self,
        series_code: str,
        season_code: str,
        episode_code: str,
        progression_counts: Dict[tuple[str, str, str], int],
        db_statuses: Optional[Dict[tuple[str, str, str], str]] = None,
    ) -> Dict[str, Any]:
        progression_count = progression_counts.get((series_code, season_code, episode_code), 0)
        db_status = db_statuses.get((series_code, season_code, episode_code)) if db_statuses else None
        return self.status_builder.build(series_code, season_code, episode_code, progression_count, db_status=db_status)

    def _load_progression_counts(self) -> Dict[tuple[str, str, str], int]:
        counts: Dict[tuple[str, str, str], int] = defaultdict(int)
        with self.db_manager.session_scope() as session:
            progressions = session.exec(select(ArcProgression)).all()
            for progression in progressions:
                counts[(progression.series, progression.season, progression.episode)] += 1
        return counts

    def _display_name_for_series(self, code: str) -> str:
        if code == "GA":
            return "Grey's Anatomy"
        return code
