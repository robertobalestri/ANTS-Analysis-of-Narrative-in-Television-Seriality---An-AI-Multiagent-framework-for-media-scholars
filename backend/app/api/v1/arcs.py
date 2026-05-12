"""Arc API routes."""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import select

from app.models.narrative import NarrativeArc, ArcProgression, Character
from app.models.schemas import (
    ArcCreateRequest,
    ArcMergeRequest,
    ArcUpdateRequest,
    ArcProgressionResponse,
    NarrativeArcResponse,
)
from app.repositories import (
    DatabaseSessionManager,
    NarrativeArcRepository,
    ArcProgressionRepository,
    CharacterRepository,
)
from app.services import NarrativeArcService, CharacterService, VectorStoreService, LLMService
from app.core.logging import setup_logging
from app.utils.path import PathHandler

logger = setup_logging(__name__)
router = APIRouter(prefix="/api/arcs", tags=["arcs"])

db_manager = DatabaseSessionManager()


def normalize_season_episode(season: str, episode: str):
    """Normalize season and episode format to S01, E01."""
    season_num = int(season.replace('S', '').replace('s', ''))
    episode_num = int(episode.replace('E', '').replace('e', ''))
    return f"S{season_num:02d}", f"E{episode_num:02d}"


def pad_number(num_str: str) -> str:
    """Pad a number string to at least 2 digits."""
    if len(num_str) == 1:
        return f"0{num_str}"
    return num_str


def get_narrative_service(session):
    """Dependency to get NarrativeArcService."""
    return NarrativeArcService(
        arc_repository=NarrativeArcRepository(session),
        progression_repository=ArcProgressionRepository(session),
        character_service=CharacterService(CharacterRepository(session)),
        llm_service=None,
        vector_store_service=VectorStoreService(),
        session=session
    )


@router.get("/series/{series}", response_model=List[NarrativeArcResponse])
async def get_arcs_by_series(series: str):
    """Get all narrative arcs for a specific series."""
    try:
        with db_manager.session_scope() as session:
            logger.info(f"Fetching arcs for series: {series}")
            arc_repository = NarrativeArcRepository(session)
            arcs = arc_repository.get_all(series=series)
            logger.info(f"Found {len(arcs)} arcs")

            for arc in arcs:
                for prog in arc.progressions:
                    normalized_season, normalized_episode = normalize_season_episode(prog.season, prog.episode)
                    prog.season = normalized_season
                    prog.episode = normalized_episode

            return [NarrativeArcResponse.from_arc(arc) for arc in arcs]
    except Exception as e:
        logger.error(f"Error getting arcs for series {series}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{series}/{season}/{episode}", response_model=List[NarrativeArcResponse])
async def get_arcs_by_episode(series: str, season: str, episode: str):
    """Get all narrative arcs that have progressions in a specific episode."""
    try:
        normalized_episode = f"E{episode.zfill(2)}"
        logger.debug(f"Fetching arcs for {series} {season} {normalized_episode}")

        with db_manager.session_scope() as session:
            query = select(NarrativeArc)\
                .join(ArcProgression)\
                .where(
                    ArcProgression.series == series,
                    ArcProgression.season == season,
                    ArcProgression.episode == normalized_episode
                )\
                .distinct()

            arcs = session.exec(query).all()

            if not arcs:
                logger.warning(f"No arcs found for {series} {season} {normalized_episode}")
                return []

            return [NarrativeArcResponse.from_arc(arc) for arc in arcs]

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/by-id/{arc_id}", response_model=NarrativeArcResponse)
async def get_arc_by_id(arc_id: str):
    """Get a single arc by ID with all its details."""
    try:
        with db_manager.session_scope() as session:
            arc_repository = NarrativeArcRepository(session)
            arc = arc_repository.get_by_id(arc_id)

            if not arc:
                raise HTTPException(status_code=404, detail=f"Arc with ID {arc_id} not found")

            session.refresh(arc, ['main_characters', 'progressions'])

            for prog in arc.progressions:
                normalized_season, normalized_episode = normalize_season_episode(prog.season, prog.episode)
                prog.season = normalized_season
                prog.episode = normalized_episode

            response = NarrativeArcResponse.from_arc(arc)
            logger.info(f"Retrieved arc '{arc.title}' with {len(arc.progressions)} progressions")
            return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting arc by ID {arc_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=NarrativeArcResponse)
async def create_arc(arc_data: ArcCreateRequest):
    """Create a new narrative arc."""
    try:
        logger.info("=== Raw Request Data ===")
        logger.info(f"Type of arc_data: {type(arc_data)}")
        logger.info(f"Raw arc_data: {arc_data.dict()}")

        with db_manager.session_scope() as session:
            narrative_arc_service = get_narrative_service(session)

            arc_dict = {
                'title': arc_data.title,
                'description': arc_data.description,
                'arc_type': arc_data.arc_type,
                'main_characters': arc_data.main_characters,
                'single_episode_progression_string': arc_data.initial_progression.content if arc_data.initial_progression else None,
                'interfering_episode_characters': arc_data.initial_progression.interfering_characters if arc_data.initial_progression else None
            }

            new_arc = narrative_arc_service.add_arc(
                arc_data=arc_dict,
                series=arc_data.series,
                season=arc_data.initial_progression.season if arc_data.initial_progression else "",
                episode=arc_data.initial_progression.episode if arc_data.initial_progression else "",
            )

            logger.info(f"Created new arc with ID: {new_arc.id}")
            return NarrativeArcResponse.from_arc(new_arc)

    except Exception as e:
        logger.error(f"Error creating arc: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{arc_id}")
async def update_arc(arc_id: str, update_data: ArcUpdateRequest):
    """Update arc details."""
    try:
        with db_manager.session_scope() as session:
            narrative_arc_service = get_narrative_service(session)

            updated_arc = narrative_arc_service.update_arc_details(
                arc_id=arc_id,
                title=update_data.title,
                description=update_data.description,
                arc_type=update_data.arc_type,
                main_characters=update_data.main_characters
            )
            if not updated_arc:
                raise HTTPException(status_code=404, detail="Arc not found")
            return NarrativeArcResponse.from_arc(updated_arc)
    except Exception as e:
        logger.error(f"Error updating arc: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{arc_id}")
async def delete_arc(arc_id: str):
    """Delete a narrative arc and its progressions."""
    try:
        with db_manager.session_scope() as session:
            narrative_arc_service = get_narrative_service(session)

            result = narrative_arc_service.delete_arc(arc_id)
            if not result:
                raise HTTPException(status_code=404, detail="Arc not found")
            return {"message": "Arc deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting arc: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/merge", response_model=NarrativeArcResponse)
async def merge_arcs(merge_data: ArcMergeRequest):
    """Merge two arcs into a new one."""
    try:
        logger.info(f"Received merge request for arcs: {merge_data.arc_id_1} and {merge_data.arc_id_2}")

        with db_manager.session_scope() as session:
            arc_repository = NarrativeArcRepository(session)

            arc1 = arc_repository.get_by_id(merge_data.arc_id_1)
            arc2 = arc_repository.get_by_id(merge_data.arc_id_2)

            if not arc1 or not arc2:
                raise HTTPException(
                    status_code=404,
                    detail="One or both arcs not found"
                )

            normalized_mappings = []
            for prog in merge_data.progression_mappings:
                if not prog.content.strip():
                    continue

                season = f"S{pad_number(prog.season.replace('S', ''))}"
                episode = f"E{pad_number(prog.episode.replace('E', ''))}"

                normalized_mappings.append({
                    "season": season,
                    "episode": episode,
                    "content": prog.content,
                    "interfering_characters": prog.interfering_characters
                })

            narrative_arc_service = get_narrative_service(session)
            merged_arc = narrative_arc_service.merge_arcs(
                arc_id_1=merge_data.arc_id_1,
                arc_id_2=merge_data.arc_id_2,
                merged_title=merge_data.merged_title,
                merged_description=merge_data.merged_description,
                merged_arc_type=merge_data.merged_arc_type,
                main_characters=merge_data.main_characters,
                progression_mappings=normalized_mappings
            )

            if not merged_arc:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to merge arcs"
                )

            logger.info(f"Successfully merged arcs into '{merged_arc.title}'")
            return NarrativeArcResponse.from_arc(merged_arc)

    except Exception as e:
        logger.error(f"Error merging arcs: {e}")
        raise HTTPException(status_code=500, detail=str(e))