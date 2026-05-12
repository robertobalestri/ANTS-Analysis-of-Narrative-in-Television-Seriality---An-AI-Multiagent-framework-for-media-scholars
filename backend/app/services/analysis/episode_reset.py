"""Episode reset service - removes all derived artifacts for an episode."""
from pathlib import Path
from typing import Dict, List, Set
import argparse
import json
import sys

from sqlmodel import select

from app.core.logging import setup_logging
from app.models.narrative import ArcProgression, CharacterEpisodePresence
from app.repositories import ArcProgressionRepository, NarrativeArcRepository, CharacterRepository, DatabaseSessionManager
from app.services.ai import VectorStoreService
from app.services.narrative import NarrativeArcService, CharacterService
from app.services.filesystem.path_handler import PathHandler

logger = setup_logging(__name__)


def _is_protected_file(path: Path) -> bool:
    """Return True if the file is source data that must not be deleted."""
    name = path.name.lower()
    if name.endswith(".srt"):
        return True
    if name.endswith("_plot.txt"):
        return True
    if name.endswith("_dialogues.txt"):
        return True
    return False


class EpisodeResetService:
    """Fully reset an episode: delete all derived files, DB records, and vector entries."""

    def __init__(self, base_dir: str = "data"):
        self.base_dir = base_dir
        self.db_manager = DatabaseSessionManager()
        self.vector_store_service = VectorStoreService()

    def reset_episode(self, series: str, season: str, episode: str) -> Dict[str, object]:
        """Reset an episode's analysis artifacts. Safe to call regardless of current state."""
        derived_files_deleted = self._delete_all_derived_files(series, season, episode)
        vector_entries_deleted = self._delete_vector_entries(series, season, episode)
        db_results = self._delete_db_records(series, season, episode)
        self._cleanup_character_presence(series, season, episode)

        return {
            "removed_progression_ids": db_results["removed_progression_ids"],
            "deleted_arc_ids": db_results["deleted_arc_ids"],
            "updated_arc_ids": db_results["updated_arc_ids"],
            "deleted_artifacts": derived_files_deleted,
            "deleted_vector_entries": vector_entries_deleted,
        }

    def _delete_all_derived_files(self, series: str, season: str, episode: str) -> List[str]:
        """Delete every file in the episode directory except source files."""
        episode_dir = Path(self.base_dir) / series / season / episode
        deleted: List[str] = []

        if not episode_dir.exists():
            logger.info(f"Episode directory does not exist: {episode_dir}")
            return deleted

        for file_path in episode_dir.iterdir():
            if not file_path.is_file():
                continue
            if _is_protected_file(file_path):
                continue
            try:
                file_path.unlink()
                deleted.append(str(file_path))
                logger.info(f"Deleted derived file: {file_path}")
            except OSError as e:
                logger.warning(f"Failed to delete {file_path}: {e}")

        return deleted

    def _delete_vector_entries(self, series: str, season: str, episode: str) -> int:
        """Delete all vector store entries for this episode."""
        try:
            collection = self.vector_store_service.collection
            episode_id = f"{series}_{season}_{episode}"
            result = collection.get(where={"episode_id": episode_id})
            ids_to_delete = result.get("ids", [])
            if ids_to_delete:
                collection.delete(ids=ids_to_delete)
                logger.info(f"Deleted {len(ids_to_delete)} vector entries for {episode_id}")
                return len(ids_to_delete)
        except Exception as e:
            logger.warning(f"Error deleting vector entries for {series} {season} {episode}: {e}")
        return 0

    def _delete_db_records(self, series: str, season: str, episode: str) -> Dict[str, List[str]]:
        """Delete all DB records: progressions, orphaned arcs, character links."""
        removed_progression_ids: List[str] = []
        deleted_arc_ids: List[str] = []
        updated_arc_ids: List[str] = []

        with self.db_manager.session_scope() as session:
            progression_repo = ArcProgressionRepository(session)
            arc_repo = NarrativeArcRepository(session)
            character_repo = CharacterRepository(session)
            character_service = CharacterService(character_repo)

            from app.services.ai import LLMService

            llm_service = LLMService()
            narrative_arc_service = NarrativeArcService(
                arc_repository=arc_repo,
                progression_repository=progression_repo,
                character_service=character_service,
                llm_service=llm_service,
                vector_store_service=self.vector_store_service,
                session=session,
            )

            # Find all progressions for this episode
            target_progressions = session.exec(
                select(ArcProgression).where(
                    ArcProgression.series == series,
                    ArcProgression.season == season,
                    ArcProgression.episode == episode,
                )
            ).all()

            if not target_progressions:
                logger.info(f"No progressions found for {series} {season} {episode}")
                return {
                    "removed_progression_ids": [],
                    "deleted_arc_ids": [],
                    "updated_arc_ids": [],
                }

            # Collect affected arc IDs before deleting progressions
            affected_arc_ids: Set[str] = set()
            for progression in target_progressions:
                affected_arc_ids.add(progression.main_arc_id)

            # Delete progressions and their interfering character links
            for progression in target_progressions:
                if progression.id:
                    try:
                        progression.interfering_characters.clear()
                        progression_repo.delete(progression.id)
                        removed_progression_ids.append(progression.id)
                    except Exception as e:
                        logger.warning(f"Failed to delete progression {progression.id}: {e}")

            session.flush()

            # For each affected arc: delete if orphaned, otherwise re-embed
            for arc_id in sorted(affected_arc_ids):
                remaining_progressions = session.exec(
                    select(ArcProgression).where(ArcProgression.main_arc_id == arc_id)
                ).all()
                if not remaining_progressions:
                    try:
                        narrative_arc_service.delete_arc(arc_id)
                        deleted_arc_ids.append(arc_id)
                    except Exception as e:
                        logger.warning(f"Failed to delete arc {arc_id}: {e}")
                else:
                    try:
                        arc = arc_repo.get_by_id(arc_id)
                        if arc:
                            narrative_arc_service.update_embeddings(arc)
                            updated_arc_ids.append(arc_id)
                    except Exception as e:
                        logger.warning(f"Failed to re-embed arc {arc_id}: {e}")

        return {
            "removed_progression_ids": removed_progression_ids,
            "deleted_arc_ids": deleted_arc_ids,
            "updated_arc_ids": updated_arc_ids,
        }

    def _cleanup_character_presence(self, series: str, season: str, episode: str) -> None:
        episode_code = f"{season}{episode}"
        path_handler = PathHandler(series, season, episode, base_dir=self.base_dir)
        season_entities_path = path_handler.get_season_extracted_refined_entities_path()

        # 1. Update JSON file
        try:
            if Path(season_entities_path).exists():
                with open(season_entities_path, "r", encoding="utf-8") as f:
                    entities_data = json.load(f)

                updated_entities_data = []
                for entity_dict in entities_data:
                    presences = entity_dict.get("presence_episodes", [])
                    if episode_code in presences:
                        presences.remove(episode_code)
                        entity_dict["presence_episodes"] = presences

                    if presences:
                        updated_entities_data.append(entity_dict)

                with open(season_entities_path, "w", encoding="utf-8") as f:
                    json.dump(updated_entities_data, f, indent=2)
                logger.info(f"Cleaned up {episode_code} from {season_entities_path}")
        except Exception as e:
            logger.error(f"Error updating JSON for character presences: {e}")

        # 2. Update Database
        try:
            with self.db_manager.session_scope() as session:
                character_repo = CharacterRepository(session)
                character_service = CharacterService(character_repo)

                presences = session.exec(
                    select(CharacterEpisodePresence).where(
                        CharacterEpisodePresence.series == series,
                        CharacterEpisodePresence.episode_code == episode_code
                    )
                ).all()

                for presence in presences:
                    character_service.remove_episode_presence(presence.character_id, episode_code, series)
        except Exception as e:
            logger.error(f"Error cleaning up character presences in DB: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reset an episode's analysis artifacts")
    parser.add_argument("--series", required=True)
    parser.add_argument("--season", required=True)
    parser.add_argument("--episode", required=True)
    parser.add_argument("--base-dir", default="data")
    args = parser.parse_args()

    svc = EpisodeResetService(base_dir=args.base_dir)
    result = svc.reset_episode(args.series, args.season, args.episode)
    print(json.dumps(result, indent=2))
    sys.exit(0)