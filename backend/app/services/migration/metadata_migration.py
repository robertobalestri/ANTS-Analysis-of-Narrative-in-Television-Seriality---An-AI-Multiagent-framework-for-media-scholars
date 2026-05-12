import json
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy.exc import SQLAlchemyError

from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from app.models.narrative import (
    EpisodeMetadata,
    SeasonMetadata,
    SeriesMetadata,
    UnmatchedUpload,
)


def migrate_series_metadata_from_json(base_dir: str, session: Session) -> int:
    migrated_count = 0
    base_path = Path(base_dir)
    if not base_path.exists():
        return 0

    for series_dir in sorted(path for path in base_path.iterdir() if path.is_dir()):
        if _migrate_series_dir_metadata(series_dir, session):
            migrated_count += 1

    session.commit()
    return migrated_count


def _migrate_series_dir_metadata(series_dir: Path, session: Session) -> bool:
    metadata_path = series_dir / "series_metadata.json"
    if not metadata_path.exists():
        return False

    with open(metadata_path, "r", encoding="utf-8") as metadata_file:
        metadata = json.load(metadata_file)

    try:
        _upsert_series_metadata(session, series_dir.name, metadata)
        session.flush()
        metadata_path.unlink()
        return True
    except (OSError, SQLAlchemyError):
        session.rollback()
        raise


def _upsert_series_metadata(session: Session, fallback_code: str, metadata: Dict[str, Any]) -> None:
    code = metadata.get("code", fallback_code)
    series = session.exec(
        select(SeriesMetadata)
        .where(SeriesMetadata.code == code)
        .options(
            selectinload(SeriesMetadata.seasons).selectinload(SeasonMetadata.episodes),
            selectinload(SeriesMetadata.unmatched_uploads),
        )
    ).first()
    if series is None:
        series = SeriesMetadata(code=code, display_name=metadata.get("display_name", code))
        session.add(series)
        session.flush()
    else:
        series.display_name = metadata.get("display_name", code)

    series.analysis_state = metadata.get("analysis_state", "idle")
    series.analysis_error = metadata.get("analysis_error")
    series.created_at = metadata.get("created_at")
    series.updated_at = metadata.get("updated_at")
    series.seasons = [
        SeasonMetadata(
            series_code=code,
            season_code=season_code,
            episodes=[
                EpisodeMetadata(episode_code=episode_code)
                for episode_code in _normalize_episode_codes(season_data.get("episodes", []))
            ],
        )
        for season_code, season_data in metadata.get("seasons", {}).items()
    ]
    series.unmatched_uploads = [
        UnmatchedUpload(
            upload_id=upload.get("upload_id"),
            series_code=code,
            filename=upload["filename"],
            content=upload.get("content"),
            media_type=upload.get("media_type", "plot"),
        )
        for upload in metadata.get("unmatched_uploads", [])
        if upload.get("filename")
    ]
    session.add(series)


def _normalize_episode_codes(episodes: List[str]) -> List[str]:
    return sorted(set(episodes))
