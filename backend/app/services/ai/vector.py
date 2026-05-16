"""Vector store service for ANTS."""
import os
from typing import List, Dict, Optional, Any, Union
from langchain_core.documents import Document
from langchain_chroma import Chroma
import numpy as np
from hdbscan import HDBSCAN

from app.services.ai.models import get_embedding_model
from app.core.logging import setup_logging

logger = setup_logging(__name__)


class VectorStoreService:
    """Service to manage vector store interactions."""

    def __init__(self, collection_name: str = "narrative_arcs", persist_directory: Optional[str] = None):
        self.collection_name = collection_name
        self.persist_directory = persist_directory or os.getenv("PERSIST_DIRECTORY", "./vector_store")
        self.embedding_model = get_embedding_model()
        self.collection = self._initialize_collection()

    def _initialize_collection(self) -> Chroma:
        return Chroma(
            collection_name=self.collection_name,
            persist_directory=self.persist_directory,
            embedding_function=self.embedding_model,
            collection_metadata={"hnsw:space": "cosine"},
        )

    def add_documents(self, documents: List[Document], ids: List[str]):
        try:
            self.collection.add_documents(documents, ids=ids)
            logger.info(f"Added {len(documents)} documents to the vector store.")
        except Exception as e:
            logger.error(f"Failed to add documents to the vector store: {e}")
            raise

    def find_similar_arcs(
        self,
        query: str,
        n_results: int = 5,
        series: Optional[str] = None,
        exclude_anthology: bool = False
    ) -> List[Dict[str, Any]]:
        """Find similar arcs (main documents only) to a query."""
        filter_criteria = {"$and": [{"doc_type": "main"}]}
        if series:
            filter_criteria["$and"].append({"series": series})
        if exclude_anthology:
            filter_criteria["$and"].append({"arc_type": {"$ne": "Anthology Arc"}})

        try:
            results = self.collection.similarity_search_with_score(
                query,
                k=n_results,
                filter=filter_criteria
            )
            return [{"metadata": result[0].metadata, "cosine_distance": float(result[1])} for result in results]
        except Exception as e:
            logger.error(f"Error during similarity search: {e}")
            return []

    def delete_documents_by_arc(self, arc_id: str):
        """Delete all documents related to a specific arc."""
        try:
            main_docs_response = self.collection.get(
                where={"id": arc_id},
                include=["metadatas"]
            )
            prog_docs_response = self.collection.get(
                where={"main_arc_id": arc_id},
                include=["metadatas"]
            )

            ids_to_delete = []
            main_ids = main_docs_response.get('ids', [])
            ids_to_delete.extend(main_ids)

            prog_ids = prog_docs_response.get('ids', [])
            ids_to_delete.extend(prog_ids)

            if ids_to_delete:
                self.collection.delete(ids=ids_to_delete)
                logger.info(f"Deleted {len(ids_to_delete)} documents for arc ID {arc_id}.")
            else:
                logger.info(f"No documents found for arc ID {arc_id}.")

        except Exception as e:
            logger.error(f"Error deleting documents for arc ID {arc_id}: {e}")
            raise

    def delete_all_documents(self):
        """Delete all documents from the collection."""
        try:
            self.collection.delete()
            logger.info("Deleted all documents from collection")
        except Exception as e:
            logger.error(f"Error deleting documents: {e}")
            raise

    def get_all_documents(self, series: str, include_embeddings: bool = True) -> List[Dict]:
        """Get all documents for a series from the vector store."""
        try:
            results = self.collection.get(
                where={"series": series},
                include=['metadatas', 'documents', 'embeddings'] if include_embeddings else ['metadatas', 'documents']
            )

            documents = []
            for i in range(len(results['ids'])):
                doc = {
                    'id': results['ids'][i],
                    'content': results['documents'][i],
                    'metadata': results['metadatas'][i],
                }
                if include_embeddings and 'embeddings' in results:
                    emb = results['embeddings'][i]
                    if hasattr(emb, 'tolist'):
                        doc['embedding'] = emb.tolist()
                    else:
                        doc['embedding'] = emb
                documents.append(doc)

            return documents

        except Exception as e:
            logger.error(f"Error getting all documents: {e}")
            return []

    def find_similar_documents(
        self,
        query: str,
        series: str,
        n_results: int = 10
    ) -> List[Dict]:
        """Find similar documents (both arcs and progressions) to a query."""
        try:
            filter_criteria = {"series": series}

            results = self.collection.similarity_search_with_score(
                query,
                k=n_results,
                filter=filter_criteria
            )

            documents = []
            for doc, score in results:
                entry = {
                    'id': doc.metadata.get('id'),
                    'content': doc.page_content,
                    'metadata': doc.metadata,
                    'distance': score
                }
                documents.append(entry)

            return documents

        except Exception as e:
            logger.error(f"Error during similarity search: {e}")
            return []

    def calculate_arcs_cosine_distances(
        self,
        arc_ids: List[str]
    ) -> Dict[str, Union[str, float]]:
        """Calculate cosine distances between selected arcs."""
        try:
            results = self.collection.get(
                ids=arc_ids,
                include=['metadatas', 'embeddings']
            )

            if not results or 'embeddings' not in results or len(results['embeddings']) != 2:
                raise ValueError("Could not find embeddings for both arcs")

            embedding1 = np.array(results['embeddings'][0])
            embedding2 = np.array(results['embeddings'][1])

            dot_product = np.dot(embedding1, embedding2)
            norm1 = np.linalg.norm(embedding1)
            norm2 = np.linalg.norm(embedding2)

            if norm1 == 0 or norm2 == 0:
                cosine_distance = 1.0
            else:
                cosine_similarity = dot_product / (norm1 * norm2)
                cosine_similarity = np.clip(cosine_similarity, -1.0, 1.0)
                cosine_distance = 1.0 - cosine_similarity

            return {
                "arc1": {
                    "id": results['ids'][0],
                    "title": results['metadatas'][0].get('title', ''),
                    "type": results['metadatas'][0].get('arc_type', '')
                },
                "arc2": {
                    "id": results['ids'][1],
                    "title": results['metadatas'][1].get('title', ''),
                    "type": results['metadatas'][1].get('arc_type', '')
                },
                "distance": float(cosine_distance)
            }

        except Exception as e:
            logger.error(f"Error calculating cosine distances: {e}")
            raise

    def find_similar_arcs_clusters(
        self,
        series: str,
        min_cluster_size: int = 2,
        min_samples: int = 1,
        cluster_selection_epsilon: float = 0.0,
        exclude_arc_types: Optional[List[str]] = None
    ) -> List[Dict]:
        """Find clusters of similar arcs using HDBSCAN clustering."""
        try:
            where_clauses = [{"series": series}, {"doc_type": "main"}]
            if exclude_arc_types:
                where_clauses.append({"arc_type": {"$nin": exclude_arc_types}})
            results = self.collection.get(
                where={"$and": where_clauses},
                include=['metadatas', 'embeddings']
            )

            if not results or 'embeddings' not in results or len(results['embeddings']) < 2:
                return []

            embeddings = np.array(results['embeddings'])

            distance_matrix = np.zeros((len(embeddings), len(embeddings)))
            for i in range(len(embeddings)):
                for j in range(len(embeddings)):
                    if i != j:
                        dot_product = np.dot(embeddings[i], embeddings[j])
                        norm_i = np.linalg.norm(embeddings[i])
                        norm_j = np.linalg.norm(embeddings[j])
                        if norm_i == 0 or norm_j == 0:
                            distance_matrix[i, j] = 1.0
                        else:
                            cosine_sim = dot_product / (norm_i * norm_j)
                            cosine_sim = np.clip(cosine_sim, -1.0, 1.0)
                            distance_matrix[i, j] = 1.0 - cosine_sim

            clusterer = HDBSCAN(
                min_cluster_size=min_cluster_size,
                min_samples=min_samples,
                cluster_selection_epsilon=cluster_selection_epsilon,
                metric='precomputed',
                core_dist_n_jobs=-1,
                cluster_selection_method='leaf',
                prediction_data=False,
                allow_single_cluster=True
            )

            clusterer.fit(distance_matrix)
            labels = clusterer.labels_
            probabilities = clusterer.probabilities_

            clusters = {}
            next_noise_id = max(labels) + 1 if any(l >= 0 for l in labels) else 0
            for i, (label, prob) in enumerate(zip(labels, probabilities)):
                if label == -1:
                    label = next_noise_id
                    next_noise_id += 1
                if label not in clusters:
                    clusters[label] = []
                clusters[label].append({
                    "id": results['ids'][i],
                    "title": results['metadatas'][i].get('title', ''),
                    "type": results['metadatas'][i].get('arc_type', ''),
                    "metadata": results['metadatas'][i],
                    "cluster_probability": float(prob),
                    "embedding": (results['embeddings'][i].tolist() 
                                  if hasattr(results['embeddings'][i], 'tolist') 
                                  else results['embeddings'][i]) 
                                  if results.get('embeddings') is not None else None
                })

            similar_groups = []
            for cluster_id_key, arcs in clusters.items():
                if not arcs:
                    continue
                cluster_indices = [results['ids'].index(arc['id']) for arc in arcs]
                distances = []
                for i, idx1 in enumerate(cluster_indices):
                    for j, idx2 in enumerate(cluster_indices[i+1:], i+1):
                        distances.append(distance_matrix[idx1, idx2])

                avg_distance = float(np.mean(distances)) if distances else 0.0
                avg_probability = float(np.mean([arc['cluster_probability'] for arc in arcs]))
                persistence = float(clusterer.cluster_persistence_[cluster_id_key]) if cluster_id_key < len(clusterer.cluster_persistence_) else 0.0

                similar_groups.append({
                    "cluster_id": int(cluster_id_key),
                    "arcs": arcs,
                    "average_distance": avg_distance,
                    "size": len(arcs),
                    "average_probability": avg_probability,
                    "cluster_persistence": persistence
                })

            similar_groups.sort(key=lambda x: (x['size'], x['average_probability']), reverse=True)

            return similar_groups

        except Exception as e:
            logger.error(f"Error finding similar arcs clusters: {e}")
            raise