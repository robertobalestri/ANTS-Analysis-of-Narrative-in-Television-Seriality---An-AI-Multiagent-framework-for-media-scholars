"""Progression API routes."""
from typing import List, Union
from fastapi import APIRouter, HTTPException, Query, Body
from sqlmodel import select

from app.models.narrative import ArcProgression
from app.models.schemas import (
    ArcProgressionResponse,
    ProgressionUpdateRequest,
    ProgressionCreateRequest,
)
from app.repositories import (
    DatabaseSessionManager,
    NarrativeArcRepository,
    ArcProgressionRepository,
    CharacterRepository,
)
from app.services import NarrativeArcService, CharacterService, VectorStoreService
from app.services.ai import LLMService
from app.core.logging import setup_logging
from app.utils.path import PathHandler

logger = setup_logging(__name__)
router = APIRouter(prefix="/api/progressions", tags=["progressions"])

db_manager = DatabaseSessionManager()


def pad_number(num_str: str) -> str:
    if len(num_str) == 1:
        return f"0{num_str}"
    return num_str


@router.get("/{series}/{season}/{episode}", response_model=List[ArcProgressionResponse])
async def get_progressions_by_episode(series: str, season: str, episode: str):
    """Get all progressions for a specific episode."""
    try:
        normalized_episode = f"E{episode.zfill(2)}"
        with db_manager.session_scope() as session:
            query = select(ArcProgression).where(
                ArcProgression.series == series,
                ArcProgression.season == season,
                ArcProgression.episode == normalized_episode
            )
            progressions = session.exec(query).all()
            return [ArcProgressionResponse.from_progression(prog) for prog in progressions]
    except Exception as e:
        logger.error(f"Error getting progressions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=ArcProgressionResponse)
async def create_progression(progression: ProgressionCreateRequest):
    """Create a new progression."""
    try:
        with db_manager.session_scope() as session:
            season = f"S{pad_number(progression.season.replace('S', ''))}"
            episode = f"E{pad_number(progression.episode.replace('E', ''))}"

            narrative_arc_service = NarrativeArcService(
                arc_repository=NarrativeArcRepository(session),
                progression_repository=ArcProgressionRepository(session),
                character_service=CharacterService(CharacterRepository(session)),
                llm_service=None,
                vector_store_service=VectorStoreService(),
                session=session
            )

            character_names = (
                progression.interfering_characters.split(';')
                if isinstance(progression.interfering_characters, str)
                else progression.interfering_characters
            )

            new_progression = narrative_arc_service.add_progression(
                arc_id=progression.arc_id,
                content=progression.content,
                series=progression.series,
                season=season,
                episode=episode,
                interfering_characters=character_names
            )

            if not new_progression:
                raise HTTPException(status_code=404, detail="Arc not found")

            return ArcProgressionResponse.from_progression(new_progression)

    except Exception as e:
        logger.error(f"Error creating progression: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{progression_id}", response_model=ArcProgressionResponse)
async def update_progression(progression_id: str, progression_data: ProgressionUpdateRequest):
    """Update a progression."""
    try:
        with db_manager.session_scope() as session:
            progression_repository = ArcProgressionRepository(session)
            character_service = CharacterService(CharacterRepository(session))

            progression = progression_repository.get_by_id(progression_id)
            if not progression:
                raise HTTPException(status_code=404, detail="Progression not found")

            progression.content = progression_data.content

            character_names = (
                progression_data.interfering_characters.split(';')
                if isinstance(progression_data.interfering_characters, str)
                else progression_data.interfering_characters
            )

            interfering_characters = character_service.get_characters_by_appellations(
                character_names,
                progression.series
            )

            progression.interfering_characters = interfering_characters
            session.commit()
            session.refresh(progression)

            narrative_arc_service = NarrativeArcService(
                arc_repository=NarrativeArcRepository(session),
                progression_repository=progression_repository,
                character_service=character_service,
                llm_service=None,
                vector_store_service=VectorStoreService(),
                session=session
            )
            narrative_arc_service.update_embeddings(progression.narrative_arc)

            return ArcProgressionResponse.from_progression(progression)

    except Exception as e:
        logger.error(f"Error updating progression: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{progression_id}")
async def delete_progression(progression_id: str):
    """Delete a progression."""
    try:
        with db_manager.session_scope() as session:
            arc_repository = NarrativeArcRepository(session)
            progression_repository = ArcProgressionRepository(session)
            character_service = CharacterService(CharacterRepository(session))
            vector_store_service = VectorStoreService()

            narrative_arc_service = NarrativeArcService(
                arc_repository=arc_repository,
                progression_repository=progression_repository,
                character_service=character_service,
                llm_service=None,
                vector_store_service=vector_store_service,
                session=session
            )

            progression = progression_repository.get_by_id(progression_id)
            if not progression:
                raise HTTPException(status_code=404, detail="Progression not found")

            progression_repository.delete(progression_id)
            narrative_arc_service.update_embeddings(progression.narrative_arc)

            return {"message": "Progression deleted successfully"}

    except Exception as e:
        logger.error(f"Error deleting progression: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate")
async def generate_progression(
    series: str = Query(...),
    season: str = Query(...),
    episode: str = Query(...),
    data: dict = Body(...)
):
    """Generate progression content for an arc in a specific episode."""
    try:
        logger.info(f"Generating progression for series: {series}, S{season}E{episode}")

        with db_manager.session_scope() as session:
            arc_repository = NarrativeArcRepository(session)
            progression_repository = ArcProgressionRepository(session)
            character_repository = CharacterRepository(session)
            character_service = CharacterService(character_repository)
            llm_service = LLMService()

            arc = None
            arc_title = None
            arc_description = None

            if data.get('arc_id'):
                arc = arc_repository.get_by_id(data['arc_id'])
                if arc:
                    arc_title = arc.title
                    arc_description = arc.description
            else:
                arc_title = data.get('arc_title')
                arc_description = data.get('arc_description')

            if not arc_title or not arc_description:
                return {"content": "", "interfering_characters": []}

            content = llm_service.generate_progression_content(
                arc_title=arc_title,
                arc_description=arc_description,
                season=season,
                episode=episode
            )

            if content == "NO_PROGRESSION" and arc and data.get('delete_existing', False):
                existing_progression = progression_repository.get_single(
                    arc_id=arc.id,
                    series=series,
                    season=season,
                    episode=episode
                )
                if existing_progression:
                    progression_repository.delete(existing_progression.id)
                return {"content": "NO_PROGRESSION", "interfering_characters": []}

            if content != "NO_PROGRESSION":
                all_characters = character_repository.get_by_series(series)
                mentioned_appellations = []
                for character in all_characters:
                    for appellation in character.appellations:
                        if appellation.appellation in content:
                            mentioned_appellations.append(character.best_appellation)
                            break
                return {"content": content, "interfering_characters": mentioned_appellations}

            return {"content": content, "interfering_characters": []}

    except Exception as e:
        logger.error(f"Error generating progression: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))