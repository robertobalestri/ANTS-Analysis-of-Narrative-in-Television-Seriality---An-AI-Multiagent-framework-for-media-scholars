"""Character API routes."""
from typing import List
from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    CharacterResponse,
    CharacterCreateRequest,
    CharacterMergeRequest,
)
from app.repositories import DatabaseSessionManager, CharacterRepository
from app.services import CharacterService
from app.core.logging import setup_logging

logger = setup_logging(__name__)
router = APIRouter(prefix="/api/characters", tags=["characters"])

db_manager = DatabaseSessionManager()


@router.get("/{series}", response_model=List[CharacterResponse])
async def get_characters(series: str):
    """Get all characters for a series."""
    try:
        with db_manager.session_scope() as session:
            character_repository = CharacterRepository(session)
            characters = character_repository.get_by_series(series)
            return [
                CharacterResponse(
                    entity_name=char.entity_name,
                    best_appellation=char.best_appellation,
                    series=char.series,
                    appellations=[app.appellation for app in char.appellations]
                )
                for char in characters
            ]
    except Exception as e:
        logger.error(f"Error getting characters: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{series}", response_model=CharacterResponse)
async def create_character(series: str, character_data: CharacterCreateRequest):
    """Create a new character."""
    try:
        with db_manager.session_scope() as session:
            character_service = CharacterService(CharacterRepository(session))
            character = character_service.add_or_update_character(
                entity_name=character_data.entity_name,
                best_appellation=character_data.best_appellation,
                appellations=character_data.appellations,
                series=series,
                episode_code=""
            )
            if not character:
                raise HTTPException(status_code=400, detail="Failed to create character")
            return CharacterResponse(
                entity_name=character.entity_name,
                best_appellation=character.best_appellation,
                series=character.series,
                appellations=[app.appellation for app in character.appellations]
            )
    except Exception as e:
        logger.error(f"Error creating character: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{series}", response_model=CharacterResponse)
async def update_character(series: str, character_data: CharacterCreateRequest):
    """Update an existing character."""
    try:
        with db_manager.session_scope() as session:
            character_service = CharacterService(CharacterRepository(session))

            character = character_service.add_or_update_character(
                entity_name=character_data.entity_name,
                best_appellation=character_data.best_appellation,
                appellations=character_data.appellations,
                series=series,
                episode_code=""
            )
            if not character:
                raise HTTPException(status_code=404, detail="Character not found")

            session.refresh(character)

            return CharacterResponse(
                entity_name=character.entity_name,
                best_appellation=character.best_appellation,
                series=character.series,
                appellations=[app.appellation for app in character.appellations]
            )
    except Exception as e:
        logger.error(f"Error updating character: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{series}/{entity_name}")
async def delete_character(series: str, entity_name: str):
    """Delete a character."""
    try:
        with db_manager.session_scope() as session:
            character_repository = CharacterRepository(session)
            character = character_repository.get_by_entity_name(entity_name, series)
            if not character:
                raise HTTPException(status_code=404, detail="Character not found")
            character_repository.delete(character)
            return {"message": "Character deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting character: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{series}/merge", response_model=dict)
async def merge_characters(series: str, merge_data: CharacterMergeRequest):
    """Merge two characters."""
    try:
        logger.info(f"Attempting to merge characters in series {series}")

        with db_manager.session_scope() as session:
            character_service = CharacterService(CharacterRepository(session))

            success = character_service.merge_characters(
                merge_data.character1_id,
                merge_data.character2_id,
                series,
                keep_character=merge_data.keep_character
            )

            if not success:
                error_msg = f"Failed to merge characters. One or both characters not found"
                logger.error(error_msg)
                raise HTTPException(status_code=400, detail=error_msg)

            logger.info(f"Successfully merged characters {merge_data.character1_id} and {merge_data.character2_id}")
            return {"message": "Characters merged successfully"}

    except Exception as e:
        error_msg = f"Error merging characters: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)