from elasticsearch import Elasticsearch
from neo4j import GraphDatabase
import openai
import logging
from datetime import datetime
import os
from dotenv import load_dotenv

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

class ProductContextService:
    def __init__(self):
        # Inicializar clientes de bases de datos
        self.es_client = Elasticsearch(['http://localhost:9200'])
        self.neo4j_driver = GraphDatabase.driver(
            os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
            auth=(os.getenv('NEO4J_USER', 'neo4j'), os.getenv('NEO4J_PASSWORD'))
        )
        self.openai_client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    async def generate_product_context(self, title: str, description: str) -> str:
        """Genera el contexto enriquecido del producto usando OpenAI."""
        prompt = f"""
        **Instrucción General:**
        Eres un Prompt Engineer Senior y Especialista en Modelos de Lenguaje Natural.
        
        ### Objetivo del Documento:
        Elabora un informe detallado sobre el producto: {title}

        ### Estructura del Documento:
        1. Descripción General
        2. Instrucciones de Uso
        3. Propósito Principal
        4. Contexto de Aplicación
        5. Casos de Uso Específicos
        6. Ventajas y Limitaciones
        7. Sinergias y Asociaciones Relevantes
        8. Preguntas Frecuentes
        9. Conclusión y Recomendaciones
        10. Especificaciones Técnicas

        **Datos proporcionados:**
        - Nombre del Producto: {title}
        - Descripción Inicial: {description}
        """

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error generando contexto con OpenAI: {e}")
            raise

    async def update_elasticsearch_context(self, product_id: str, context: str):
        """Actualiza el contexto del producto en Elasticsearch."""
        try:
            update_body = {
                "doc": {
                    "product_context": context,
                    "context_updated_at": datetime.now().isoformat()
                }
            }
            response = self.es_client.update(
                index="products",
                id=product_id,
                body=update_body
            )
            return response
        except Exception as e:
            logger.error(f"Error actualizando Elasticsearch: {e}")
            raise

    async def update_neo4j_context(self, product_url: str, context: str):
        """Actualiza el contexto del producto en Neo4j."""
        try:
            with self.neo4j_driver.session() as session:
                result = session.write_transaction(
                    lambda tx: tx.run(
                        """
                        MATCH (p:Product {url: $url})
                        SET p.product_context = $context,
                            p.context_updated_at = datetime()
                        RETURN p
                        """,
                        url=product_url,
                        context=context
                    )
                )
                return result
        except Exception as e:
            logger.error(f"Error actualizando Neo4j: {e}")
            raise