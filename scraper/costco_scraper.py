import asyncio
from playwright.async_api import async_playwright
from scraper.url_classifier import is_product_url_llm
from utils.helpers import extract_product_info
from scraper.get_content import save_scraped_content
from bs4 import BeautifulSoup
import logging
import openai

class CostcoScraper:
    def __init__(self, mongo_handler, postgres_handler, neo4j_handler):
        self.mongo_handler = mongo_handler
        self.postgres_handler = postgres_handler
        self.neo4j_handler = neo4j_handler
        self.base_url = "https://www.costco.com.mx/Electronicos/Apple/Mac/Apple-MacBook-Air-13-Chip-M2-512-GB-Plata/p/673623"

    async def run(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()

            # Extraer URLs (7 minutos)
            start_time = asyncio.get_event_loop().time()
            await self.extract_urls(page, browser, duration=420)

            # Scrapear productos (7 minutos)
            await self.scrape_products(page,duration=420)

            await browser.close()

    async def extract_urls(self, page, browser, duration):
        urls = []
        start_time = asyncio.get_event_loop().time()
        new_urls_count = 0
        try:
            while asyncio.get_event_loop().time() - start_time < duration:
                await page.goto(self.base_url, wait_until='networkidle')

                # Esperar a que se cargue el cuerpo de la página
                await page.wait_for_selector("body")

                # Buscar todos los links que coincidan con un patron
                links = await page.query_selector_all("a[href^='/'][href*='/p/']")

                for link in links:
                    href = await link.get_attribute("href")
                    full_url = f"{self.base_url}{href}" if href.startswith('/') else href
                    
                    # Verificar si la URL es de un producto usando el LLM
                    if await is_product_url_llm(full_url):
                        if await self.postgres_handler.store_url(full_url):
                            print(full_url + " nueva url guardada")
                            new_urls_count += 1

                # Navegar a una página diferente o hacer clic en "Siguiente" si existe
                # Esta parte dependerá de la estructura del sitio de Costco
                next_page = await page.query_selector("a.next-page")
                if next_page:
                    await next_page.click()
                else:
                    # Si no hay más páginas, podemos romper el ciclo
                    break

        except Exception as e:
            print(f"Error durante la extracción de URLs: {e}")
        finally:
            return urls


    async def scrape_products(self, page, duration):
        start_time = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start_time < duration:
            urls_to_scrape = await self.postgres_handler.get_urls_to_scrape(limit=10)  # Obtener 10 URLs a la vez
            
            if not urls_to_scrape:
                print("No hay más URLs para scrapear")
                break

            for url in urls_to_scrape:
                try:
                    await page.goto(url, wait_until='networkidle')
                    product_info = await extract_product_info(page)
                    
                    if product_info:
                        # Almacenar en bases de datos
                        try:
                            await self.mongo_handler.store(product_info)
                            await self.postgres_handler.store(product_info)
                            await self.neo4j_handler.store(product_info)
                        except Exception as e:
                            print(f"Error al almacenar producto: {e}")
                    
                    # Marcar la URL como scrapeada
                    await self.postgres_handler.mark_url_as_scraped(url)
                
                except Exception as e:
                    print(f"Error al scrapear la URL {url}: {e}")
                    # Aún así, marcamos la URL como scrapeada para evitar bucles infinitos
                    await self.postgres_handler.mark_url_as_scraped(url)

                if asyncio.get_event_loop().time() - start_time > duration:
                    break