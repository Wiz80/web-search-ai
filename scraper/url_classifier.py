import openai
from openai import OpenAI
import os
from dotenv import load_dotenv, find_dotenv

_ = load_dotenv(find_dotenv())
openai_client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])

async def is_product_url_llm(url):
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
    
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres un asistente que determina si una URL es de un producto de Costco México."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=10,
            n=1,
            temperature=0.5,
        )
        
        answer = response.choices[0].message.content.strip().lower()
        return answer == 'sí' or answer == 'si'
    except Exception as e:
        print(f"Error al clasificar la URL: {e}")
        return False