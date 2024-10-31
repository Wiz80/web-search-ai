from playwright.async_api import Page
from bs4 import BeautifulSoup
import json
import logging
import openai
from openai import OpenAI
import os

import re

from dotenv import load_dotenv, find_dotenv
_ = load_dotenv(find_dotenv())
openai_client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])

def clean_and_parse_json(raw_response):
    # Eliminar cualquier texto antes o después del JSON
    json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
    if json_match:
        json_str = json_match.group()
    else:
        raise ValueError("No se encontró un objeto JSON válido en la respuesta")

    # Intenta parsear el JSON
    try:
        content_json = json.loads(json_str)
    except json.JSONDecodeError as e:
        json_str = json_str.replace("'", '"')
        json_str = re.sub(r'(\w+):', r'"\1":', json_str)
        
        try:
            content_json = json.loads(json_str)
        except json.JSONDecodeError:
            raise ValueError(f"No se pudo parsear el JSON después de intentar corregirlo: {e}")

    return content_json


async def extract_product_info(page: Page):
    try:
        # Navigate to the URL and wait for the content to load
        await page.goto(page.url, wait_until='networkidle')

        # Wait for the body to load
        await page.wait_for_selector("body")

        # Scroll to load dynamic content
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
        await page.wait_for_timeout(2000)  # Additional wait after scrolling

        # Get HTML content
        html_content = await page.content()
        soup = BeautifulSoup(html_content, 'html.parser')

        # Extract specific product information
        title = await page.title()

        html_content = await page.content()
        soup = BeautifulSoup(html_content, 'html.parser')
        text_content = soup.get_text(separator="\n", strip=True) 

        llm_response = await extract_product_info_from_url(text_content)

        content_json = clean_and_parse_json(llm_response)
        # Construct the product information dictionary
        product_info = {
            'title': title,
            'description': content_json['description'],
            'price_without_discount': content_json['price_without_discount'],
            'price': content_json['price'],
            'url': page.url,
            'similar_purchases': content_json['similar_purchases'],
            'most_bought': content_json['most_bought'],
            'recommendations': content_json['recommendations'],
            'similar_products': content_json['similar_products'],
            'other_members_also_purchased': content_json['other_members_also_purchased']
        }

        return product_info

    except Exception as e:
        logging.error(f"An error occurred while extracting product info from {page.url}: {e}")
        return None


async def extract_product_info_from_url(content):
    prompt = f"""
        El texto que te estoy compartiendo es la descripción de un producto de Costco México.

        Tu tarea es extraer de este texto la información relevante para añadir a una base de datos relacional.

        El formato de la respuesta DEBE ser un JSON válido con la siguiente estructura:

        {{
            "description": "Descripción del producto",
            "price_without_discount": "Precio del producto sin descuento",
            "price": "Precio del producto con descuento",
            "other_members_also_purchased": ["Títulos de los productos que otros miembros han comprado similares a este"],
            "similar_purchases": ["Título de los productos similares a este"],
            "most_bought": ["Título de los productos más comprados"],
            "recommendations": ["Título de los productos recomendados"],
            "similar_products": ["Título de los productos similares a este"]
        }}

        IMPORTANTE:
        1. Asegúrate de que el JSON sea válido y pueda ser parseado por json.loads().
        2. No incluyas ningún texto adicional antes o después del JSON.
        3. Usa comillas dobles para las claves y valores string.
        4. Si algún campo no está presente en el texto, déjalo como una lista o string vacío según corresponda.

        Este es el contenido:
        {content}
    """
            
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres un asistente que extrae información estructurada de descripciones de productos."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
        )
    
        answer = response.choices[0].message.content.strip()
        return answer
    except Exception as e:
        print(f"Error al clasificar la URL: {e}")
        return False