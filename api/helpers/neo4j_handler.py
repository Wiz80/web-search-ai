from neo4j import GraphDatabase
from dotenv import load_dotenv
from openai import OpenAI
from typing import List, Dict, Any, Optional
import os

load_dotenv()

class Neo4jHandler:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    async def store(self, product_info):
        with self.driver.session() as session:
            session.write_transaction(self._create_and_return_product, product_info)

    @staticmethod
    def _create_and_return_product(tx, product_info):
        query = (
            "MERGE (p:Product {url: $url}) "
            "SET p.title = $title, "
            "p.description = $description, "
            "p.price_without_discount = $price_without_discount, "
            "p.price = $price, "
            "p.similar_purchases = $similar_purchases, "
            "p.most_bought = $most_bought, "
            "p.recommendations = $recommendations, "
            "p.similar_products = $similar_products, "
            "p.other_members_also_purchased = $other_members_also_purchased, "
            "p.product_resume = $product_resume, "
            "p.product_context = $product_context "
            "RETURN p"
        )
        result = tx.run(query, **product_info)
        return result.single()[0]

    def create_vector_index(self) -> None:
        """
        Creates a vector index in Neo4j for product description embeddings.
        The index enables efficient similarity search across product descriptions.
        """
        with self.driver.session() as session:
            session.run("""
                CREATE VECTOR INDEX product_description_embeddings IF NOT EXISTS
                FOR (p:Product) ON (p.descriptionEmbedding)
                OPTIONS {
                    indexConfig: {
                        `vector.dimensions`: 1536,
                        `vector.similarity_function`: 'cosine'
                    }
                }
            """)


    async def semantic_search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Performs semantic search across products using description embeddings.

        Args:
            query: Search query text
            top_k: Number of similar products to return (default: 5)

        Returns:
            List of similar products with their similarity scores
        """
        # Generate embedding for the search query
        query_embedding = await self._generate_embedding(query)

        with self.driver.session() as session:
            return session.read_transaction(
                self._execute_semantic_search,
                query_embedding,
                top_k
            )

    @staticmethod
    def _execute_semantic_search(tx, query_embedding: List[float], top_k: int) -> List[Dict[str, Any]]:
        """
        Executes the semantic search query in Neo4j.

        Args:
            tx: Neo4j transaction
            query_embedding: Vector embedding of the search query
            top_k: Number of results to return

        Returns:
            List of similar products with their similarity scores
        """
        query = """
        CALL db.index.vector.queryNodes(
            'product_description_embeddings',
            $top_k,
            $query_embedding
        ) YIELD node AS product, score
        RETURN 
            product.title AS title,
            product.description AS description,
            product.price AS price,
            product.url AS url,
            score AS similarity
        ORDER BY similarity DESC
        """
        result = tx.run(query, query_embedding=query_embedding, top_k=top_k)
        return [dict(record) for record in result]

    async def _generate_embedding(self, text: str) -> List[float]:
        """
        Generates an embedding for the given text using OpenAI's API.

        Args:
            text: Text to generate embedding for

        Returns:
            Vector embedding as a list of floats
        """
        response = self.openai_client.embeddings.create(
            model="text-embedding-ada-002",
            input=text
        )
        return response.data[0].embedding

    def close(self) -> None:
        """Closes the Neo4j driver connection."""
        self.driver.close()