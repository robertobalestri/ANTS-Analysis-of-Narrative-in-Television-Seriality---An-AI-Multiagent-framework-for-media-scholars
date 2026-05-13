"""Video service for managing episode video files."""
import os
from pathlib import Path
from typing import Optional, List

class VideoService:
    """Service for handling video file discovery and management."""
    
    VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm"}

    def __init__(self, base_dir: str = "data"):
        self.base_dir = base_dir

    def find_video_for_episode(self, series: str, season: str, episode: str) -> Optional[Path]:
        """Find the first video file in an episode directory."""
        episode_dir = Path(self.base_dir) / series.upper() / season.upper() / episode.upper()
        if not episode_dir.exists():
            return None
            
        for file in episode_dir.iterdir():
            if file.suffix.lower() in self.VIDEO_EXTENSIONS:
                return file
        return None

    def get_video_path(self, series: str, season: str, episode: str) -> Optional[str]:
        """Get the absolute path to the video file for an episode."""
        video_file = self.find_video_for_episode(series, season, episode)
        return str(video_file.absolute()) if video_file else None

    def is_video_file(self, filename: str) -> bool:
        """Check if a filename has a supported video extension."""
        return Path(filename).suffix.lower() in self.VIDEO_EXTENSIONS
