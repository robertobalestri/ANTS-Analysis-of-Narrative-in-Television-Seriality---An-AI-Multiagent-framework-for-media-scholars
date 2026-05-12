"""Path utilities for ANTS."""
import os
from typing import List


class PathHandler:
    """Handler for generating file paths within a series/season/episode structure."""

    def __init__(self, series: str, season: str, episode: str, base_dir: str = "data"):
        self.series = series
        self.season = season
        self.episode = episode
        self.base_dir = base_dir

    def get_raw_plot_file_path(self) -> str:
        return os.path.join(self.base_dir, self.series, self.season, self.episode,
                           f"{self.series}{self.season}{self.episode}_plot.txt")

    def get_full_dialogues_file_path(self) -> str:
        return os.path.join(self.base_dir, self.series, self.season, self.episode,
                           f"{self.series}{self.season}{self.episode}_full_dialogues.json")

    def get_simplified_plot_file_path(self) -> str:
        return os.path.join(self.base_dir, self.series, self.season, self.episode,
                           f"{self.series}{self.season}{self.episode}_plot_simplified.txt")

    def get_named_plot_file_path(self) -> str:
        return os.path.join(self.base_dir, self.series, self.season, self.episode,
                           f"{self.series}{self.season}{self.episode}_plot_named.txt")

    def get_entity_substituted_plot_file_path(self) -> str:
        return os.path.join(self.base_dir, self.series, self.season, self.episode,
                           f"{self.series}{self.season}{self.episode}_plot_entities_substituted.txt")

    def get_entity_normalized_plot_file_path(self) -> str:
        return os.path.join(self.base_dir, self.series, self.season, self.episode,
                           f"{self.series}{self.season}{self.episode}_plot_entities_normalized.txt")

    def get_semantic_segments_path(self) -> str:
        return os.path.join(self.base_dir, self.series, self.season, self.episode,
                           f"{self.series}{self.season}{self.episode}_plot_semantic_segments.json")

    def get_episode_narrative_arcs_path(self) -> str:
        return os.path.join(self.base_dir, self.series, self.season, self.episode,
                           f"{self.series}{self.season}{self.episode}_mu_agent_arcs.json")

    def get_suggested_episode_arc_path(self) -> str:
        return os.path.join(self.base_dir, self.series, self.season, self.episode,
                           f"{self.series}{self.season}{self.episode}_suggested_arcs.json")

    def get_character_entities_path(self) -> str:
        return os.path.join(self.base_dir, self.series, self.season, self.episode,
                           f"{self.series}{self.season}{self.episode}_character_entities.json")

    def get_extracted_refined_entities_path(self) -> str:
        return os.path.join(self.base_dir, self.series, self.season,
                           f"{self.series}{self.season}_extracted_refined_entities.json")

    def get_season_extracted_refined_entities_path(self) -> str:
        return self.get_extracted_refined_entities_path()

    def get_series_metadata_path(self) -> str:
        return os.path.join(self.base_dir, self.series, f"{self.series}_metadata.json")

    def get_season_metadata_path(self) -> str:
        return os.path.join(self.base_dir, self.series, self.season, f"{self.series}{self.season}_metadata.json")

    def get_episode_metadata_path(self) -> str:
        return os.path.join(self.base_dir, self.series, self.season, self.episode,
                           f"{self.series}{self.season}{self.episode}_metadata.json")


def get_episodes_in_season(season_path: str) -> List[str]:
    """Get list of episode folders in a season directory."""
    return [ep for ep in os.listdir(season_path) if os.path.isdir(os.path.join(season_path, ep))]