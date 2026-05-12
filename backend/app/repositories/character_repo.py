"""Character repository."""
from typing import List, Optional
from sqlmodel import select
from sqlalchemy.orm import selectinload

from app.models.narrative import Character, CharacterAppellation
from app.repositories.base import BaseRepository
from app.core.logging import setup_logging

logger = setup_logging(__name__)


class CharacterRepository(BaseRepository):
    """Repository for Character operations."""

    def get_by_entity_name(self, entity_name: str, series: str) -> Optional[Character]:
        query = select(Character).where(
            Character.entity_name == entity_name,
            Character.series == series
        ).options(
            selectinload(Character.appellations),
            selectinload(Character.main_narrative_arcs),
            selectinload(Character.interfering_progressions)
        )
        return self.session.exec(query).first()

    def get_by_appellations(self, appellations: List[str], series: str) -> List[Character]:
        if not appellations:
            return []

        query = select(Character).join(CharacterAppellation).where(
            Character.series == series,
            CharacterAppellation.appellation.in_(appellations)
        ).options(
            selectinload(Character.appellations),
            selectinload(Character.main_narrative_arcs),
            selectinload(Character.interfering_progressions)
        ).distinct()

        return self.session.exec(query).all()

    def get_character_by_appellation(self, appellation: str, series: str) -> Optional[Character]:
        query = select(Character).join(CharacterAppellation).where(
            Character.series == series,
            CharacterAppellation.appellation == appellation
        ).options(
            selectinload(Character.appellations)
        )
        return self.session.exec(query).first()

    def add(self, character: Character) -> None:
        self.session.add(character)
        self.session.flush()

    def update(self, character: Character) -> None:
        self.session.add(character)
        self.session.flush()

    def get_by_series(self, series: str) -> List[Character]:
        query = select(Character).where(Character.series == series).options(
            selectinload(Character.appellations)
        )
        return self.session.exec(query).all()

    def delete(self, character: Character) -> None:
        try:
            for appellation in character.appellations:
                self.session.delete(appellation)

            for arc in character.main_narrative_arcs:
                arc.main_characters.remove(character)

            for progression in character.interfering_progressions:
                progression.interfering_characters.remove(character)

            self.session.delete(character)
            self.session.flush()
            logger.info(f"Successfully deleted character {character.entity_name}")
        except Exception as e:
            logger.error(f"Error deleting character {character.entity_name}: {e}")
            raise