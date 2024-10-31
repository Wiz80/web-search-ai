
from fastapi import HTTPException
from typing import Dict
from datetime import datetime
from api.helpers.neo4j_handler import Neo4jHandler 
import os

neo4j_handler = Neo4jHandler(
    uri=os.getenv("NEO4J_URI"),
    user=os.getenv("NEO4J_USER"),
    password=os.getenv("NEO4J_PASSWORD")
)

class StoreEmbeddingNeo4j:
    """
    Handles the setup and management of semantic search functionality in Neo4j.
    Includes index verification and embedding population.
    """
    def __init__(self):
        """
        Initialize the setup handler with a Neo4j semantic handler.

        Args:
            neo4j_handler: Instance of Neo4jSemanticHandler for database operations
        """
        self.neo4j_handler = neo4j_handler
        self.population_status = {
            "is_running": False,
            "started_at": None,
            "completed_at": None,
            "processed_count": 0,
            "error": None
        }

    async def check_index_exists(self) -> bool:
        """
        Verifies if the vector index exists in Neo4j.

        Returns:
            bool: True if index exists, False otherwise
        """
        try:
            with self.neo4j_handler.driver.session() as session:
                result = session.run("""
                    SHOW VECTOR INDEXES
                    YIELD name
                    WHERE name = 'product_description_embeddings'
                    RETURN count(*) as count
                """)
                return result.single()["count"] > 0
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error checking index: {str(e)}")

    async def create_index_if_not_exists(self) -> Dict[str, bool]:
        """
        Creates the vector index if it doesn't already exist.

        Returns:
            Dict containing status of index creation
        """
        try:
            exists = await self.check_index_exists()
            if not exists:
                await self.neo4j_handler.create_vector_index()
                return {"created": True, "message": "Vector index created successfully"}
            return {"created": False, "message": "Vector index already exists"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error creating index: {str(e)}")

    async def start_population(self) -> None:
        """
        Starts the population of embeddings for all products that don't have them.
        Updates status during the process.
        """
        if self.population_status["is_running"]:
            return

        self.population_status.update({
            "is_running": True,
            "started_at": datetime.now().isoformat(),
            "completed_at": None,
            "processed_count": 0,
            "error": None
        })

        try:
            with self.neo4j_handler.driver.session() as session:
                # Get count of products without embeddings
                result = session.run("""
                    MATCH (p:Product)
                    WHERE p.descriptionEmbedding IS NULL
                    AND p.description IS NOT NULL
                    RETURN count(p) as count
                """)
                total_to_process = result.single()["count"]

                # Process products in batches
                products = session.run("""
                    MATCH (p:Product)
                    WHERE p.descriptionEmbedding IS NULL
                    AND p.description IS NOT NULL
                    RETURN p.url AS url, p.product_context AS description
                """)

                for product in products:
                    if product["description"]:
                        embedding = await self.neo4j_handler._generate_embedding(product["description"])
                        session.run("""
                            MATCH (p:Product {url: $url})
                            SET p.descriptionEmbedding = $embedding
                        """, url=product["url"], embedding=embedding)
                        
                        self.population_status["processed_count"] += 1

            self.population_status.update({
                "is_running": False,
                "completed_at": datetime.now().isoformat()
            })

        except Exception as e:
            self.population_status.update({
                "is_running": False,
                "error": str(e),
                "completed_at": datetime.now().isoformat()
            })
            raise
