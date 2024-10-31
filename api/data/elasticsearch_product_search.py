from elasticsearch import Elasticsearch, helpers
import csv

# Configuración de Elasticsearch
es_config = {
    'hosts': ['http://localhost:9200']  # Especificamos el esquema directamente en la URL
}

client = Elasticsearch(**es_config)

# Prueba de conexión
try:
    info = client.info()
    print("Conexión exitosa:", info)
except Exception as e:
    print("Error de conexión:", str(e))

# Definir el mapeo del índice
index_name = 'products'
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
                        },
                        'autocomplete': {
                            'tokenizer': 'autocomplete',
                            'filter': ['lowercase']
                        },
                        'autocomplete_search': {
                            'tokenizer': 'lowercase'
                        }
                    },
                    'tokenizer': {
                        'autocomplete': {
                            'type': 'edge_ngram',
                            'min_gram': 1,
                            'max_gram': 20,
                            'token_chars': [
                                'letter',
                                'digit'
                            ]
                        }
                    }
                }
            },
            'mappings': {
                'properties': {
                    'title': {'type': 'text', 'analyzer': 'product_analyzer'},
                    'description': {'type': 'text', 'analyzer': 'product_analyzer'},
                    'price': {'type': 'float'},
                    'price_without_discount': {'type': 'float'},
                    'similar_purchases': {'type': 'text', 'analyzer': 'product_analyzer'},
                    'most_bought': {'type': 'text', 'analyzer': 'product_analyzer'},
                    'recommendations': {'type': 'text', 'analyzer': 'product_analyzer'},
                    'similar_products': {'type': 'text', 'analyzer': 'product_analyzer'},
                    'other_members_also_purchased': {'type': 'text', 'analyzer': 'product_analyzer'},
                    'resumen_producto': {
                        'type': 'text',
                        'analyzer': 'autocomplete',
                        'search_analyzer': 'autocomplete_search'
                    }
                }
            }
        }
# Crear el índice (si no existe)
if not client.indices.exists(index=index_name):
    client.indices.create(index=index_name, body=index_body)
    print(f"Índice '{index_name}' creado con éxito.")
else:
    print(f"El índice '{index_name}' ya existe.")

# Función para leer el CSV y generar documentos
def generate_documents(csv_file):
    with open(csv_file, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            doc = {
                'title': row['title'],
                'description': row['description'],
                'price': float(row['price']) if row['price'] != '' and row['price'].strip() else 0,
                'price_without_discount': float(row['price_without_discount']) if row['price_without_discount'] != '' and row['price_without_discount'].strip() else 0,
                'similar_purchases': row['similar_purchases'].strip('[]').split(','),
                'most_bought': row['most_bought'].strip('[]').split(','),
                'recommendations': row['recommendations'].strip('[]').split(','),
                'similar_products': row['similar_products'].strip('[]').split(','),
                'other_members_also_purchased': row['other_members_also_purchased'].strip('[]').split(','),
                'resumen_producto': row['resumen_producto'],
            }
            yield {
                "_index": index_name,
                "_source": doc
            }

# Cargar los documentos en Elasticsearch
csv_file = 'helpers/products_new.csv'

try:
    success, failed = helpers.bulk(client, generate_documents(csv_file))
    print(f"Documentos insertados con éxito: {success}")
    print(f"Documentos fallidos: {failed}")
except Exception as e:
    print(f"Error durante la inserción de documentos: {str(e)}")