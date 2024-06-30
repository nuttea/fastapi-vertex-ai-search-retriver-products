import os
import json
import vertexai

if os.getenv('API_ENV') != 'production':
    from dotenv import load_dotenv
    load_dotenv()

import uvicorn

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional

project_id = os.environ.get('PROJECT_ID', 'nuttee-lab-00')
location = os.environ.get('LOCATION', 'us-central1')
search_engine_id = os.environ.get('SEARCH_ENGINE_ID', 'recommend_products')
data_store_id = os.environ.get('DATA_STORE_ID', 'recommend_products_nuttee-lab-00')
data_store_location = os.environ.get('DATA_STORE_LOCATION', 'global')
max_documents = os.environ.get('MAX_DOCUMENTS', '5')
engine_data_type = os.environ.get('ENGINE_DATA_TYPE', '1')

vertexai.init(project=project_id, location=location)

from langchain_community.retrievers import (
    GoogleVertexAIMultiTurnSearchRetriever,
    GoogleVertexAISearchRetriever,
)
from langchain.schema import Document

# Init Google Vertex AI Search Retriever
# https://python.langchain.com/docs/integrations/retrievers/google_vertex_ai_search/
# Create a retriever
retriever = GoogleVertexAISearchRetriever(
    project_id = project_id,
    location = data_store_location,
    search_engine_id = search_engine_id,
    max_documents = max_documents,
    engine_data_type = engine_data_type,
)

# Test Retriever
#print(retriever.get_relevant_documents("what is google cloud revenue?"))

app = FastAPI()
app.project_id = project_id
app.location = location
app.search_engine_id = search_engine_id
app.data_store_id = data_store_id
app.data_store_location = data_store_location
app.max_documents = max_documents
app.engine_data_type = engine_data_type

templates = Jinja2Templates(directory="templates")

@app.get("/")
async def root():
    return {"message": "Hello World!"}

# {
# \"description\": \"This bed is perfect for any bedroom. It's made of solid wood and has a beautiful finish. The bed comes with a mattress and box spring. The picture on the wall is a beautiful landscape. The bedroom is spacious and has a lot of natural light.\", 
# \"id\": \"119\", 
# \"categories\": \"Bed\", 
# \"availableTime\": \"2023-08-26 23:00:17 UTC\", 
# \"images\": 
#   [{
#       \"height\": \"1024\", 
#       \"uri\": \"https://storage.googleapis.com/csm-dataset/products_images_dataset/dataset/Bed/6/img8.png\", 
#       \"width\": \"1024\"
#   }], 
# \"language_code\": \"en\", 
# \"priceInfo\": {
#   \"originalPrice\": 239.6, 
#   \"cost\": 47.92, 
#   \"currencyCode\": \"USD\", 
#   \"price\": 239.6
#   }, 
# \"title\": \"Bed in a bedrooen\",,
# \"availableQuantity\": \"57\"
# }",
# "metadata":{"id":"190477da2212792a8023d4b977c84770","name":"projects/389071638346/locations/global/collections/default_collection/dataStores/products-ds_1717761505389/branches/0/documents/190477da2212792a8023d4b977c84770"},"type":"Document"}

class Product(BaseModel):
    id: int
    categories: str
    availableTime: str
    image_uri: str
    language_code: str
    price: float
    currency_code: str
    title: str
    availableQuantity: int


@app.get("/search")
async def data_store_search(query: str) -> list[Product]:
    """
    Searches the Google Vertex AI Search engine for products based on the provided query.

    Args:
        query (str): The search query to use.

    Returns:
        list[Product]: A list of products matching the search query.
    """

    items = []
    result = retriever.get_relevant_documents(query)
    
    for doc in result:
        row = json.loads(doc.page_content)
        items.append(
            Product(
                id = row["id"],
                categories = row["categories"],
                availableTime = row["availableTime"],
                image_uri = row["images"][0]["uri"],
                language_code = row["language_code"],
                price = row["priceInfo"]["price"],
                currency_code = row["priceInfo"]["currencyCode"],
                title = row["title"],
                availableQuantity = row["availableQuantity"],
            )
        )

    return items

@app.get("/search_with_filters")
async def data_store_search_with_filters(query: str, filters: str) -> list[Product]:
    """
    Searches the Google Vertex AI Search engine for products based on the provided query and filters.
    https://cloud.google.com/generative-ai-app-builder/docs/filter-search-metadata

    Args:
        query (str): The search query to use.
        filters (str): The filters to apply to the search. 
            Examples: 
            - "categories: ANY("Bed") AND priceInfo.price<1000"
            - "priceInfo.price<500"

    Returns:
        list[Product]: A list of products matching the search query and filters.
    """

    items = []

    retriever_with_filters = GoogleVertexAISearchRetriever(
        project_id=app.project_id,
        location=app.location,
        search_engine_id=app.search_engine_id,
        max_documents=app.max_documents,
        engine_data_type=app.engine_data_type,
        filter=filters,
    )
    result = retriever_with_filters.get_relevant_documents(query)
    
    for doc in result:
        row = json.loads(doc.page_content)
        items.append(
            Product(
                id = row["id"],
                categories = row["categories"],
                availableTime = row["availableTime"],
                image_uri = row["images"][0]["uri"],
                language_code = row["language_code"],
                price = row["priceInfo"]["price"],
                currency_code = row["priceInfo"]["currencyCode"],
                title = row["title"],
                availableQuantity = row["availableQuantity"],
            )
        )

    return items

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
