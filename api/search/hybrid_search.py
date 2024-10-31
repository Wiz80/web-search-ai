from typing import List, Dict, Any, Union
import torch
from sentence_transformers import CrossEncoder
import logging
from dataclasses import dataclass
from elasticsearch import Elasticsearch
from neo4j import GraphDatabase
from api.helpers.elasticsearch_handler import ElasticsearchHandler
from api.helpers.neo4j_handler import Neo4jHandler
import os

@dataclass
class SearchResult:
    """
    Standardized format for search results from any source.
    """
    title: str
    description: str
    price: float
    source: str  # 'elastic' or 'neo4j'
    original_score: float
    url: str = None
    resumen: str = None

class HybridSearchReranker:
    """
    Handles hybrid search combining Elasticsearch BM25 and Neo4j vector search results,
    with cross-encoder reranking for improved relevance.
    """
    
    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-12-v2",
        device: str = None
    ):
        """
        Initialize the hybrid search reranker.

        Args:
            elasticsearch_handler: Instance of ElasticsearchHandler
            neo4j_handler: Instance of Neo4jHandler
            model_name: Name of the cross-encoder model to use
            device: Device to run the model on ('cuda' or 'cpu')
        """
        self.es_handler = ElasticsearchHandler(
            hosts=['http://localhost:9200']
        )

        self.neo4j_handler = Neo4jHandler(
            uri=os.getenv("NEO4J_URI"),
            user=os.getenv("NEO4J_USER"),
            password=os.getenv("NEO4J_PASSWORD")
        )
        
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        
        try:
            self.cross_encoder = CrossEncoder(
                model_name,
                device=device,
                max_length=512
            )
        except Exception as e:
            logging.error(f"Error loading cross-encoder model: {e}")
            raise

    def _standardize_elastic_results(
        self, 
        elastic_results: List[Dict[str, Any]]
    ) -> List[SearchResult]:
        """
        Convert Elasticsearch results to standardized format.
        """
        return [
            SearchResult(
                title=result['title'],
                description=result.get('description', ''),
                price=result.get('price', 0.0),
                resumen=result.get('resumen', ''),
                source='elastic',
                original_score=result['score']
            )
            for result in elastic_results
        ]

    def _standardize_neo4j_results(
        self, 
        neo4j_results: List[Dict[str, Any]]
    ) -> List[SearchResult]:
        """
        Convert Neo4j results to standardized format.
        """
        return [
            SearchResult(
                title=result['title'],
                description=result.get('description', ''),
                price=result.get('price', 0.0),
                url=result.get('url'),
                source='neo4j',
                original_score=result['similarity']
            )
            for result in neo4j_results
        ]

    async def _get_combined_results(
        self, 
        query: str,
        size_per_source: int = 10
    ) -> List[SearchResult]:
        """
        Get and combine results from both sources.
        """
        # Get results from both sources concurrently
        elastic_results = await self.es_handler.search_products_bm25(query, size=size_per_source)
        neo4j_results = await self.neo4j_handler.semantic_search(query, top_k=size_per_source)

        # Standardize results
        standardized_elastic = self._standardize_elastic_results(elastic_results)
        standardized_neo4j = self._standardize_neo4j_results(neo4j_results)

        # Combine results
        return standardized_elastic + standardized_neo4j

    def _prepare_reranking_pairs(
        self,
        query: str,
        results: List[SearchResult]
    ) -> List[List[str]]:
        """
        Prepare text pairs for cross-encoder reranking.
        """
        pairs = []
        for result in results:
            # Combine relevant text fields for comprehensive matching
            document_text = (
                f"Title: {result.title}\n"
                f"Description: {result.description}\n"
                f"Summary: {result.resumen if result.resumen else ''}"
            ).strip()
            
            pairs.append([query, document_text])
        
        return pairs

    async def search_and_rerank(
        self,
        query: str,
        size_per_source: int = 10,
        final_size: int = 10,
        batch_size: int = 32
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search and rerank results.

        Args:
            query: Search query string
            size_per_source: Number of results to get from each source
            final_size: Number of results to return after reranking
            batch_size: Batch size for cross-encoder processing

        Returns:
            List of reranked results with scores and metadata
        """
        try:
            # Get combined results
            combined_results = await self._get_combined_results(query, size_per_source)
            
            if not combined_results:
                return []

            # Prepare pairs for reranking
            pairs = self._prepare_reranking_pairs(query, combined_results)

            # Compute cross-encoder scores in batches
            scores = []
            for i in range(0, len(pairs), batch_size):
                batch = pairs[i:i + batch_size]
                try:
                    batch_scores = self.cross_encoder.predict(
                        batch,
                        batch_size=batch_size,
                        show_progress_bar=False
                    )
                    scores.extend(batch_scores)
                except Exception as e:
                    logging.error(f"Error in cross-encoder prediction: {e}")
                    raise

            # Combine results with new scores and sort
            results_with_scores = list(zip(combined_results, scores))
            results_with_scores.sort(key=lambda x: x[1], reverse=True)

            # Format final results
            reranked_results = []
            for idx, (result, new_score) in enumerate(results_with_scores[:final_size]):
                reranked_results.append({
                    'title': result.title,
                    'description': result.description,
                    'price': result.price,
                    'url': result.url,
                    'resumen': result.resumen,
                    'source': result.source,
                    'score': float(new_score),
                    'original_score': result.original_score,
                    'rank': idx + 1
                })

            return reranked_results

        except Exception as e:
            logging.error(f"Error in search and rerank: {e}")
            raise