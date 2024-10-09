import asyncio
from scraper.costco_scraper import CostcoScraper
from database.mongo_handler import MongoHandler
from database.postgres_handler import PostgresHandler
from database.neo4j_handler import Neo4jHandler
from dotenv import load_dotenv
import os

# Cargar variables de entorno
load_dotenv()

async def main():
    # Configuraciones de conexión
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/costco_db")
    postgres_uri = os.getenv("POSTGRES_URI", "postgresql://user:password@localhost:5434/costco_db")
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "password")

    # Inicializar handlers de base de datos
    mongo_handler = MongoHandler(mongo_uri)
    postgres_handler = PostgresHandler(postgres_uri)
    neo4j_handler = Neo4jHandler(neo4j_uri, neo4j_user, neo4j_password)
    
    # Inicializar y ejecutar el scraper
    scraper = CostcoScraper(mongo_handler, postgres_handler, neo4j_handler)
    await scraper.run()

if __name__ == "__main__":
    asyncio.run(main())

