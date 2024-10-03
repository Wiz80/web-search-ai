import asyncio
from playwright.async_api import async_playwright
from scraper.url_classifier import URLClassifier
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
        self.url_classifier = URLClassifier()
        self.base_url = "https://www.costco.com.mx"

    async def run(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()

            # Extraer URLs (7 minutos)
            start_time = asyncio.get_event_loop().time()
            urls = await self.extract_urls(page, duration=420)

            # Scrapear productos (7 minutos)
            await self.scrape_products(page, urls, browser, duration=420)

            await browser.close()

    async def extract_urls(self, page, browser, duration):
        urls = []
        start_time = asyncio.get_event_loop().time()
        try:
            while asyncio.get_event_loop().time() - start_time < duration:
                await page.goto(self.base_url, wait_until='networkidle')

                # Esperar a que se cargue el cuerpo de la página
                await page.wait_for_selector("body")

                # Buscar todos los links que coincidan con el patrón de productos
                links = await page.query_selector_all("a[href^='/'][href*='/p/']")

                for link in links:
                    href = await link.get_attribute("href")
                    full_url = f"{self.base_url}{href}" if href.startswith('/') else href
                    
                    # Verificar si la URL es de un producto usando el LLM
                    if await self.is_product_url_llm(full_url):
                        urls.append(full_url)

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
        
    async def is_product_url_llm(self, url):
        prompt = f"""
        Determina si la siguiente URL corresponde a un producto de Costco México.
        
        URL: {url}
        
        Ejemplos de URLs de productos:
        - https://www.costco.com.mx/Grocery/Grocery/Aceites-y-Vinagres/Capullo-Aceite-de-Canola-37-l/p/500276
        - https://www.costco.com.mx/Linea-Blanca-y-Cocina/Linea-Blanca/Lavadoras-y-Secadoras/Maytag-Lavadora-25-KG/p/682698
        - https://www.costco.com.mx/Grocery/Grocery/Higienicos-y-Desechables/Kirkland-Signature-Papel-Higienico-30-pzas/p/6262016
        - https://www.costco.com.mx/Grocery/Grocery/Detergentes/Mas-Color-Detergente-Liquido-9-L/p/505169
        - https://www.costco.com.mx/Jardin-Flores-y-Mascotas/Mascotas/Perros/Kirkland-Signature-Natures-Domain-Alimento-para-Perro-con-Salmon-y-Camote-1587kg/p/470974
        
        Ejemplos de URLs que no son productos:
        - https://www.costco.com.mx/grocery
        - https://www.costco.com.mx/search?text=KWKETO
        - https://atencionalsocio.costco.com.mx/app/answers/detail/a_id/227
        - https://atencionalsocio.costco.com.mx/app/answers/detail/a_id/232
        - https://www3.costco.com.mx/gasolina
        - https://www.costco.com.mx/tiresearch


        Responde con 'Sí' si es una URL de producto, o 'No' si no lo es.
        """
        
        response = openai.Completion.create(
            engine="text-davinci-002",
            prompt=prompt,
            max_tokens=10,
            n=1,
            stop=None,
            temperature=0.5,
        )
        
        answer = response.choices[0].text.strip().lower()
        return answer == 'sí' or answer == 'si'

                

    async def scrape_products(self, page, urls, duration):
        start_time = asyncio.get_event_loop().time()
        
        for url in urls:
            if asyncio.get_event_loop().time() - start_time > duration:
                break

            await page.goto(url)
            product_info = await extract_product_info(page)
            
            # Almacenar en bases de datos
            try:
                await self.mongo_handler.store(product_info)
                await self.postgres_handler.store(product_info)
                await self.neo4j_handler.store(product_info)
            except Exception as e:
                print(f"Error al almacenar producto: {e}")
                # Asegurar que al menos se almacene en PostgreSQL
                await self.postgres_handler.store(product_info)