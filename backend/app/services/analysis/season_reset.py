"""Season reset service."""
import argparse
import json
import sys
from typing import Dict

from app.core.logging import setup_logging
from app.services.analysis.episode_reset import EpisodeResetService

logger = setup_logging(__name__)


class SeasonResetService:
    """Reset all episodes in a season and delete series characters."""

    def __init__(self, base_dir: str = "data"):
        self.base_dir = base_dir
        self.episode_reset_service = EpisodeResetService(base_dir=base_dir)

    def reset_season(self, series: str, season: str) -> Dict[str, object]:
        """Reset an entire season: delete all DB records for the season, then reset episode files."""
        from app.services.filesystem.path_handler import PathHandler
        from app.models.narrative import ArcProgression
        from sqlmodel import select

        episodes = PathHandler.list_episode_folders(self.base_dir, series, season)
        episodes_reset = []
        deleted_progression_ids: list[str] = []
        deleted_arc_ids: list[str] = []

        from app.repositories import (
            DatabaseSessionManager,
            ArcProgressionRepository,
            NarrativeArcRepository,
            CharacterRepository,
        )
        from app.services.ai import VectorStoreService
        from app.services.narrative import CharacterService, NarrativeArcService

        db_manager = DatabaseSessionManager()
        vector_store = VectorStoreService()

        # 1. Delete all progressions for this season
        with db_manager.session_scope() as session:
            progression_repo = ArcProgressionRepository(session)
            arc_repo = NarrativeArcRepository(session)
            character_repo = CharacterRepository(session)
            character_service = CharacterService(character_repo)

            # Collect arc IDs before deleting progressions
            season_progressions = session.exec(
                select(ArcProgression).where(
                    ArcProgression.series == series,
                    ArcProgression.season == season,
                )
            ).all()

            affected_arc_ids: set[str] = set()
            for prog in season_progressions:
                if prog.id:
                    try:
                        progression_repo.delete(prog.id)
                        deleted_progression_ids.append(prog.id)
                    except Exception as e:
                        logger.warning(f"Failed to delete progression {prog.id}: {e}")
                affected_arc_ids.add(prog.main_arc_id)

            # 2. Delete arcs with no remaining progressions (in OTHER seasons)
            for arc_id in sorted(affected_arc_ids):
                remaining = session.exec(
                    select(ArcProgression).where(ArcProgression.main_arc_id == arc_id)
                ).all()
                if not remaining:
                    try:
                        narrative_arc_service = NarrativeArcService(
                            arc_repository=arc_repo,
                            progression_repository=progression_repo,
                            character_service=character_service,
                            llm_service=None,
                            vector_store_service=vector_store,
                            session=session,
                        )
                        narrative_arc_service.delete_arc(arc_id)
                        deleted_arc_ids.append(arc_id)
                    except Exception as e:
                        logger.warning(f"Failed to delete arc {arc_id}: {e}")

            # 3. Delete all characters for the series
            characters = character_repo.get_by_series(series)
            for character in characters:
                try:
                    character_repo.delete(character)
                except Exception as e:
                    logger.error(f"Failed to delete character {character.entity_name}: {e}")

        # 4. Delete episode-derived files
        for episode in episodes:
            self.episode_reset_service.reset_episode(series, season, episode)
            episodes_reset.append(episode)

        logger.info(f"Season reset completed for {series} {season}. "
                    f"Reset {len(episodes_reset)} episodes, "
                    f"deleted {len(deleted_progression_ids)} progressions, "
                    f"deleted {len(deleted_arc_ids)} arcs.")

        return {
            "episodes_reset": episodes_reset,
            "deleted_progression_ids": deleted_progression_ids,
            "deleted_arc_ids": deleted_arc_ids,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reset all episodes in a season")
    parser.add_argument("--series", required=True)
    parser.add_argument("--season", required=True)
    parser.add_argument("--base-dir", default="data")
    args = parser.parse_args()

    svc = SeasonResetService(base_dir=args.base_dir)
    result = svc.reset_season(args.series, args.season)
    print(json.dumps(result, indent=2))
    sys.exit(0)