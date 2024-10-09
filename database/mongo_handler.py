from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

class MongoHandler:
    def __init__(self, connection_string):
        self.client = MongoClient(connection_string)
        self.db = self.client.costco_db
        self.collection = self.db.products

    async def store(self, product_info):
        self.collection.update_one(
            {'url': product_info['url']},
            {'$set': product_info},
            upsert=True
        )