import asyncio
from scraper.costco_scraper import CostcoScraper
from database.mongo_handler import MongoHandler
from database.postgres_handler import PostgresHandler
from database.neo4j_handler import Neo4jHandler

async def main():
    mongo_handler = MongoHandler()
    postgres_handler = PostgresHandler()
    neo4j_handler = Neo4jHandler()
    
    scraper = CostcoScraper(mongo_handler, postgres_handler, neo4j_handler)
    await scraper.run()

if __name__ == "__main__":
    asyncio.run(main())