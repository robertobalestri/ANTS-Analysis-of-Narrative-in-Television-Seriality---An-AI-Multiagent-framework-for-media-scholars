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


class NarrativeArcExtractionPipelineService:
    """Bridges FastAPI routes to the narrative arc extraction pipeline.

    Analysis runs inline (via import) since it writes results to disk and DB
    but doesn't cause table conflicts. Reset operations use in-process services
    from app.services.analysis.
    """

    async def run_narrative_arc_extraction_pipeline(
        self,
        series: str,
        season: str,
        episode: str,
        base_dir: str = DATA_DIR,
    ) -> Dict[str, Any]:
        """Run the full narrative extraction pipeline for a single episode."""
        logger.info(f"Pipeline: extracting arcs for {series}/{season}/{episode}")
        try:
            # Lazy import to avoid SQLModel conflicts at startup
            from app.services.filesystem.path_handler import PathHandler
            from app.services.pipeline.narrative_arc_extraction_pipeline import run_narrative_arc_extraction_pipeline as run_fn

            path_handler = PathHandler(series, season, episode, base_dir=base_dir)
            plot_path = path_handler.get_raw_plot_file_path()
            if not os.path.exists(plot_path):
                return {"status": "error", "message": f"Plot file not found: {plot_path}"}

            await run_fn(series, season, episode, base_dir=base_dir)
            logger.info(f"Pipeline: completed {series}/{season}/{episode}")
            return {"status": "success", "message": f"Arc extraction completed for {series}/{season}/{episode}"}
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
            result = await self.run_narrative_arc_extraction_pipeline(series, season, ep, base_dir)
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
            from app.services.pipeline.narrative_arc_extraction_service import NarrativeArcExtractionService

            svc = NarrativeArcExtractionService(base_dir=base_dir)
            result = await svc.analyze_series(series)
            return {"status": "success", "series": series, "processed": result}
        except Exception as e:
            logger.error(f"Series analysis error for {series}: {e}")
            return {"status": "error", "message": str(e)}

    async def analyze_video_scenes(
        self,
        series: str,
        season: str,
        episode: str,
        base_dir: str = DATA_DIR,
    ) -> Dict[str, Any]:
        """Run the video scene extraction pipeline."""
        logger.info(f"Pipeline: analyzing video scenes for {series}/{season}/{episode}")
        try:
            from app.services.pipeline.video_pipeline import process_video_scenes
            
            result = await process_video_scenes(series, season, episode, base_dir=base_dir)
            return result
        except Exception as e:
            logger.error(f"Video pipeline error for {series}/{season}/{episode}: {e}")
            return {"status": "error", "message": str(e)}

    async def transcribe_episode_video(
        self,
        series: str,
        season: str,
        episode: str,
        base_dir: str = DATA_DIR,
    ) -> Dict[str, Any]:
        """Transcribe an episode's video to generate SRT."""
        logger.info(f"Pipeline: transcribing video for {series}/{season}/{episode}")
        try:
            from app.services.filesystem.path_handler import PathHandler
            from app.services.library.video_service import VideoService
            from app.services.processing.transcription_service import TranscriptionService
            import torch

            path_handler = PathHandler(series, season, episode, base_dir=base_dir)
            video_svc = VideoService(base_dir=base_dir)
            video_path = video_svc.find_video_for_episode(series, season, episode)

            if not video_path:
                return {"status": "error", "message": "Video file not found"}

            srt_path = path_handler.get_srt_file_path()
            
            # Determine device
            device = "cuda" if torch.cuda.is_available() else "cpu"
            # Use a slightly better model than tiny if on CUDA
            model_size = "base" if device == "cuda" else "tiny"
            
            transcription_svc = TranscriptionService(device=device, model_size=model_size)
            result = await transcription_svc.transcribe_video(str(video_path), srt_path)
            
            return result
        except Exception as e:
            logger.error(f"Transcription error for {series}/{season}/{episode}: {e}")
            return {"status": "error", "message": str(e)}

    async def generate_plot_from_srt(
        self,
        series: str,
        season: str,
        episode: str,
        base_dir: str = DATA_DIR,
    ) -> Dict[str, Any]:
        """Generate a narrative plot from an existing SRT file."""
        logger.info(f"Pipeline: generating plot from SRT for {series}/{season}/{episode}")
        try:
            from app.services.filesystem.path_handler import PathHandler
            from app.services.processing.summarizing import generate_plot_from_dialogues
            from app.utils.llm import get_llm
            from app.utils.srt import parse_srt, entries_to_text

            path_handler = PathHandler(series, season, episode, base_dir=base_dir)
            srt_path = path_handler.get_srt_file_path()
            if not os.path.exists(srt_path):
                return {"status": "error", "message": "SRT file not found"}

            with open(srt_path, "r", encoding="utf-8") as f:
                srt_content = f.read()
            
            srt_entries = parse_srt(srt_content)
            dialogues_text = entries_to_text(srt_entries)
            
            plot_path = path_handler.get_raw_plot_file_path()
            llm = get_llm()
            
            plot = await generate_plot_from_dialogues(dialogues_text, llm, plot_path)
            
            return {"status": "success", "message": "Plot generated from SRT", "plot_path": plot_path}
        except Exception as e:
            logger.error(f"Error generating plot from SRT: {e}")
            return {"status": "error", "message": str(e)}

    async def generate_dialogues_and_plot_from_video(
        self,
        series: str,
        season: str,
        episode: str,
        base_dir: str = DATA_DIR,
    ) -> Dict[str, Any]:
        """Full pipeline: Transcribe video -> Generate plot from dialogues."""
        logger.info(f"Pipeline: dialogues and plot from video for {series}/{season}/{episode}")
        try:
            # 1. Transcribe
            trans_result = await self.transcribe_episode_video(series, season, episode, base_dir)
            if trans_result.get("status") == "error":
                return trans_result
            
            # 2. Generate Plot
            plot_result = await self.generate_plot_from_srt(series, season, episode, base_dir)
            return plot_result
        except Exception as e:
            logger.error(f"Error in full video to plot pipeline: {e}")
            return {"status": "error", "message": str(e)}


    async def generate_plot_from_srt(
        self,
        series: str,
        season: str,
        episode: str,
        base_dir: str = DATA_DIR,
    ) -> Dict[str, Any]:
        """Generate a plot summary from an existing SRT file."""
        logger.info(f"Pipeline: generating plot from SRT for {series}/{season}/{episode}")
        try:
            from app.services.filesystem.path_handler import PathHandler
            from app.services.processing.plot_generation import generate_plot_from_dialogues
            from app.services.ai import get_llm
            from app.utils.srt import parse_srt, entries_to_text

            path_handler = PathHandler(series, season, episode, base_dir=base_dir)
            srt_path = path_handler.get_srt_file_path()
            if not os.path.exists(srt_path):
                return {"status": "error", "message": "SRT file not found"}

            with open(srt_path, "r", encoding="utf-8") as f:
                srt_content = f.read()
            
            entries = parse_srt(srt_content)
            dialogues_text = entries_to_text(entries)
            
            plot_path = path_handler.get_raw_plot_file_path()
            llm = get_llm()
            
            plot_text = await generate_plot_from_dialogues(dialogues_text, llm, plot_path)
            
            return {
                "status": "success",
                "message": "Plot generated from SRT",
                "plot_path": plot_path,
                "preview": plot_text[:200] + "..."
            }
        except Exception as e:
            logger.error(f"Error generating plot from SRT: {e}")
            return {"status": "error", "message": str(e)}

    async def full_video_to_plot(
        self,
        series: str,
        season: str,
        episode: str,
        base_dir: str = DATA_DIR,
    ) -> Dict[str, Any]:
        """Transcribe video AND generate plot in one go."""
        logger.info(f"Pipeline: Full video-to-plot for {series}/{season}/{episode}")
        try:
            # 1. Transcribe
            transcription_res = await self.transcribe_episode_video(series, season, episode, base_dir)
            if transcription_res.get("status") == "error":
                return transcription_res
            
            # 2. Generate Plot
            plot_res = await self.generate_plot_from_srt(series, season, episode, base_dir)
            return plot_res
        except Exception as e:
            logger.error(f"Full video-to-plot error: {e}")
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
