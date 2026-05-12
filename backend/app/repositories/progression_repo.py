"""ArcProgression repository."""
from typing import List, Optional
from sqlmodel import select
from sqlalchemy.orm import selectinload

from app.models.narrative import ArcProgression
from app.repositories.base import BaseRepository
from app.core.logging import setup_logging

logger = setup_logging(__name__)


class ArcProgressionRepository(BaseRepository):
    """Repository for ArcProgression operations."""

    def add_or_update(self, progression: ArcProgression) -> None:
        existing_progression = self.session.exec(
            select(ArcProgression).where(
                ArcProgression.main_arc_id == progression.main_arc_id,
                ArcProgression.series == progression.series,
                ArcProgression.season == progression.season,
                ArcProgression.episode == progression.episode
            )
        ).first()

        if existing_progression:
            existing_progression.content = progression.content
            existing_progression.ordinal_position = progression.ordinal_position
            logger.info(f"Updated ArcProgression in S{progression.season}E{progression.episode}")
        else:
            self.session.add(progression)
            logger.info(f"Added new ArcProgression in S{progression.season}E{progression.episode}")

    def get_by_arc_id(self, arc_id: str) -> List[ArcProgression]:
        query = select(ArcProgression).where(
            ArcProgression.main_arc_id == arc_id
        ).options(
            selectinload(ArcProgression.narrative_arc),
            selectinload(ArcProgression.interfering_characters)
        )
        return self.session.exec(query).all()

    def get_single(self, arc_id: str, series: str, season: str, episode: str) -> Optional[ArcProgression]:
        query = select(ArcProgression).where(
            ArcProgression.main_arc_id == arc_id,
            ArcProgression.series == series,
            ArcProgression.season == season,
            ArcProgression.episode == episode
        ).options(
            selectinload(ArcProgression.interfering_characters)
        )
        return self.session.exec(query).first()

    def get_by_id(self, progression_id: str) -> Optional[ArcProgression]:
        return self.session.get(ArcProgression, progression_id)

    def delete(self, progression_id: str) -> None:
        progression = self.session.get(ArcProgression, progression_id)
        if progression:
            self.session.delete(progression)
            logger.info(f"Deleted progression {progression_id}")