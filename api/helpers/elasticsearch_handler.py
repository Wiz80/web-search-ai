from elasticsearch import Elasticsearch
import fuzzywuzzy as fuzz
from typing import List, Dict, Any
import logging

class ElasticsearchHandler:
    def __init__(self, hosts):
        self.client = Elasticsearch(hosts)
        self.index_name = 'products'

    def create_index_products(self):
        index_body = {
            'settings': {
                'index': {
                    'number_of_shards': 1,
                    'number_of_replicas': 1
                },
                'analysis': {
                    'analyzer': {
                        'product_analyzer': {
                            'type': 'custom',
                            'tokenizer': 'standard',
                            'filter': ['lowercase', 'asciifolding']
                        }
                    }
                },
                'similarity': {
                    'custom_bm25': {
                        'type': 'BM25',
                        'k1': 1.2,  
                        'b': 0.75 
                    }
                }
            },
            'mappings': {
                'properties': {
                    'title': {
                        'type': 'text',
                        'analyzer': 'product_analyzer',
                        'similarity': 'custom_bm25'
                    },
                    'description': {
                        'type': 'text',
                        'analyzer': 'product_analyzer',
                        'similarity': 'custom_bm25'
                    },
                    'product_context': {
                        'type': 'text',
                        'analyzer': 'product_analyzer',
                        'similarity': 'custom_bm25'
                    },
                    'price': {'type': 'float'},
                    'price_without_discount': {'type': 'float'},
                    'product_resume': {
                        'type': 'text',
                        'analyzer': 'product_analyzer',
                        'similarity': 'custom_bm25'
                    }
                }
            }
        }

        if not self.client.indices.exists(index=self.index_name):
            self.client.indices.create(index=self.index_name, body=index_body)
            logging.info(f"Índex '{self.index_name}' successfully created.")
            return True
        else:
            logging.info(f"The index '{self.index_name}' already exists.")
            return False
    
    async def store_product(self, product_data: Dict[str, Any], index: int) -> bool:
        try:
            response = self.client.index(
                index=self.index_name,
                id=index,
                body=product_data
            )
            
            if response['result'] == 'created':
                logging.info(f"Product {index}:{product_data['title']} stored in Elasticsearch")
                return True
            else:
                logging.error(f"Error while storing product {index}:{product_data['title']} in Elasticsearch")
                return False

        except Exception as e:
            logging.error(f"Error while storing product {index}:{product_data['title']} in Elasticsearch: {e}")
            return False

    async def search_products_bm25(self, query: str, size: int = 10) -> List[Dict[str, Any]]:
        """
        Search for products using BM25 algorithm.

        Args:
            query (str): The search query.
            size (int, optional): The number of results to return. Defaults to 10.

        Returns:
            List[Dict[str, Any]]: A list of product dictionaries.
        """
        search_body = {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["product_resume^4", "title^2", "description"],
                    "type": "best_fields",
                    "operator": "or",
                    "minimum_should_match": "70%"
                }
            },
            "_source": [
                "title",
                "product_resume",
                "price",
                "description"
            ],
            "size": size
        }
        
        try:
            results = self.client.search(index=self.index_name, body=search_body)
            return [{
                'title': hit['_source']['title'],
                'resumen': hit['_source']['product_resume'],
                'price': hit['_source'].get('price'),
                'description': hit['_source'].get('description'),
                'score': hit['_score']
            } for hit in results['hits']['hits']]
        
        except Exception as e:
            logging.error(f"Error en la búsqueda BM25: {e}")
            return []

    async def search_products_autocomplete(self, query: str, size: int = 10) -> List[Dict[str, Any]]:
        """
        Search for products using autocomplete.

        Args:
            query (str): The search query.
            size (int, optional): The number of results to return. Defaults to 10.

        Returns:    
            List[Dict[str, Any]]: A list of product dictionaries.
        """

        search_body = {
            "query": {
                "match": {
                    "product_resume": {
                        "query": query,
                        "operator": "and"
                    }
                }
            },
            "_source": ["product_resume"],
            "size": size
        }
        
        results = self.client.search(index='products', body=search_body)
        return [hit['_source']['product_resume'] for hit in results['hits']['hits']]
    
    async def deduplicate_results(self, results: List[str], threshold: int = 95) -> List[str]:
        deduplicated = []
        for result in results:
            if not any(fuzz.ratio(result, dedup) >= threshold for dedup in deduplicated):
                deduplicated.append(result)
        return deduplicated

    async def get_recommendations_autocomplete(self, query: str, size: int = 20, threshold: int = 95) -> List[str]:
        results = await self.search_products_autocomplete(query, size)
        return await self.deduplicate_results(results, threshold)
    
    def delete_index(self):
        """
        Delete index in Elasticsearch.

        Returns:
            bool: True if the index was deleted, False otherwise.
        """
        if self.client.indices.exists(index=self.index_name):
            self.client.indices.delete(index=self.index_name)
            logging.info(f"Índice '{self.index_name}' eliminado con éxito.")
            return True
        return False
