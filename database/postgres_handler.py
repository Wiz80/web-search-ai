import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import Json
import os
import logging

load_dotenv()

class PostgresHandler:
    def __init__(self, connection_string):
        self.conn = psycopg2.connect(connection_string)
        self.cur = self.conn.cursor()
        self.create_table()

    @staticmethod
    def clean_price(price_str):
        if not price_str:
            return None
        # Eliminar el símbolo de moneda y las comas
        price_str = price_str.replace('$', '').replace(',', '')
        try:
            # Convertir a float
            return float(price_str)
        except ValueError:
            # Si no se puede convertir, retornar None
            return None

    def create_table(self):
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                title TEXT,
                description TEXT,
                price_without_discount NUMERIC,
                price NUMERIC,
                url TEXT UNIQUE,
                similar_purchases JSONB,
                most_bought JSONB,
                recommendations JSONB,
                similar_products JSONB,
                other_members_also_purchased JSONB
            )
        """)
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS urls_to_scrape (
                id SERIAL PRIMARY KEY,
                url TEXT UNIQUE,
                already_scraped BOOLEAN DEFAULT FALSE
            )
        """)
        self.conn.commit()
    
    async def url_exists(self, url):
        query = """
            SELECT EXISTS(SELECT 1 FROM urls_to_scrape WHERE url = %s)
        """
        self.cur.execute(query, (url,))
        return self.cur.fetchone()[0]

    
    async def store_url(self, url):
        if not await self.url_exists(url):
            query = """
                INSERT INTO urls_to_scrape (url)
                VALUES (%s)
                ON CONFLICT (url) DO NOTHING
            """
            self.cur.execute(query, (url,))
            self.conn.commit()
            return True
        return False
    
    async def get_urls_to_scrape(self, limit=100):
        query = """
            SELECT url FROM urls_to_scrape
            WHERE already_scraped = FALSE
            LIMIT %s
        """
        self.cur.execute(query, (limit,))
        return [row[0] for row in self.cur.fetchall()]
    
    async def mark_url_as_scraped(self, url):
        query = """
            UPDATE urls_to_scrape
            SET already_scraped = TRUE
            WHERE url = %s
        """
        self.cur.execute(query, (url,))
        self.conn.commit()

    async def store(self, product_info):
        query = """
            INSERT INTO products (
                title, description, price_without_discount, price, url,
                similar_purchases, most_bought, recommendations,
                similar_products, other_members_also_purchased
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (url) DO UPDATE SET
                title = EXCLUDED.title,
                description = EXCLUDED.description,
                price_without_discount = EXCLUDED.price_without_discount,
                price = EXCLUDED.price,
                similar_purchases = EXCLUDED.similar_purchases,
                most_bought = EXCLUDED.most_bought,
                recommendations = EXCLUDED.recommendations,
                similar_products = EXCLUDED.similar_products,
                other_members_also_purchased = EXCLUDED.other_members_also_purchased
        """
        try:
            self.cur.execute(query, (
                product_info['title'],
                product_info['description'],
                self.clean_price(product_info['price_without_discount']),
                self.clean_price(product_info['price']),
                product_info['url'],
                Json(product_info['similar_purchases']),
                Json(product_info['most_bought']),
                Json(product_info['recommendations']),
                Json(product_info['similar_products']),
                Json(product_info['other_members_also_purchased'])
            ))
            self.conn.commit()
        except psycopg2.Error as e:
            logging.error(f"Error al almacenar producto en PostgreSQL: {e}")
            self.conn.rollback()
            raise