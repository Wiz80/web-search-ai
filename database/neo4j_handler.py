from neo4j import GraphDatabase
from dotenv import load_dotenv
import os

load_dotenv()

class Neo4jHandler:
    def __init__(self):
        uri = os.getenv("NEO4J_URI")
        user = os.getenv("NEO4J_USER")
        password = os.getenv("NEO4J_PASSWORD")
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    async def store(self, product_info):
        with self.driver.session() as session:
            session.write_transaction(self._create_and_return_product, product_info)

    @staticmethod
    def _create_and_return_product(tx, product_info):
        query = (
            "CREATE (p:Product {title: $title, description: $description, price: $price, url: $url}) "
            "RETURN p"
        )
        result = tx.run(query, title=product_info['title'], description=product_info['description'],
                        price=product_info['price'], url=product_info['url'])
        return result.single()[0]
