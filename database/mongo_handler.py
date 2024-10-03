from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

class MongoHandler:
    def __init__(self):
        self.client = MongoClient(os.getenv("MONGO_URI"))
        self.db = self.client.costco_db
        self.collection = self.db.products

    async def store(self, product_info):
        self.collection.insert_one(product_info)