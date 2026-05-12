"""NarrativeArc repository."""
from typing import List, Optional, Dict
from sqlmodel import select, func
from sqlalchemy.orm import selectinload

from app.models.narrative import NarrativeArc
from app.repositories.base import BaseRepository
from app.core.logging import setup_logging

logger = setup_logging(__name__)


class NarrativeArcRepository(BaseRepository):
    """Repository for NarrativeArc operations."""

    def add_or_update(self, arc: NarrativeArc) -> None:
        existing_arc = self.session.get(NarrativeArc, arc.id)
        if existing_arc:
            existing_arc.title = arc.title
            existing_arc.description = arc.description
            existing_arc.arc_type = arc.arc_type
            existing_arc.series = arc.series
            logger.info(f"Updated NarrativeArc: {arc.title}")
        else:
            self.session.add(arc)
            logger.info(f"Added new NarrativeArc: {arc.title}")

    def update_fields(self, arc: NarrativeArc, updated_fields: Dict) -> None:
        for field, value in updated_fields.items():
            if hasattr(arc, field):
                setattr(arc, field, value)
                logger.debug(f"Set {field} to {value} for arc ID {arc.id}")
            else:
                logger.warning(f"Field '{field}' does not exist on NarrativeArc.")
        self.session.add(arc)

    def get_by_id(self, arc_id: str) -> Optional[NarrativeArc]:
        arc = self.session.get(NarrativeArc, arc_id)
        if arc:
            self.session.refresh(arc, ['main_characters', 'progressions'])
        return arc

    def get_by_title(self, title: str, series: str) -> Optional[NarrativeArc]:
        return self.session.query(NarrativeArc)\
            .filter(func.lower(NarrativeArc.title) == title.lower())\
            .filter(NarrativeArc.series == series)\
            .first()

    def get_all(self, series: Optional[str] = None) -> List[NarrativeArc]:
        query = select(NarrativeArc).options(
            selectinload(NarrativeArc.main_characters),
            selectinload(NarrativeArc.progressions)
        )
        if series:
            query = query.where(NarrativeArc.series == series)
        return self.session.exec(query).all()

    def delete(self, arc_id: str) -> None:
        arc = self.session.get(NarrativeArc, arc_id)
        if arc:
            self.session.delete(arc)
            logger.info(f"Deleted NarrativeArc: {arc.title}")