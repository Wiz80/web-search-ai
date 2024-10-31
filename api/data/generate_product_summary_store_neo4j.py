from openai import OpenAI
import os
import pandas as pd
from dotenv import load_dotenv
from neo4j import GraphDatabase

# Cargar variables de entorno
load_dotenv()


client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Clase para manejar la conexión con Neo4j
class Neo4jHandler:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def store(self, product_info):
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
            "p.other_members_also_purchased = $other_members_also_purchased, "
            "p.resumen_producto = $resumen_producto "
            "RETURN p"
        )
        tx.run(query, **product_info)

    def close(self):
        self.driver.close()

# Función para generar el resumen del producto
def generate_product_summary(title):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": """
             Eres un asistente que resume títulos y descripciones de productos en descripciones muy cortas y concisas.
             Resumirás los títulos de productos de costco, una empresa de ventas de productos al por mayor.
             La idea es que este resumen que darás sea como por ejemplo:
             Titulo del producto: Karma Tapete 160 cm x 214 cm | Costco México  
             Descripción corta: Un tapete de 160 cm x 214 cm con una tapa de cobre y una capa de plástico. Tiene unas cuantas de colores y patrones.
             
             La salida que espero es:
             Tapete 160 cm x 214 cm

             Otro ejemplo:
             Título del producto: Empire Lighting, Lámpara Colgante LED Charlton | Costco M... 
             Descripción corta: La Lámpara Colgante LED Charlton de Empire Lighting brinda un impacto dramático instantáneo a tu entrada, sala de estar o comedor. Diez luces colocadas tanto en dirección horizontal como vertical brindan una amplia distribución de la luz, y el tinte del vidrio ahumado agrega un estilo visual cuando se ilumina.

             La salida que espero es:
             Lámpara Colgante LED

             El resumen debe ser lo más corto y conciso.
             """},
            {"role": "user", "content": f"Resume el siguiente título de producto en una descripción corta y general: {title}"}
        ]
    )
    return response.choices[0].message.content

# Función para leer y actualizar el CSV original
def process_csv(input_file, output_file):
    df = pd.read_csv(input_file)

    # Crear el campo 'resumen_producto'
    df['resumen_producto'] = df['title'].apply(generate_product_summary)

    # Guardar el nuevo CSV con el campo 'resumen_producto'
    df.to_csv(output_file, index=False)

    return df

# Función para cargar los datos en el grafo de Neo4j
def load_data_to_neo4j(df, neo4j_handler):
    for _, row in df.iterrows():
        product_info = {
            'url': row['url'],
            'title': row['title'],
            'description': row['description'],
            'price_without_discount': row['price_without_discount'],
            'price': row['price'],
            'similar_purchases': row['similar_purchases'],
            'most_bought': row['most_bought'],
            'recommendations': row['recommendations'],
            'similar_products': row['similar_products'],
            'other_members_also_purchased': row['other_members_also_purchased'],
            'resumen_producto': row['resumen_producto']
        }
        neo4j_handler.store(product_info)

# Variables de archivo y conexión
input_file = 'helpers/products.csv'  # Nombre del archivo CSV de entrada
output_file = 'helpers/products_new.csv'  # Nombre del archivo CSV de salida

neo4j_uri = os.getenv("NEO4J_URI")
neo4j_user = os.getenv("NEO4J_USER")
neo4j_password = os.getenv("NEO4J_PASSWORD")

# Procesar el CSV y cargar los datos en Neo4j
if __name__ == "__main__":
    # Procesar el archivo CSV
    df = process_csv(input_file, output_file)

    # Conectar y cargar en Neo4j
    neo4j_handler = Neo4jHandler(neo4j_uri, neo4j_user, neo4j_password)
    load_data_to_neo4j(df, neo4j_handler)
    neo4j_handler.close()

    print(f"Archivo CSV procesado y guardado en {output_file}. Datos cargados en Neo4j.")
