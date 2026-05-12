"""Character service for ANTS."""
from sqlite3 import IntegrityError
from typing import List, Optional, Union

from app.models.narrative import Character, CharacterAppellation, CharacterEpisodePresence, NarrativeArc, ArcProgression
from app.repositories import CharacterRepository
from app.core.logging import setup_logging

logger = setup_logging(__name__)


class CharacterService:
    """Service to manage character-related operations."""

    def __init__(self, character_repository: CharacterRepository):
        self.character_repository = character_repository

    def add_or_update_character(self, entity_name: str, best_appellation: str, appellations: List[str], series: str, episode_code: str) -> Optional[Character]:
        """Add a new character or update an existing one."""
        if len(entity_name.strip()) <= 1:
            logger.warning(f"Skipping invalid entity name: '{entity_name}'")
            return None

        try:
            normalized_entity_name = self._normalize_name(entity_name)

            validated_appellations = set()
            for appellation in appellations:
                if appellation and len(appellation.strip()) > 1:
                    validated_appellations.add(appellation.strip())

            if best_appellation and len(best_appellation.strip()) > 1:
                validated_appellations.add(best_appellation.strip())
            elif validated_appellations:
                best_appellation = next(iter(validated_appellations))
            else:
                logger.warning(f"No valid appellations found for entity: {entity_name}")
                return None

            existing_character = self.character_repository.get_by_entity_name(normalized_entity_name, series)

            if not existing_character:
                for appellation in validated_appellations:
                    existing_character = self.character_repository.get_character_by_appellation(appellation, series)
                    if existing_character:
                        break

            if existing_character:
                existing_character.best_appellation = best_appellation

                existing_app_set = {app.appellation for app in existing_character.appellations}

                for appellation in validated_appellations:
                    if appellation in existing_app_set:
                        continue

                    other_character = self.character_repository.get_character_by_appellation(appellation, series)
                    if other_character and other_character.entity_name != existing_character.entity_name:
                        logger.warning(f"Appellation '{appellation}' is already used by character '{other_character.entity_name}', skipping.")
                        continue

                    new_appellation = CharacterAppellation(
                        appellation=appellation,
                        character_id=existing_character.entity_name
                    )
                    existing_character.appellations.append(new_appellation)

                existing_episodes = {ep.episode_code for ep in existing_character.presence_episodes}
                if episode_code not in existing_episodes:
                    existing_character.presence_episodes.append(
                        CharacterEpisodePresence(
                            character_id=existing_character.entity_name,
                            episode_code=episode_code,
                            series=series
                        )
                    )

                self.character_repository.update(existing_character)
                logger.info(f"Updated existing character: {existing_character.entity_name}")
                return existing_character
            else:
                new_character = Character(
                    entity_name=normalized_entity_name,
                    best_appellation=best_appellation,
                    series=series
                )

                for appellation in validated_appellations:
                    existing_char = self.character_repository.get_character_by_appellation(appellation, series)
                    if existing_char:
                        logger.warning(f"Appellation '{appellation}' is already used by character '{existing_char.entity_name}', skipping.")
                        continue

                    new_appellation = CharacterAppellation(
                        appellation=appellation,
                        character_id=new_character.entity_name
                    )
                    new_character.appellations.append(new_appellation)

                if not new_character.appellations:
                    logger.warning(f"No valid appellations for character: {entity_name}")
                    return None

                new_character.presence_episodes.append(
                    CharacterEpisodePresence(
                        character_id=new_character.entity_name,
                        episode_code=episode_code,
                        series=series
                    )
                )

                self.character_repository.add(new_character)
                logger.info(f"Added new character: {new_character.entity_name}")
                return new_character

        except IntegrityError as e:
            logger.error(f"Database integrity error when processing character {entity_name}: {e}")
            self.character_repository.session.rollback()
            raise
        except Exception as e:
            logger.error(f"Unexpected error when processing character {entity_name}: {e}")
            self.character_repository.session.rollback()
            raise

    def get_characters_by_appellations(self, appellations: List[str], series: str) -> List[Character]:
        """Get characters by matching their appellations."""
        cleaned_appellations = []
        for appellation in appellations:
            if isinstance(appellation, str):
                if ';' in appellation:
                    cleaned_appellations.extend([
                        name.strip()
                        for name in appellation.split(';')
                        if name.strip()
                    ])
                else:
                    cleaned_appellations.append(appellation.strip())

        characters = self.character_repository.get_by_appellations(cleaned_appellations, series)

        if not characters:
            logger.warning(f"No characters found for appellations: {cleaned_appellations}")
        else:
            logger.info(f"Found {len(characters)} characters for appellations: {cleaned_appellations}")

        return characters

    def link_characters_to_arc(self, characters: List[Character], arc: Optional[NarrativeArc]):
        if not arc:
            return

        unique_input = {c.entity_name: c for c in characters}

        existing_ids = {c.entity_name for c in arc.main_characters}
        new_characters = [c for name, c in unique_input.items() if name not in existing_ids]

        if new_characters:
            arc.main_characters.extend(new_characters)
            for character in new_characters:
                if arc not in character.main_narrative_arcs:
                    character.main_narrative_arcs.append(arc)
            logger.info(f"Linked {len(new_characters)} characters to arc '{arc.title}'")

    def link_characters_to_progression(self, characters: List[Character], progression: ArcProgression):
        unique_input = {c.entity_name: c for c in characters}

        existing_ids = {c.entity_name for c in progression.interfering_characters}
        new_characters = [c for name, c in unique_input.items() if name not in existing_ids]

        if new_characters:
            progression.interfering_characters.extend(new_characters)
            for character in new_characters:
                if progression not in character.interfering_progressions:
                    character.interfering_progressions.append(progression)
            logger.info(f"Linked {len(new_characters)} characters to progression in S{progression.season}E{progression.episode}")

    def delete_character(self, entity_name: str, series: str) -> bool:
        """Delete a character and update all related arcs and progressions."""
        try:
            character = self.character_repository.get_by_entity_name(entity_name, series)
            if not character:
                return False

            for arc in character.main_narrative_arcs:
                arc.main_characters.remove(character)

            for progression in character.interfering_progressions:
                progression.interfering_characters.remove(character)

            self.character_repository.delete(character)
            return True

        except Exception as e:
            logger.error(f"Error deleting character {entity_name}: {e}")
            raise

    def remove_episode_presence(self, entity_name: str, episode_code: str, series: str) -> bool:
        """Remove a character's presence from a specific episode."""
        try:
            character = self.character_repository.get_by_entity_name(entity_name, series)
            if not character:
                return False

            presence_to_remove = next(
                (p for p in character.presence_episodes if p.episode_code == episode_code),
                None
            )

            if presence_to_remove:
                character.presence_episodes.remove(presence_to_remove)

                if not character.presence_episodes:
                    logger.info(f"Character {entity_name} has no more appearances. Deleting character.")
                    return self.delete_character(entity_name, series)

                self.character_repository.update(character)
                return True

            return False

        except Exception as e:
            logger.error(f"Error removing episode presence for character {entity_name} in {episode_code}: {e}")
            raise

    def merge_characters(
        self,
        character1_id: str,
        character2_id: str,
        series: str,
        keep_character: str = 'character1'
    ) -> bool:
        """Merge two characters, keeping the data from the specified character."""
        char1 = self.character_repository.get_by_entity_name(character1_id, series)
        char2 = self.character_repository.get_by_entity_name(character2_id, series)

        if not char1 or not char2:
            return False

        kept_char = char1 if keep_character == 'character1' else char2
        merged_char = char2 if keep_character == 'character1' else char1

        existing_appellations = {app.appellation for app in kept_char.appellations}
        for app in merged_char.appellations:
            if app.appellation not in existing_appellations:
                kept_char.appellations.append(
                    CharacterAppellation(
                        appellation=app.appellation,
                        character_id=kept_char.entity_name
                    )
                )
                existing_appellations.add(app.appellation)

        for arc in merged_char.main_narrative_arcs:
            if kept_char not in arc.main_characters:
                arc.main_characters.append(kept_char)

        for prog in merged_char.interfering_progressions:
            if kept_char not in prog.interfering_characters:
                prog.interfering_characters.append(kept_char)

        self.character_repository.delete(merged_char)

        return True

    def _normalize_name(self, name: str) -> str:
        """Helper method to normalize character names."""
        return name.lower().replace(' ', '_')

    def add_appellation_to_character(self, entity_name: str, appellation: str, series: str) -> Optional[Character]:
        """Add an appellation to an existing character."""
        character = self.character_repository.get_by_entity_name(entity_name, series)
        if not character:
            logger.warning(f"Character {entity_name} not found in series {series}")
            return None

        if any(app.appellation == appellation for app in character.appellations):
            return character

        new_app = CharacterAppellation(appellation=appellation, character_id=entity_name)
        character.appellations.append(new_app)
        self.character_repository.update(character)
        logger.info(f"Added appellation '{appellation}' to character '{entity_name}'")
        return character