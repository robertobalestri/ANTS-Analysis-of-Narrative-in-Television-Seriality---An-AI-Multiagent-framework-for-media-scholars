"""Narrative arc service for ANTS."""
from typing import List, Optional, Dict, Union
from langchain_core.documents import Document
import uuid
from contextlib import contextmanager
from sqlmodel import Session

from app.models.narrative import NarrativeArc, ArcProgression, Character
from app.repositories import NarrativeArcRepository, ArcProgressionRepository
from app.services.ai import LLMService, VectorStoreService
from app.services.narrative.character import CharacterService
from app.services.narrative.progression import ArcProgressionService
from app.core.logging import setup_logging
from app.core.exceptions import NotFoundError

logger = setup_logging(__name__)


class NarrativeArcService:
    """Service to manage narrative arcs."""

    DEFAULT_SIMILARITY_THRESHOLD = 0.35

    def __init__(
        self,
        arc_repository: NarrativeArcRepository,
        progression_repository: ArcProgressionRepository,
        character_service: CharacterService,
        llm_service: LLMService,
        vector_store_service: VectorStoreService,
        session: Session,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD
    ):
        self.arc_repository = arc_repository
        self.progression_service = ArcProgressionService(progression_repository, character_service)
        self.character_service = character_service
        self.llm_service = llm_service
        self.vector_store_service = vector_store_service
        self.session = session
        self.similarity_threshold = similarity_threshold

    @contextmanager
    def transaction(self):
        """
        Provide a transactional scope around a series of operations.
        
        This context manager ensures that all database operations within the 'with' block
        are treated as a single atomic unit. If any operation fails, the entire transaction
        is rolled back to maintain data integrity.
        
        Usage:
            with self.transaction():
                self.arc_repository.add_or_update(arc)
                self.progression_service.add_or_update_progression(...)
        """
        try:
            yield
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            logger.error(f"Transaction rollback due to: {e}")
            raise

    def merge_arcs(
        self,
        arc_id_1: str,
        arc_id_2: str,
        merged_title: str,
        merged_description: str,
        merged_arc_type: str,
        main_characters: List[str],
        progression_mappings: List[Dict[str, Union[str, List[str]]]]
    ) -> Optional[NarrativeArc]:
        """Merge two arcs into a new one."""
        with self.transaction():
            try:
                arc1 = self.arc_repository.get_by_id(arc_id_1)
                arc2 = self.arc_repository.get_by_id(arc_id_2)

                if not arc1 or not arc2:
                    raise NotFoundError(f"One or both arcs not found: {arc_id_1}, {arc_id_2}")

                logger.info(f"Starting merge of arcs: '{arc1.title}' and '{arc2.title}'")

                self.vector_store_service.delete_documents_by_arc(arc_id_1)
                self.vector_store_service.delete_documents_by_arc(arc_id_2)

                arc1.title = merged_title
                arc1.description = merged_description
                arc1.arc_type = merged_arc_type

                characters = self.character_service.get_characters_by_appellations(
                    main_characters,
                    arc1.series
                )
                arc1.main_characters = characters

                arc1.progressions = []

                for mapping in progression_mappings:
                    if mapping['content'].strip():
                        progression = ArcProgression(
                            id=str(uuid.uuid4()),
                            content=mapping['content'],
                            series=arc1.series,
                            season=mapping['season'],
                            episode=mapping['episode'],
                            main_arc_id=arc1.id
                        )

                        if mapping.get('interfering_characters'):
                            interfering_chars = self.character_service.get_characters_by_appellations(
                                mapping['interfering_characters'],
                                arc1.series
                            )
                            if interfering_chars:
                                self.character_service.link_characters_to_progression(
                                    interfering_chars,
                                    progression
                                )

                        self.progression_service.add_or_update_progression(
                            arc=arc1,
                            progression=progression,
                            series=arc1.series,
                            season=mapping['season'],
                            episode=mapping['episode']
                        )

                self.arc_repository.add_or_update(arc1)

                self.progression_service.resequence_ordinal_positions(arc1.id)

                self.update_embeddings(arc1)

                self.arc_repository.delete(arc_id_2)

                logger.info(f"Successfully merged arcs into '{arc1.title}'")
                return arc1

            except NotFoundError as e:
                logger.error(f"Not found error during merge: {e}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error merging arcs: {e}")
                raise

    def add_arc(
        self,
        arc_data: Dict,
        series: str,
        season: str,
        episode: str
    ) -> NarrativeArc:
        """Add a new narrative arc with its first progression."""
        with self.transaction():
            try:
                arc = self._construct_narrative_arc(arc_data, series)
                
                main_char_names = [n.strip() for n in arc_data.get('main_characters', '').split(';') if n.strip()]
                if main_char_names:
                    characters = self.character_service.get_characters_by_appellations(main_char_names, series)
                    if characters:
                        self.character_service.link_characters_to_arc(characters, arc)

                self.arc_repository.add_or_update(arc)
                self.session.flush()

                self._handle_progressions(arc, arc_data, series, season, episode)

                self.update_embeddings(arc)
                
                logger.info(f"Added new arc '{arc.title}' in {season}{episode}")
                return arc

            except Exception as e:
                logger.error(f"Error adding arc: {e}")
                raise

    def _construct_narrative_arc(self, arc_data: Dict, series: str) -> NarrativeArc:
        """Helper method to construct a NarrativeArc object from arc_data."""
        return NarrativeArc(
            id=str(uuid.uuid4()),
            title=arc_data['title'].strip().title(),
            arc_type=arc_data.get('arc_type', 'default_type'),
            description=arc_data['description'],
            series=series
        )

    def _handle_progressions(
        self,
        arc: NarrativeArc,
        arc_data: Dict,
        series: str,
        season: str,
        episode: str
    ):
        """Handle adding or updating arc progressions."""
        progression_data = arc_data.get('single_episode_progression_string')
        if progression_data:
            # Calculate ordinal position based on existing progressions for this episode
            current_ep_progressions = [p for p in arc.progressions if p.season == season and p.episode == episode]
            ordinal_position = len(current_ep_progressions) + 1

            progression = ArcProgression(
                id=str(uuid.uuid4()),
                content=progression_data,
                series=series,
                season=season,
                episode=episode,
                main_arc_id=arc.id,
                ordinal_position=ordinal_position
            )

            self.session.add(progression)
            self.session.flush()

            if interfering_chars := arc_data.get('interfering_episode_characters'):
                interfering_names = [
                    name.strip()
                    for name in interfering_chars.split(';')
                    if name.strip()
                ]
                interfering_characters = self.character_service.get_characters_by_appellations(
                    interfering_names,
                    series
                )
                if interfering_characters:
                    self.character_service.link_characters_to_progression(
                        interfering_characters,
                        progression
                    )
                else:
                    logger.warning(f"No interfering characters found for progression in {season}{episode}")

            self.progression_service.add_or_update_progression(
                arc=arc,
                progression=progression,
                series=series,
                season=season,
                episode=episode
            )

    def update_embeddings(self, arc: NarrativeArc):
        """Update the vector store embeddings for the arc."""
        main_characters_str = ', '.join([char.best_appellation for char in arc.main_characters])

        main_doc = Document(
            page_content=f"{arc.title}\n{arc.description}",
            metadata={
                "title": arc.title,
                "arc_type": arc.arc_type,
                "description": arc.description,
                "main_characters": main_characters_str,
                "series": arc.series,
                "doc_type": "main",
                "id": arc.id,
            }
        )

        docs = [main_doc]
        ids = [arc.id]
        for progression in arc.progressions:
            interfering_chars_str = ', '.join([
                char.best_appellation
                for char in progression.interfering_characters
            ])

            progression_title = f"{arc.series} | {arc.title} | S{progression.season.replace('S', '')}E{progression.episode.replace('E', '')}"
            if interfering_chars_str:
                progression_title += f" | {interfering_chars_str}"

            prog_doc = Document(
                page_content=f"{progression.content}",
                metadata={
                    "progression_title": progression_title,
                    "arc_type": arc.arc_type,
                    "interfering_characters": interfering_chars_str,
                    "series": arc.series,
                    "doc_type": "progression",
                    "id": progression.id,
                    "main_arc_id": arc.id,
                    "parent_arc_title": arc.title,
                    "season": progression.season,
                    "episode": progression.episode,
                    "ordinal_position": progression.ordinal_position
                }
            )
            docs.append(prog_doc)
            ids.append(progression.id)

        try:
            self.vector_store_service.delete_documents_by_arc(arc.id)
            self.vector_store_service.add_documents(docs, ids)
            logger.info(f"Updated vector store entries for arc '{arc.title}' with {len(docs)} documents")
        except Exception as e:
            logger.error(f"Error updating vector store for arc {arc.id}: {e}")
            raise

    def add_arc_to_vector_store(self, arc: NarrativeArc):
        """Optional helper if you want to separately add arcs to vector store."""
        self.update_embeddings(arc)

    def delete_arc(self, arc_id: str) -> bool:
        """Delete a narrative arc and its progressions."""
        with self.transaction():
            try:
                arc = self.arc_repository.get_by_id(arc_id)
                if not arc:
                    logger.warning(f"No arc found with ID {arc_id}")
                    return False

                self.vector_store_service.delete_documents_by_arc(arc_id)
                self.arc_repository.delete(arc_id)
                logger.info(f"Successfully deleted arc '{arc.title}' with ID {arc_id}")
                return True

            except Exception as e:
                logger.error(f"Error deleting arc {arc_id}: {e}")
                raise

    def update_arc_details(
        self,
        arc_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        arc_type: Optional[str] = None,
        main_characters: Optional[List[str]] = None
    ) -> Optional[NarrativeArc]:
        """Update specific details of a narrative arc."""
        with self.transaction():
            try:
                arc = self.arc_repository.get_by_id(arc_id)
                if not arc:
                    raise NotFoundError(f"No arc found with ID {arc_id}")

                update_fields = {}
                if title is not None:
                    update_fields["title"] = title.strip().title()
                if description is not None:
                    update_fields["description"] = description
                if arc_type is not None:
                    update_fields["arc_type"] = arc_type

                if update_fields:
                    self.arc_repository.update_fields(arc, update_fields)

                if main_characters is not None:
                    characters = self.character_service.get_characters_by_appellations(
                        main_characters, arc.series
                    )
                    arc.main_characters = characters
                    logger.info(f"Updated main characters for arc '{arc.title}'")

                return arc

            except Exception as e:
                logger.error(f"Error updating arc {arc_id}: {e}")
                raise

    def update_progression(
        self,
        progression_id: str,
        content: str,
        interfering_characters: List[str]
    ) -> Optional[ArcProgression]:
        """Update the content and interfering characters of a progression."""
        with self.transaction():
            try:
                progression = self.progression_service.get_progression_by_id(progression_id)
                if not progression:
                    raise NotFoundError(f"No progression found with ID {progression_id}")

                progression.content = content

                characters = self.character_service.get_characters_by_appellations(
                    interfering_characters,
                    progression.series
                )
                progression.interfering_characters = characters

                self.progression_service.add_or_update_progression(
                    arc=progression.narrative_arc,
                    progression=progression,
                    series=progression.series,
                    season=progression.season,
                    episode=progression.episode
                )

                self.update_embeddings(progression.narrative_arc)

                logger.info(f"Updated progression {progression_id} with {len(characters)} interfering characters")
                return progression

            except Exception as e:
                logger.error(f"Error updating progression {progression_id}: {e}")
                raise

    def add_progression(
        self,
        arc_id: str,
        content: str,
        series: str,
        season: str,
        episode: str,
        interfering_characters: Union[str, List[str]]
    ) -> Optional[ArcProgression]:
        """Add a new progression to an existing arc."""
        with self.transaction():
            try:
                character_names = (
                    interfering_characters.split(';')
                    if isinstance(interfering_characters, str)
                    else interfering_characters
                )

                arc = self.arc_repository.get_by_id(arc_id)
                if not arc:
                    raise NotFoundError(f"No arc found with ID {arc_id}")

                normalized_season = f"S{season.replace('S', '').replace('s', '').zfill(2)}"
                normalized_episode = f"E{episode.replace('E', '').replace('e', '').zfill(2)}"

                progression = ArcProgression(
                    id=str(uuid.uuid4()),
                    content=content,
                    series=series,
                    season=normalized_season,
                    episode=normalized_episode,
                    main_arc_id=arc.id
                )
                self.session.add(progression) # Add to session before linking characters

                if character_names:
                    characters = self.character_service.get_characters_by_appellations(
                        character_names,
                        series
                    )
                    if characters:
                        self.character_service.link_characters_to_progression(
                            characters,
                            progression
                        )
                        logger.info(f"Linked {len(characters)} interfering characters to new progression")

                updated_progression = self.progression_service.add_or_update_progression(
                    arc=arc,
                    progression=progression,
                    series=series,
                    season=normalized_season,
                    episode=normalized_episode
                )

                self.session.refresh(arc, ['progressions'])

                self.update_embeddings(arc)

                logger.info(f"Added new progression to arc '{arc.title}' in {normalized_season}{normalized_episode}")
                return updated_progression

            except Exception as e:
                logger.error(f"Error adding progression to arc {arc_id}: {e}")
                raise