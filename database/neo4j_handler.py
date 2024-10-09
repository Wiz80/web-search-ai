from neo4j import GraphDatabase
from dotenv import load_dotenv
import os

load_dotenv()

class Neo4jHandler:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

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
            "p.other_members_also_purchased = $other_members_also_purchased "
            "RETURN p"
        )
        result = tx.run(query, **product_info)
        return result.single()[0]
