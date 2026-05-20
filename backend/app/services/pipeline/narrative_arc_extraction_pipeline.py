import asyncio
import json
import os

from dotenv import load_dotenv

from app.services.ai import get_llm
from app.services.narrative.graph import extract_narrative_arcs
from app.services.filesystem.path_handler import PathHandler
from app.services.processing.entity_extraction import (
    extract_and_refine_entities,
    substitute_appellations_with_names,
)
from app.models.processing import EntityLink
from app.core.logging import setup_logging
from app.utils.text import clean_text, load_text

load_dotenv(override=True)
logger = setup_logging(__name__)


class _FileTracker:
    """Tracks files created during pipeline execution for rollback on failure."""

    def __init__(self):
        self.created_files: list[str] = []

    def track(self, path: str) -> None:
        self.created_files.append(path)

    def rollback(self) -> None:
        """Remove all tracked files. Called on pipeline failure."""
        for path in self.created_files:
            try:
                if os.path.exists(path):
                    os.remove(path)
                    logger.info(f"Rollback: removed {path}")
            except OSError as e:
                logger.warning(f"Rollback: failed to remove {path}: {e}")
        self.created_files.clear()


async def process_text(path_handler: PathHandler) -> None:
    series = path_handler.series
    season = path_handler.season
    episode = path_handler.episode
    file_tracker = _FileTracker()
    try:
        llm = get_llm()

        input_file = path_handler.get_raw_plot_file_path()
        logger.info(f"Loading raw plot from: {input_file}")
        if not os.path.exists(input_file):
            logger.error(f"Raw plot file not found: {input_file}")
            return

        raw_plot = load_text(input_file)
        cleaned_plot = clean_text(raw_plot)
        logger.info("Cleaning plot text completed.")

        # Extract and refine entities directly from the cleaned plot
        episode_extracted_refined_entities_path = path_handler.get_episode_refined_entities_path()
        season_extracted_refined_entities_path = path_handler.get_season_extracted_refined_entities_path()

        if not os.path.exists(episode_extracted_refined_entities_path):
            logger.info("Extracting and refining entities from cleaned plot.")
            episode_code_str = f"{season}{episode}"
            entities = await extract_and_refine_entities(
                cleaned_plot,
                llm,
                series,
                season,
                episode_code_str,
            )
            file_tracker.track(episode_extracted_refined_entities_path)
        else:
            logger.info(f"Loading existing entities from: {episode_extracted_refined_entities_path}")
            with open(episode_extracted_refined_entities_path, "r") as episode_extracted_refined_entities_file:
                entities_data = json.load(episode_extracted_refined_entities_file)
                entities = [EntityLink(**entity) for entity in entities_data]

        entity_normalized_plot_path = path_handler.get_entity_normalized_plot_file_path()
        if not os.path.exists(entity_normalized_plot_path):
            logger.info("Normalizing entity names in plot.")
            # We use substitute_appellations_with_names to replace all appellations with best_appellation
            entity_normalized_plot = substitute_appellations_with_names(cleaned_plot, entities)
            with open(entity_normalized_plot_path, "w", encoding="utf-8") as entity_normalized_plot_file:
                entity_normalized_plot_file.write(entity_normalized_plot)
            file_tracker.track(entity_normalized_plot_path)
        else:
            logger.info(f"Loading entity normalized plot from: {entity_normalized_plot_path}")
            with open(entity_normalized_plot_path, "r", encoding="utf-8") as entity_normalized_plot_file:
                entity_normalized_plot = entity_normalized_plot_file.read()

        suggested_episode_arc_path = path_handler.get_suggested_episode_arc_path()
        if not os.path.exists(suggested_episode_arc_path):
            file_paths_for_graph = {
                "episode_plot_path": path_handler.get_entity_normalized_plot_file_path(),
                "seasonal_narrative_analysis_output_path": path_handler.get_season_narrative_analysis_path(),
                "episode_narrative_analysis_output_path": path_handler.get_episode_narrative_analysis_path(),
                "season_entities_path": path_handler.get_season_extracted_refined_entities_path(),
                "suggested_episode_arc_path": suggested_episode_arc_path,
            }
            logger.info("Extracting and syncing narrative arcs.")
            sync_results = await extract_narrative_arcs(file_paths_for_graph, series, season, episode)
            
            logger.info(f"Processed {len(sync_results)} arcs in the database via agentic sync.")
            logger.info("Processing complete.")

        # Update episode status to completed
        _update_episode_status(series, season, episode, "completed")
    except Exception as e:
        logger.error(f"An error occurred during processing: {e}")
        logger.info("Rolling back created files due to failure.")
        file_tracker.rollback()
        # Update episode status to error
        _update_episode_status(series, season, episode, "error")
        raise


async def run_narrative_arc_extraction_pipeline(series: str, season: str, episode: str, base_dir: str = "data") -> None:
    logger.warning(f"Starting text processing for episode {episode}")
    await process_text(PathHandler(series, season, episode, base_dir=base_dir))


async def analyze_series(series: str, season: str, episodes: range | None = None, base_dir: str = "data") -> None:
    logger.info("Starting text processing.")
    for ep in episodes or range(1, 10):
        await analyze_episode(series, season, f"E{ep:02d}", base_dir=base_dir)


def _update_episode_status(series: str, season: str, episode: str, status: str) -> None:
    """Update episode narrative_arc_extraction_status in the database."""
    from app.repositories import DatabaseSessionManager
    from app.models.narrative import EpisodeMetadata, SeasonMetadata
    from sqlmodel import select

    db_manager = DatabaseSessionManager()
    try:
        with db_manager.session_scope() as session:
            season_meta = session.exec(
                select(SeasonMetadata).where(
                    SeasonMetadata.series_code == series.upper(),
                    SeasonMetadata.season_code == season.upper()
                )
            ).first()
            if not season_meta:
                return
            episode_meta = session.exec(
                select(EpisodeMetadata).where(
                    EpisodeMetadata.season_id == season_meta.id,
                    EpisodeMetadata.episode_code == episode.upper()
                )
            ).first()
            if episode_meta:
                episode_meta.narrative_arc_extraction_status = status
                session.add(episode_meta)
                session.commit()
                logger.info(f"Updated status for {series} {season} {episode} to {status}")
            else:
                logger.warning(
                    f"Episode {episode} not found in DB for {series} {season}. "
                    f"Could not update narrative_arc_extraction_status={status}"
                )
    except Exception as e:
        logger.error(f"Failed to update episode status: {e}")