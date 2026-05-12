from pathlib import Path
from typing import Any, Dict, Optional

from app.services.filesystem.path_handler import PathHandler


class LibraryEpisodeStatusBuilder:
    def __init__(self, base_dir: str = "data"):
        self.base_dir = base_dir

    def build(
        self,
        series_code: str,
        season_code: str,
        episode_code: str,
        progression_count: int,
        db_status: Optional[str] = None,
    ) -> Dict[str, Any]:
        episode_dir = Path(self.base_dir) / series_code / season_code / episode_code
        path_handler = PathHandler(series_code, season_code, episode_code, base_dir=self.base_dir)

        plot_path = Path(path_handler.get_raw_plot_file_path())
        full_dialogues_path = Path(path_handler.get_full_dialogues_file_path())
        srt_path = self.find_srt_path(episode_dir)
        has_analysis_artifacts = Path(path_handler.get_semantic_segments_path()).exists() or Path(path_handler.get_suggested_episode_arc_path()).exists()

        # Use DB status as authoritative if set, otherwise compute from files
        if db_status in ('completed', 'error', 'pending', 'not_processed', 'missing_files'):
            analysis_status = db_status
        elif progression_count > 0 and plot_path.exists():
            analysis_status = "completed"
        elif progression_count > 0 and not plot_path.exists():
            analysis_status = "error"
        elif plot_path.exists() or srt_path is not None:
            analysis_status = "pending"
        else:
            analysis_status = "missing_files"

        return {
            "series": series_code,
            "season": season_code,
            "episode": episode_code,
            "has_plot_file": plot_path.exists(),
            "has_srt_file": srt_path is not None,
            "has_dialogue_json": full_dialogues_path.exists(),
            "has_analysis_artifacts": has_analysis_artifacts,
            "progression_count": progression_count,
            "analysis_status": analysis_status,
        }

    def find_srt_path(self, episode_dir: Path) -> Path | None:
        if not episode_dir.exists():
            return None
        srt_files = sorted(episode_dir.glob("*.srt"))
        return srt_files[0] if srt_files else None
