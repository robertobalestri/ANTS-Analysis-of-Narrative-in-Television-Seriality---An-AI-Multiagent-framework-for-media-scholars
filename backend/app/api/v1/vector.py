"""Vector store API routes."""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Body

from app.services import VectorStoreService
from app.core.logging import setup_logging

logger = setup_logging(__name__)
router = APIRouter(prefix="/api/vector-store", tags=["vector"])


@router.get("/search", response_model=List[dict])
async def search_vectors(
    query: str = Query(...),
    series: Optional[str] = Query(None),
    n_results: int = Query(5)
):
    """Search the vector store for similar arcs."""
    try:
        vector_service = VectorStoreService()
        results = vector_service.find_similar_arcs(
            query=query,
            n_results=n_results,
            series=series
        )
        return results
    except Exception as e:
        logger.error(f"Error searching vectors: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/clusters", response_model=List[dict])
async def get_arc_clusters(
    series: str = Query(...),
    min_cluster_size: int = Query(2),
    min_samples: int = Query(1),
    threshold: float = Query(0.0)
):
    """Get clusters of similar arcs."""
    try:
        vector_service = VectorStoreService()
        clusters = vector_service.find_similar_arcs_clusters(
            series=series,
            min_cluster_size=min_cluster_size,
            min_samples=min_samples,
            cluster_selection_epsilon=threshold
        )
        return clusters
    except Exception as e:
        logger.error(f"Error getting clusters: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/distance")
async def get_arc_distance(
    arc1_id: str = Query(...),
    arc2_id: str = Query(...)
):
    """Calculate cosine distance between two arcs."""
    try:
        vector_service = VectorStoreService()
        result = vector_service.calculate_arcs_cosine_distances([arc1_id, arc2_id])
        return result
    except Exception as e:
        logger.error(f"Error calculating distance: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/arc/{arc_id}")
async def delete_arc_vectors(arc_id: str):
    """Delete vector store entries for an arc."""
    try:
        vector_service = VectorStoreService()
        vector_service.delete_documents_by_arc(arc_id)
        return {"message": "Vector entries deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting vectors: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare")
async def compare_arcs(arc_ids: List[str] = Body(...)):
    """Calculate cosine distance between two arcs."""
    if len(arc_ids) != 2:
        raise HTTPException(status_code=400, detail="Exactly 2 arc IDs required")
    try:
        vector_service = VectorStoreService()
        result = vector_service.calculate_arcs_cosine_distances(arc_ids)
        return result
    except Exception as e:
        logger.error(f"Error calculating distance: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{series}/clusters", response_model=List[dict])
async def get_clusters_by_series(
    series: str,
    threshold: float = Query(0.0),
    min_cluster_size: int = Query(2),
    max_clusters: Optional[int] = Query(None),
    exclude_arc_types: Optional[str] = Query(None)
):
    """Get clusters of similar arcs for a series."""
    exclude_types = [t.strip() for t in exclude_arc_types.split(",")] if exclude_arc_types else None
    try:
        vector_service = VectorStoreService()
        clusters = vector_service.find_similar_arcs_clusters(
            series=series,
            min_cluster_size=min_cluster_size,
            cluster_selection_epsilon=threshold,
            exclude_arc_types=exclude_types
        )
        if max_clusters:
            clusters = clusters[:max_clusters]
        return clusters
    except Exception as e:
        logger.error(f"Error getting clusters for series {series}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{series}")
async def get_vectors_for_series(series: str):
    """Get all vector entries for a series."""
    try:
        vector_service = VectorStoreService()
        entries = vector_service.get_all_documents(series)
        return entries
    except Exception as e:
        logger.error(f"Error getting vectors for series {series}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))