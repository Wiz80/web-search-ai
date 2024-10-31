from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import List
from api.helpers.neo4j_handler import Neo4jHandler 
from api.helpers.elasticsearch_handler import ElasticsearchHandler
from api.data.data_loader import execute_data_loader
from api.models import SearchQuery, ProductSearchResult, ProductUpdateRequest
from api.store.store_embedding_neo4j import StoreEmbeddingNeo4j
from api.store.product_context import ProductContextService
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


import os


service = ProductContextService()

app = FastAPI()

# Initialize handlers
neo4j_handler = Neo4jHandler(
    uri=os.getenv("NEO4J_URI"),
    user=os.getenv("NEO4J_USER"),
    password=os.getenv("NEO4J_PASSWORD")
)

elasticsearch_handler = ElasticsearchHandler(
    hosts=['http://localhost:9200']
)


@app.get("/recommendations/", response_model=List[str])
async def recommedations(q: str):
    """
    Returns a list of recommended products based on the search term.
    """
    recommendations_response = await elasticsearch_handler.get_recommendations(q)
    return recommendations_response

@app.post("/store-embedding", response_model=List[str])
async def store_embedding(
    background_tasks: BackgroundTasks,
) -> JSONResponse:
    """
    Endpoint to setup and initialize semantic search functionality.
    Checks/creates index and starts embedding population in the background.

    Args:
        background_tasks: FastAPI background tasks handler

    Returns:
        JSONResponse with setup status and next steps
    """
    try:

        handler = StoreEmbeddingNeo4j()
        # Check and create index if needed
        index_status = await handler.create_index_if_not_exists()
        
        # Start population in background if not already running
        if not handler.population_status["is_running"]:
            background_tasks.add_task(handler.start_population)
            message = "Embedding population started in background"
        else:
            message = "Embedding population already in progress"

        return JSONResponse(
            status_code=200,
            content={
                "index_status": index_status,
                "population_status": "started" if not handler.population_status["is_running"] else "in_progress",
                "message": message
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    


@app.post("/semantic-search", response_model=List[ProductSearchResult])
async def semantic_search(search_query: SearchQuery) -> List[ProductSearchResult]:
    """
    Endpoint for semantic search of products.
    
    Args:
        search_query: SearchQuery object containing:
            - query: Search text to find similar products
            - limit: Maximum number of results to return (default: 100)
        
    Returns:
        List of products most semantically similar to the query, including:
            - title: Product title
            - url: Product URL
            - description: Product description
            - similarity_score: Semantic similarity score
    """
    try:
        results = await neo4j_handler.semantic_search(
            query=search_query.query,
            top_k=search_query.limit
        )
        
        formatted_results = [
            ProductSearchResult(
                title=result["title"],
                url=result["url"],
                description=result["description"],
                similarity_score=result["similarity"]
            )
            for result in results
        ]
        
        return formatted_results
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error during semantic search: {str(e)}"
        )

@app.post("/data-loader")
async def data_loader():
    await execute_data_loader()

@app.post("/update-product-context")
async def update_product_context(
    product: ProductUpdateRequest,
    background_tasks: BackgroundTasks
):
    """
    Endpoint para actualizar el contexto de un producto existente.
    La actualización se realiza de forma asíncrona en segundo plano.
    """

    async def process_update():
        try:
            # Generar nuevo contexto
            context = await service.generate_product_context(
                product.title,
                product.description
            )

            # Actualizar ambas bases de datos
            await service.update_elasticsearch_context(product.product_id, context)
            await service.update_neo4j_context(product.url, context)

            logger.info(f"Contexto actualizado exitosamente para producto {product.product_id}")
        except Exception as e:
            logger.error(f"Error procesando actualización para producto {product.product_id}: {e}")
            raise
    
    await process_update()
    # Agregar la tarea a background tasks
    #background_tasks.add_task(process_update)
    
    return {"message": "Actualización de contexto iniciada", "product_id": product.product_id}

@app.post("/update-all-products")
async def update_all_products():
    """
    Endpoint para iniciar la actualización de todos los productos.
    Recupera los productos de Elasticsearch y actualiza su contexto uno por uno.
    """
    try:
        # Obtener todos los productos de Elasticsearch
        response = service.es_client.search(
            index="products",
            body={
                "query": {"match_all": {}},
                "_source": ["id", "url", "title", "description"]
            },
            size=1000
        )

        products = response["hits"]["hits"]
        updated_count = 0

        for product in products:
            source = product["_source"]
            update_data = ProductUpdateRequest(
                product_id=product["_id"],
                url=source["url"],
                title=source["title"],
                description=source["description"]
            )
            
            await update_product_context(update_data, BackgroundTasks())
            updated_count += 1

        return {
            "message": f"Actualización iniciada para {updated_count} productos",
            "total_products": len(products)
        }

    except Exception as e:
        logger.error(f"Error iniciando actualización masiva: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

