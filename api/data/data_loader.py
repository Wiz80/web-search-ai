import pandas as pd
import asyncio
from api.helpers.elasticsearch_handler import ElasticsearchHandler
from api.helpers.neo4j_handler import Neo4jHandler
from typing import Dict, Any
import logging
import os
from dotenv import load_dotenv

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class DataLoader:
    def __init__(self, elastic_hosts: list, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        self.es_handler = ElasticsearchHandler(elastic_hosts)
        self.neo4j_handler = Neo4jHandler(neo4j_uri, neo4j_user, neo4j_password)
        
    async def process_list_field(self, field_value: str) -> list:
        """Procesa campos que contienen listas en formato string."""
        if not field_value or field_value == '[]':
            return []
        try:
            # Eliminar caracteres innecesarios y dividir por comas
            clean_value = field_value.strip('[]').replace('"', '')
            if not clean_value:
                return []
            return [item.strip() for item in clean_value.split(',')]
        except Exception as e:
            logging.error(f"Error procesando campo lista: {e}")
            return []

    def prepare_product_data(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Prepara los datos del producto para su inserción."""
        return {
            'url': row['url'],
            'title': row['title'],
            'description': row['description'],
            'price_without_discount': float(row['price_without_discount']) if pd.notna(row['price_without_discount']) else None,
            'price': float(row['price']) if pd.notna(row['price']) else None,
            'similar_purchases': row['similar_purchases'],
            'most_bought': row['most_bought'],
            'recommendations': row['recommendations'],
            'similar_products': row['similar_products'],
            'other_members_also_purchased': row['other_members_also_purchased'],
            'product_resume': row['resumen_producto'],
            'product_context': ''
        }

    async def load_data(self, csv_path: str):
        """Carga los datos del CSV en Elasticsearch y Neo4j."""
        try:
            # Leer el CSV
            path = os.getcwd() + '/api/data/db_marketplace_clean.csv'
            df = pd.read_csv(path)
            logging.info(f"Leyendo {len(df)} registros del CSV")

            # Crear índice en Elasticsearch
            self.es_handler.create_index_products()
            
            # Crear índice vectorial en Neo4j
            self.neo4j_handler.create_vector_index()

            # Procesar cada fila
            for index, row in df.iterrows():
                try:
                    # Preparar datos
                    product_data = self.prepare_product_data(row)
                    
                    # Insertar en Elasticsearch
                    await self.es_handler.store_product(product_data, index=index)
                    logging.info(f"Producto {index + 1} insertado en Elasticsearch")

                    # Insertar en Neo4j
                    await self.neo4j_handler.store(product_data)
                    logging.info(f"Producto {index + 1} insertado en Neo4j")

                except Exception as e:
                    logging.error(f"Error procesando producto {index + 1}: {e}")
                    continue

            logging.info("Carga de datos completada")

        except Exception as e:
            logging.error(f"Error en la carga de datos: {e}")
        finally:
            self.neo4j_handler.close()

async def execute_data_loader():
    # Cargar variables de entorno
    load_dotenv()
    
    # Configuración
    elastic_hosts = ['http://localhost:9200']  # Ajusta según tu configuración
    neo4j_uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    neo4j_user = os.getenv('NEO4J_USER', 'neo4j')
    neo4j_password = os.getenv('NEO4J_PASSWORD')

    if not neo4j_password:
        raise ValueError("NEO4J_PASSWORD no está configurado en las variables de entorno")

    # Crear instancia del cargador
    loader = DataLoader(
        elastic_hosts=elastic_hosts,
        neo4j_uri=neo4j_uri,
        neo4j_user=neo4j_user,
        neo4j_password=neo4j_password
    )

    # Cargar datos
    await loader.load_data('db_marketplace_clean.csv')