from pydantic import BaseModel

class ProductSearchResult(BaseModel):
    """Pydantic model for product search results"""
    title: str
    url: str
    description: str
    similarity_score: float

class SearchQuery(BaseModel):
    """Pydantic model for search query"""
    query: str
    limit: int = 100 

class ProductUpdateRequest(BaseModel):
    product_id: str
    url: str
    title: str
    description: str