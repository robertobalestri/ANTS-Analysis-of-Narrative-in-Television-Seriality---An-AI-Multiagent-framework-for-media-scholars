"""Series ingestion service - manages series, seasons, episodes, and uploads."""
import os
import re
import uuid
from contextlib import suppress
import requests
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import selectinload
from sqlmodel import select

from app.core.logging import setup_logging
from app.core.exceptions import NotFoundError, ValidationError
from app.models.narrative import EpisodeMetadata, SeasonMetadata, SeriesMetadata, UnmatchedUpload
from app.repositories import DatabaseSessionManager
from app.services.filesystem.path_handler import PathHandler
from app.services.library.episode_status import LibraryEpisodeStatusBuilder
from app.services.library.video_service import VideoService
from app.services.migration.metadata_migration import migrate_series_metadata_from_json

logger = setup_logging(__name__)

ANALYSIS_STATES = {"idle", "ready", "running", "completed", "failed"}
AUTO_MATCH_PATTERN = re.compile(r"S(?P<season>\d{1,2})E(?P<episode>\d{1,2})", re.IGNORECASE)


class SeriesIngestionService:
    def __init__(self, base_dir: str = "data", db_manager: Optional[DatabaseSessionManager] = None):
        self.base_dir = base_dir
        self.status_builder = LibraryEpisodeStatusBuilder(base_dir=base_dir)
        self.video_service = VideoService(base_dir=base_dir)
        self.db_manager = db_manager or DatabaseSessionManager()
        self.path_handler = PathHandler("", "", "", base_dir=base_dir)

    def list_series(self) -> List[Dict[str, Any]]:
        self._ingest_legacy_metadata()
        series_entries: List[Dict[str, Any]] = []
        base_path = Path(self.base_dir)
        if not base_path.exists():
            return []

        for series_dir in sorted([path for path in base_path.iterdir() if path.is_dir()]):
            self._backfill_metadata_from_filesystem(series_dir.name)
            metadata = self._read_metadata(series_dir.name)
            status = self.get_series_status(series_dir.name)
            series_entries.append(
                {
                    "code": series_dir.name,
                    "display_name": metadata.get("display_name", series_dir.name),
                    "poster_url": metadata.get("poster_url"),
                    "analysis_state": status["analysis_state"],
                    "expected_episode_count": status["expected_episode_count"],
                    "uploaded_episode_count": status["uploaded_episode_count"],
                    "unmatched_upload_count": status["unmatched_upload_count"],
                }
            )
        return series_entries

    def create_series(self, code: str, display_name: str) -> Dict[str, Any]:
        normalized_code = self._normalize_series_code(code)
        series_path = Path(self.base_dir) / normalized_code
        series_path.mkdir(parents=True, exist_ok=True)

        metadata = self._default_metadata(normalized_code, display_name)
        existing = self._read_metadata(normalized_code)
        if existing:
            metadata.update(existing)
            metadata["display_name"] = display_name
        self._write_metadata(normalized_code, metadata)
        
        # Fetch IMDb poster if not already present
        if not metadata.get("poster_url"):
            self.fetch_and_save_poster(display_name, normalized_code)
            
        return self.get_series_status(normalized_code)

    def sync_posters(self) -> None:
        """Scan all series and fetch posters if missing."""
        series_list = self.list_series()
        for series in series_list:
            if not series.get("poster_url"):
                logger.info(f"Series {series['code']} is missing a poster. Fetching...")
                self.fetch_and_save_poster(series["display_name"], series["code"])

    def fetch_and_save_poster(self, series_name: str, series_code: str) -> Optional[str]:
        """Fetch poster from IMDb API and save it locally."""
        try:
            logger.info(f"Fetching IMDb poster for {series_name}...")
            # Use the search API
            search_url = f"https://api.imdbapi.dev/search/titles?query={requests.utils.quote(series_name)}"
            response = requests.get(search_url, headers={"accept": "application/json"}, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            titles = data.get("titles", [])
            if not titles:
                logger.warning(f"No IMDb titles found for {series_name}")
                return None
                
            first_title = titles[0]
            image_info = first_title.get("primaryImage")
            if not image_info or not image_info.get("url"):
                logger.warning(f"No image URL found for {series_name}")
                return None
                
            image_url = image_info["url"]
            
            # Download the image
            img_response = requests.get(image_url, timeout=10)
            img_response.raise_for_status()
            
            # Save locally
            series_path = Path(self.base_dir) / series_code
            series_path.mkdir(parents=True, exist_ok=True)
            
            poster_filename = f"poster_{series_code.lower()}.jpg"
            poster_path = series_path / poster_filename
            
            with open(poster_path, "wb") as f:
                f.write(img_response.content)
                
            # Update metadata in DB
            relative_url = f"/api/library/series/{series_code}/poster"
            with self.db_manager.session_scope() as session:
                from sqlmodel import select
                series_obj = session.exec(select(SeriesMetadata).where(SeriesMetadata.code == series_code)).first()
                if series_obj:
                    series_obj.poster_url = relative_url
                    session.add(series_obj)
                    session.commit()
            
            # Update metadata in JSON file
            metadata = self._read_metadata(series_code)
            metadata["poster_url"] = relative_url
            self._write_metadata(series_code, metadata)
                    
            logger.info(f"Saved poster for {series_name} to {poster_path}")
            return relative_url
            
        except Exception as e:
            logger.error(f"Error fetching IMDb poster for {series_name}: {e}")
            return None

    def create_seasons(self, series_code: str, seasons: List[str]) -> Dict[str, Any]:
        normalized_series = self._normalize_series_code(series_code)
        metadata = self._read_metadata(normalized_series)
        for season in seasons:
            season_code = self._normalize_season(season)
            season_path = Path(self.base_dir) / normalized_series / season_code
            season_path.mkdir(parents=True, exist_ok=True)
            metadata.setdefault("seasons", {}).setdefault(season_code, {"episodes": []})
        self._write_metadata(normalized_series, metadata)
        return self.get_series_status(normalized_series)

    def create_episodes(self, series_code: str, season_code: str, episodes: List[str]) -> Dict[str, Any]:
        normalized_series = self._normalize_series_code(series_code)
        normalized_season = self._normalize_season(season_code)
        metadata = self._read_metadata(normalized_series)
        season_entry = metadata.setdefault("seasons", {}).setdefault(normalized_season, {"episodes": []})

        known_episodes = set(season_entry.get("episodes", []))
        for episode in episodes:
            episode_code = self._normalize_episode(episode)
            episode_path = Path(self.base_dir) / normalized_series / normalized_season / episode_code
            episode_path.mkdir(parents=True, exist_ok=True)
            known_episodes.add(episode_code)
        season_entry["episodes"] = sorted(known_episodes)
        self._write_metadata(normalized_series, metadata)
        return self.get_series_status(normalized_series)

    def register_uploads(self, series_code: str, uploads: List[Dict[str, str]]) -> Dict[str, Any]:
        normalized_series = self._normalize_series_code(series_code)
        metadata = self._read_metadata(normalized_series)
        unmatched_uploads = metadata.setdefault("unmatched_uploads", [])
        auto_matched: List[Dict[str, str]] = []

        written_plot_paths: List[str] = []
        try:
            for upload in uploads:
                filename = upload["filename"]
                content = upload["content"]
                matched = self._parse_upload_target(filename)
                if matched:
                    saved = self.save_plot_file(normalized_series, matched["season"], matched["episode"], content)
                    written_plot_paths.append(saved["path"])
                    auto_matched.append(saved)
                    self._ensure_episode_metadata(metadata, matched["season"], matched["episode"])
                else:
                    unmatched_uploads.append({
                        "upload_id": self._build_upload_id(filename),
                        "filename": filename,
                        "content": content,
                    })

            metadata["analysis_state"] = self._derive_analysis_state(metadata)
            self._write_metadata(normalized_series, metadata)
        except Exception:
            self._rollback_plot_files(written_plot_paths)
            raise
        status = self.get_series_status(normalized_series)
        status["auto_matched_uploads"] = auto_matched
        status["unmatched_uploads"] = [
            {"upload_id": item["upload_id"], "filename": item["filename"]}
            for item in self._read_metadata(normalized_series).get("unmatched_uploads", [])
        ]
        return status

    def assign_upload(self, series_code: str, upload_id: str, season_code: str, episode_code: str) -> Dict[str, Any]:
        normalized_series = self._normalize_series_code(series_code)
        normalized_season = self._normalize_season(season_code)
        normalized_episode = self._normalize_episode(episode_code)
        metadata = self._read_metadata(normalized_series)
        uploads = metadata.get("unmatched_uploads", [])

        matched_upload: Optional[Dict[str, str]] = None
        remaining_uploads: List[Dict[str, str]] = []
        for upload in uploads:
            if upload["upload_id"] == upload_id:
                matched_upload = upload
            else:
                remaining_uploads.append(upload)

        if matched_upload is None:
            raise NotFoundError(f"Upload {upload_id} not found")

        saved_plot = self.save_plot_file(normalized_series, normalized_season, normalized_episode, matched_upload["content"])
        try:
            metadata["unmatched_uploads"] = remaining_uploads
            self._ensure_episode_metadata(metadata, normalized_season, normalized_episode)
            metadata["analysis_state"] = self._derive_analysis_state(metadata)
            self._write_metadata(normalized_series, metadata)
        except Exception:
            self._rollback_plot_files([saved_plot["path"]])
            raise
        return self.get_series_status(normalized_series)

    def save_plot_file(self, series_code: str, season_code: str, episode_code: str, content: str) -> Dict[str, str]:
        normalized_series, normalized_season, normalized_episode, episode_path = self._normalize_episode_target(
            series_code,
            season_code,
            episode_code,
        )
        path_handler = PathHandler(normalized_series, normalized_season, normalized_episode, base_dir=self.base_dir)
        plot_path = Path(path_handler.get_raw_plot_file_path())
        
        with open(plot_path, "w", encoding="utf-8") as plot_file:
            plot_file.write(content)
        return {
            "season": normalized_season,
            "episode": normalized_episode,
            "path": plot_path,
        }

    def save_episode_source_file(self, series_code: str, season_code: str, episode_code: str, filename: str, content: str) -> Dict[str, str]:
        normalized_series, normalized_season, normalized_episode, episode_path = self._normalize_episode_target(
            series_code,
            season_code,
            episode_code,
        )

        lowered = filename.lower()
        if lowered.endswith('.txt'):
            saved = self.save_plot_file(normalized_series, normalized_season, normalized_episode, content)
            saved["source_type"] = "plot"
            return saved

        if lowered.endswith('.srt'):
            srt_path = Path(path_handler.get_srt_file_path())
            with open(srt_path, "w", encoding="utf-8") as srt_file:
                srt_file.write(content)
            return {
                "season": normalized_season,
                "episode": normalized_episode,
                "path": str(srt_path),
                "source_type": "srt",
            }

        if self.video_service.is_video_file(filename):
            extension = Path(filename).suffix.lower()
            video_path = Path(path_handler.get_video_file_path(extension))
            # content can be str (if from text decoding) or bytes. In library.py it's decoded as utf-8.
            # For video, we need to handle binary. 
            # Note: library.py calls this with text_content. We need to fix library.py too.
            mode = "wb" if isinstance(content, bytes) else "w"
            encoding = None if isinstance(content, bytes) else "utf-8"
            with open(video_path, mode, encoding=encoding) as video_file:
                video_file.write(content)
            return {
                "season": normalized_season,
                "episode": normalized_episode,
                "path": str(video_path),
                "source_type": "video",
            }

        raise ValidationError("Only plot .txt, subtitle .srt, or video files are supported")

    def delete_episode_file(self, series_code: str, season_code: str, episode_code: str, file_type: str) -> Dict[str, Any]:
        normalized_series, normalized_season, normalized_episode, episode_path = self._normalize_episode_target(
            series_code,
            season_code,
            episode_code,
        )
        path_handler = PathHandler(normalized_series, normalized_season, normalized_episode, base_dir=self.base_dir)
        
        if file_type == "plot":
            file_path = Path(path_handler.get_raw_plot_file_path())
        elif file_type == "srt":
            file_path = self.status_builder.find_srt_path(episode_path)
        elif file_type == "video":
            file_path = self.video_service.find_video_for_episode(normalized_series, normalized_season, normalized_episode)
        else:
            raise ValidationError(f"Invalid file type for deletion: {file_type}")

        if file_path and file_path.exists():
            os.remove(file_path)
            logger.info(f"Deleted {file_type} file for {normalized_series} {normalized_season} {normalized_episode}")
            
        return self.get_series_status(normalized_series)

    def get_episode_plot_content(self, series_code: str, season_code: str, episode_code: str) -> Optional[str]:
        normalized_series, normalized_season, normalized_episode, _ = self._normalize_episode_target(
            series_code,
            season_code,
            episode_code,
        )
        path_handler = PathHandler(normalized_series, normalized_season, normalized_episode, base_dir=self.base_dir)
        plot_path = Path(path_handler.get_raw_plot_file_path())
        
        if plot_path.exists():
            from app.utils.text import load_text
            return load_text(str(plot_path))
        return None

    def get_series_status(self, series_code: str) -> Dict[str, Any]:
        self._ingest_legacy_metadata()
        normalized_series = self._normalize_series_code(series_code)
        self._backfill_metadata_from_filesystem(normalized_series)
        metadata = self._read_metadata(normalized_series)
        seasons = metadata.get("seasons", {})
        expected_episode_count = sum(len(season.get("episodes", [])) for season in seasons.values())
        uploaded_episode_count = 0
        episodes: List[Dict[str, Any]] = []

        for season_code in sorted(seasons.keys()):
            season = seasons[season_code]
            for episode_code in sorted(season.get("episodes", [])):
                episode_status = self.status_builder.build(
                    normalized_series,
                    season_code,
                    episode_code,
                    0,
                )
                if episode_status["has_plot_file"]:
                    uploaded_episode_count += 1
                episodes.append({
                    "season": season_code,
                    "episode": episode_code,
                    "has_plot": episode_status["has_plot_file"],
                })

        analysis_state = metadata.get("analysis_state", "idle")
        if analysis_state not in ANALYSIS_STATES:
            analysis_state = "idle"

        return {
            "code": normalized_series,
            "display_name": metadata.get("display_name", normalized_series),
            "analysis_state": analysis_state,
            "expected_episode_count": expected_episode_count,
            "uploaded_episode_count": uploaded_episode_count,
            "unmatched_upload_count": len(metadata.get("unmatched_uploads", [])),
            "episodes": episodes,
            "unmatched_uploads": [
                {"upload_id": item["upload_id"], "filename": item["filename"]}
                for item in metadata.get("unmatched_uploads", [])
            ],
        }

    def set_analysis_state(self, series_code: str, state: str, error: Optional[str] = None) -> None:
        if state not in ANALYSIS_STATES:
            raise ValidationError(f"Invalid analysis state: {state}")
        normalized_series = self._normalize_series_code(series_code)
        metadata = self._read_metadata(normalized_series)
        metadata["analysis_state"] = state
        if error:
            metadata["analysis_error"] = error
        else:
            metadata.pop("analysis_error", None)
        self._write_metadata(normalized_series, metadata)

    def list_expected_episodes(self, series_code: str) -> List[Dict[str, str]]:
        self._ingest_legacy_metadata()
        normalized_series = self._normalize_series_code(series_code)
        self._backfill_metadata_from_filesystem(normalized_series)
        metadata = self._read_metadata(normalized_series)
        episodes: List[Dict[str, str]] = []
        for season_code in sorted(metadata.get("seasons", {}).keys()):
            for episode_code in sorted(metadata["seasons"][season_code].get("episodes", [])):
                episodes.append({"season": season_code, "episode": episode_code})
        return episodes

    def _ingest_legacy_metadata(self) -> None:
        with self.db_manager.session_scope() as session:
            migrate_series_metadata_from_json(self.base_dir, session)

    def _backfill_metadata_from_filesystem(self, series_code: str) -> None:
        normalized_series = self._normalize_series_code(series_code)
        series_path = Path(self.base_dir) / normalized_series
        if not series_path.exists():
            return

        metadata = self._read_metadata(normalized_series)
        seasons = metadata.setdefault("seasons", {})
        changed = False

        for season_dir in sorted(path for path in series_path.iterdir() if path.is_dir() and path.name.startswith("S")):
            normalized_season = self._normalize_season(season_dir.name)
            season_entry = seasons.setdefault(normalized_season, {"episodes": []})
            known_episodes = set(season_entry.get("episodes", []))

            for episode_dir in sorted(path for path in season_dir.iterdir() if path.is_dir() and path.name.startswith("E")):
                normalized_episode = self._normalize_episode(episode_dir.name)
                if normalized_episode not in known_episodes:
                    known_episodes.add(normalized_episode)
                    changed = True

            normalized_episodes = sorted(known_episodes)
            if normalized_episodes != season_entry.get("episodes", []):
                season_entry["episodes"] = normalized_episodes
                changed = True

        if changed:
            self._write_metadata(normalized_series, metadata)

    def _read_metadata(self, series_code: str) -> Dict[str, Any]:
        normalized_series = self._normalize_series_code(series_code)
        with self.db_manager.session_scope() as session:
            series = session.exec(
                select(SeriesMetadata)
                .where(SeriesMetadata.code == normalized_series)
                .options(
                    selectinload(SeriesMetadata.seasons).selectinload(SeasonMetadata.episodes),
                    selectinload(SeriesMetadata.unmatched_uploads),
                )
            ).first()
            if series is None:
                return self._default_metadata(normalized_series, normalized_series)

            return {
                "code": series.code,
                "display_name": series.display_name,
                "seasons": {
                    season.season_code: {"episodes": sorted(episode.episode_code for episode in season.episodes)}
                    for season in series.seasons
                },
                "unmatched_uploads": [
                    {
                        "upload_id": upload.upload_id or str(upload.id),
                        "filename": upload.filename,
                        "content": upload.content,
                        "media_type": upload.media_type,
                    }
                    for upload in series.unmatched_uploads
                ],
                "analysis_state": series.analysis_state,
                "analysis_error": series.analysis_error,
                "poster_url": series.poster_url,
                "created_at": series.created_at,
                "updated_at": series.updated_at,
            }

    def _write_metadata(self, series_code: str, metadata: Dict[str, Any]) -> None:
        normalized_series = self._normalize_series_code(series_code)
        with self.db_manager.session_scope() as session:
            series = session.exec(
                select(SeriesMetadata)
                .where(SeriesMetadata.code == normalized_series)
                .options(
                    selectinload(SeriesMetadata.seasons).selectinload(SeasonMetadata.episodes),
                    selectinload(SeriesMetadata.unmatched_uploads),
                )
            ).first()
            if series is None:
                series = SeriesMetadata(code=normalized_series, display_name=metadata.get("display_name", normalized_series))
                session.add(series)
                session.flush()
            else:
                series.display_name = metadata.get("display_name", normalized_series)

            series.analysis_state = metadata.get("analysis_state", "idle")
            series.analysis_error = metadata.get("analysis_error")
            series.created_at = metadata.get("created_at")
            series.updated_at = metadata.get("updated_at")
            series.poster_url = metadata.get("poster_url")
            series.seasons = []
            series.unmatched_uploads = []
            session.flush()
            series.seasons = [
                SeasonMetadata(
                    series_code=normalized_series,
                    season_code=season_code,
                    episodes=[
                        EpisodeMetadata(episode_code=episode_code)
                        for episode_code in sorted(set(season_data.get("episodes", [])))
                    ],
                )
                for season_code, season_data in metadata.get("seasons", {}).items()
            ]
            series.unmatched_uploads = [
                UnmatchedUpload(
                    upload_id=upload.get("upload_id"),
                    series_code=normalized_series,
                    filename=upload["filename"],
                    content=upload.get("content"),
                    media_type=upload.get("media_type", "plot"),
                )
                for upload in metadata.get("unmatched_uploads", [])
                if upload.get("filename")
            ]
            session.add(series)

    def _default_metadata(self, code: str, display_name: str) -> Dict[str, Any]:
        return {
            "code": code,
            "display_name": display_name,
            "seasons": {},
            "unmatched_uploads": [],
            "analysis_state": "idle",
        }

    def _normalize_series_code(self, code: str) -> str:
        normalized = re.sub(r"[^A-Za-z0-9_-]", "", code.strip().upper())
        if not normalized:
            raise ValidationError("Series code cannot be empty")
        return normalized

    def _normalize_season(self, season: str) -> str:
        season_num = int(str(season).upper().replace("S", ""))
        return f"S{season_num:02d}"

    def _normalize_episode(self, episode: str) -> str:
        episode_num = int(str(episode).upper().replace("E", ""))
        return f"E{episode_num:02d}"

    def _parse_upload_target(self, filename: str) -> Optional[Dict[str, str]]:
        match = AUTO_MATCH_PATTERN.search(filename)
        if not match:
            return None
        return {
            "season": self._normalize_season(match.group("season")),
            "episode": self._normalize_episode(match.group("episode")),
        }

    def _normalize_episode_target(self, series_code: str, season_code: str, episode_code: str) -> tuple[str, str, str, Path]:
        normalized_series = self._normalize_series_code(series_code)
        normalized_season = self._normalize_season(season_code)
        normalized_episode = self._normalize_episode(episode_code)
        episode_path = Path(self.base_dir) / normalized_series / normalized_season / normalized_episode
        episode_path.mkdir(parents=True, exist_ok=True)
        return normalized_series, normalized_season, normalized_episode, episode_path

    def _build_upload_id(self, filename: str) -> str:
        stem = Path(filename).stem.lower()
        cleaned = re.sub(r"[^a-z0-9]+", "-", stem).strip("-") or "upload"
        return f"{cleaned}-{uuid.uuid4().hex[:8]}"

    def _rollback_plot_files(self, plot_paths: List[str]) -> None:
        for plot_path in plot_paths:
            with suppress(OSError):
                os.remove(plot_path)

    def _ensure_episode_metadata(self, metadata: Dict[str, Any], season_code: str, episode_code: str) -> None:
        season_entry = metadata.setdefault("seasons", {}).setdefault(season_code, {"episodes": []})
        if episode_code not in season_entry["episodes"]:
            season_entry["episodes"] = sorted([*season_entry["episodes"], episode_code])

    def _derive_analysis_state(self, metadata: Dict[str, Any]) -> str:
        expected_episode_count = sum(len(season.get("episodes", [])) for season in metadata.get("seasons", {}).values())
        unmatched_count = len(metadata.get("unmatched_uploads", []))
        uploaded_episode_count = 0
        for season_code, season in metadata.get("seasons", {}).items():
            for episode_code in season.get("episodes", []):
                episode_plot_path = Path(self.base_dir) / metadata["code"] / season_code / episode_code / "plot.txt"
                if episode_plot_path.exists():
                    uploaded_episode_count += 1
        if expected_episode_count and uploaded_episode_count == expected_episode_count and unmatched_count == 0:
            return "ready"
        return metadata.get("analysis_state", "idle")