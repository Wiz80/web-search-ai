import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

class PostgresHandler:
    def __init__(self):
        self.conn = psycopg2.connect(os.getenv("POSTGRES_URI"))
        self.cur = self.conn.cursor()
        self.create_table()

    def create_table(self):
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                title TEXT,
                description TEXT,
                price DECIMAL,
                url TEXT,
                extraction_date TIMESTAMP
            )
        """)
        self.conn.commit()

    async def store(self, product_info):
        self.cur.execute("""
            INSERT INTO products (title, description, price, url, extraction_date)
            VALUES (%s, %s, %s, %s, NOW())
        """, (product_info['title'], product_info['description'], product_info['price'], product_info['url']))
        self.conn.commit()
