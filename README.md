# Fastapi for Vertex AI Search Datastore Retriever

## Prerequisite

- Python 3.10 (check with command "python3.10 --version")
- Google Cloud Project ID with IAM permission to enable services (Agent Builder, Cloud Run, set IAM, create Service Account)
- Install runme extension to run this README.md interactively

## Development

Set up gcloud and environment variables

Google Vertex AI Search Retriver parameters reference
https://python.langchain.com/v0.2/docs/integrations/retrievers/google_vertex_ai_search/

```bash {"id":"01J1HV70WT9K1Z78EA6G69FNRJ","promptEnv":"yes"}
export PROJECT_ID=[Enter your project id]
echo "PROJECT_ID set to $PROJECT_ID"
```

```bash {"id":"01J1HSVRW3G8FT67BFC214T9E1","promptEnv":"no"}
VERTEXAI_PROJECT_ID=$PROJECT_ID
LOCATION="us-central1"
SEARCH_ENGINE_ID="recommend_products"
DATA_STORE_LOCATION="global"
MAX_DOCUMENTS="5"
ENGINE_DATA_TYPE="1"

BQ_DATASET="csm_dataset"
BQ_TABLE="recommendation_products"
BQ_BUCKET="${PROJECT_ID}-${BQ_DATASET}"

DATA_STORE_ID_PREFIX="recommend_products"
DATA_STORE_ID="${DATA_STORE_ID_PREFIX}_${PROJECT_ID}"
DATA_STORE_DISPLAY_NAME="Recommendation Products"
SEARCH_APP_ID="recommend_products"
SEARCH_APP_DISPLAY_NAME="Recommend Products App"

CLOUDRUN_SA="cloudrun-products-search"
CLOUDRUN_SA_EMAIL="$CLOUDRUN_SA@$PROJECT_ID.iam.gserviceaccount.com"
CLOUDRUN_INSTANCE_NAME="fast-api-search-products"

cat <<EOF > .env
# Environment variables
VERTEXAI_PROJECT_ID="$VERTEXAI_PROJECT_ID"
PROJECT_ID="$VERTEXAI_PROJECT_ID"
LOCATION="$LOCATION"
SEARCH_ENGINE_ID="${SEARCH_ENGINE_ID}"
DATA_STORE_LOCATION="$DATA_STORE_LOCATION"
DATA_STORE_ID="$DATA_STORE_ID"
MAX_DOCUMENTS=$MAX_DOCUMENTS
ENGINE_DATA_TYPE=$ENGINE_DATA_TYPE
BQ_DATASET="$BQ_DATASET"
BQ_TABLE="$BQ_TABLE"
BQ_BUCKET="${PROJECT_ID}-${BQ_DATASET}"
DATA_STORE_ID_PREFIX="$DATA_STORE_ID_PREFIX"
DATA_STORE_DISPLAY_NAME="$DATA_STORE_DISPLAY_NAME"
SEARCH_APP_ID="$SEARCH_APP_ID"
SEARCH_APP_DISPLAY_NAME="$SEARCH_APP_DISPLAY_NAME"
CLOUDRUN_SA="$CLOUDRUN_SA"
CLOUDRUN_SA_EMAIL="$CLOUDRUN_SA@$PROJECT_ID.iam.gserviceaccount.com"
CLOUDRUN_INSTANCE_NAME="$CLOUDRUN_INSTANCE_NAME"
EOF

set -o allexport
source .env
set +o allexport
```

Authenticate to Google Cloud for login and application default login credential

```bash {"id":"01J1HSJRA7J0D6P6QC64J0VEZW"}
gcloud auth login
gcloud config set project $VERTEXAI_PROJECT_ID
gcloud auth application-default login
```

Creat Service Account for Cloud Run

```bash {"id":"01J1MJB8D3HJWJBRM6JA1VRDRK"}
# Create the service account for Cloud Run
gcloud iam service-accounts create $CLOUDRUN_SA \
    --display-name "Cloud Run Service Account for Vertex AI Search" \
    --project $PROJECT_ID

# Add IAM permission
gcloud projects add-iam-policy-binding --no-user-output-enabled $PROJECT_ID \
    --member serviceAccount:$CLOUDRUN_SA_EMAIL \
    --role roles/storage.objectViewer
gcloud projects add-iam-policy-binding --no-user-output-enabled $PROJECT_ID \
    --member serviceAccount:$CLOUDRUN_SA_EMAIL \
    --role roles/secretmanager.secretAccessor
gcloud projects add-iam-policy-binding --no-user-output-enabled $PROJECT_ID \
    --member serviceAccount:$CLOUDRUN_SA_EMAIL \
    --role roles/discoveryengine.viewer
```

Enable required services

```bash {"id":"01J1MJTMK6SB3FT0FNVVDFF67W"}
gcloud services enable aiplatform.googleapis.com --project $PROJECT_ID
gcloud services enable run.googleapis.com --project $PROJECT_ID
gcloud services enable cloudresourcemanager.googleapis.com --project $PROJECT_ID
gcloud services enable discoveryengine.googleapis.com --project $PROJECT_ID
gcloud services enable bigquery.googleapis.com --project $PROJECT_ID
gcloud services enable storage.googleapis.com --project $PROJECT_ID
```

## Create Bigquery Table, Vertex AI Search Strutured Datastore, and Vertex AI Search App

Create a Cloud Storage Bucket and upload a jsonl products data file

```bash {"id":"01J1HT2ZVPRN11K1FFS5W2FRJW"}
gsutil ls gs://$BQ_BUCKET || PATH_EXIST=$?
echo $PATH_EXIST
if [[ ${PATH_EXIST} -eq 0 ]]; then
    echo "Bucket Exist"
else
    echo "Bucket Not Exist"
    gsutil mb -l $LOCATION gs://$BQ_BUCKET
fi

gsutil -q stat gs://$BQ_BUCKET/recommendation_products.jsonl || PATH_EXIST=$?
if [[ ${PATH_EXIST} -eq 0 ]]; then
    echo "File Exist"
else
    echo "File Not Exist"
    gsutil cp recommendation_products.jsonl gs://$BQ_BUCKET/recommendation_products.jsonl
fi
```

Create a Dataset on BigQuery

```bash {"id":"01J1HTCY1E931GV8Q9P4SC2Z81"}
bq show $PROJECT_ID:$BQ_DATASET || DATASET_EXIST=$?

if [[ ${DATASET_EXIST} -eq 0 ]]; then
    echo "Dataset Exist"
else
    echo "Dataset Not Exist"
    bq --location=US mk --dataset $PROJECT_ID:$BQ_DATASET
fi
```

Create a Table on BigQuery

```bash {"id":"01J1HWAYEY4TKTQCEMJ1MGYY46"}
bq show $PROJECT_ID:$BQ_DATASET.$BQ_TABLE || TABLE_EXIST=$?

if [[ ${TABLE_EXIST} -eq 0 ]]; then
    echo "Table Exist"
else
    echo "Table Not Exist"
    bq --location=US load --source_format=NEWLINE_DELIMITED_JSON --autodetect $PROJECT_ID:$BQ_DATASET.$BQ_TABLE gs://$BQ_BUCKET/recommendation_products.jsonl
fi
```

## Vertex AI Search

create a serach data store from bigquery
https://cloud.google.com/generative-ai-app-builder/docs/create-data-store-es#bigquery

Send REST API Request to create a datastore

```bash {"id":"01J1HSJRA7J0D6P6QC6AJF7J18"}
curl -X POST \
-H "Authorization: Bearer $(gcloud auth print-access-token)" \
-H "Content-Type: application/json" \
-H "X-Goog-User-Project: $PROJECT_ID" \
"https://discoveryengine.googleapis.com/v1alpha/projects/$PROJECT_ID/locations/global/collections/default_collection/dataStores?dataStoreId=${DATA_STORE_ID_PREFIX}_${PROJECT_ID}" \
-d '{
  "displayName": "'"$DATA_STORE_DISPLAY_NAME"'",
  "industryVertical": "GENERIC",
  "solutionTypes": ["SOLUTION_TYPE_SEARCH"]
}'
```

Import data from BigQuery

```bash {"id":"01J1HSJRA7J0D6P6QC6BDYW084"}
curl -X POST \
-H "Authorization: Bearer $(gcloud auth print-access-token)" \
-H "Content-Type: application/json" \
"https://discoveryengine.googleapis.com/v1/projects/$PROJECT_ID/locations/global/collections/default_collection/dataStores/${DATA_STORE_ID_PREFIX}_${PROJECT_ID}/branches/0/documents:import" \
-d '{
  "bigquerySource": {
    "projectId": "'"$PROJECT_ID"'",
    "datasetId":"'"$BQ_DATASET"'",
    "tableId": "'"$BQ_TABLE"'",
    "dataSchema": "custom"
  },
  "reconciliationMode": "INCREMENTAL",
  "autoGenerateIds": "true"
}'
```

Create a Search App with created datastore
https://cloud.google.com/generative-ai-app-builder/docs/create-engine-es

```bash {"excludeFromRunAll":"false","id":"01J1HSJRA7J0D6P6QC6CHHQQN4"}
curl -X POST \
-H "Authorization: Bearer $(gcloud auth print-access-token)" \
-H "Content-Type: application/json" \
-H "X-Goog-User-Project: $PROJECT_ID" \
"https://discoveryengine.googleapis.com/v1/projects/$PROJECT_ID/locations/global/collections/default_collection/engines?engineId=$SEARCH_APP_ID" \
-d '{
  "displayName": "'"$SEARCH_APP_DISPLAY_NAME"'",
  "dataStoreIds": ["'"${DATA_STORE_ID_PREFIX}_${PROJECT_ID}"'"],
  "solutionType": "SOLUTION_TYPE_SEARCH",
  "searchEngineConfig": {
     "searchTier": "SEARCH_TIER_ENTERPRISE"
   }
}'
```

Test get search result

```bash {"excludeFromRunAll":"false","id":"01J1HSJRA7J0D6P6QC6G7B289R"}
QUERY="for sleeping"

curl -X POST -H "Authorization: Bearer $(gcloud auth print-access-token)" \
-H "Content-Type: application/json" \
"https://discoveryengine.googleapis.com/v1/projects/$PROJECT_ID/locations/global/collections/default_collection/engines/$SEARCH_APP_ID/servingConfigs/default_search:search" \
-d '{
"query": "'"${QUERY}"'"
}'
```

```bash {"id":"01J1HSJRA7J0D6P6QC6JCVA13V"}
QUERY="for sleeping"
MAX_PRICE="200"

curl -X POST -H "Authorization: Bearer $(gcloud auth print-access-token)" \
-H "Content-Type: application/json" \
"https://discoveryengine.googleapis.com/v1/projects/$PROJECT_ID/locations/global/collections/default_collection/engines/$SEARCH_APP_ID/servingConfigs/default_search:search" \
-d '{
"query": "'"${QUERY}"'",
"filter": "priceInfo.price<'"$MAX_PRICE"'",
}'
```

Example response

```json {"excludeFromRunAll":"true","id":"01J1HSJRA7J0D6P6QC6MAKZ9ND"}
{
  "results": [
    {
      "id": "cbad0261ebcc0cd5e4317ac9abb4560e",
      "document": {
        "name": "projects/389071638346/locations/global/collections/default_collection/dataStores/recommend_products_nuttee-lab-00/branches/0/documents/cbad0261ebcc0cd5e4317ac9abb4560e",
        "id": "cbad0261ebcc0cd5e4317ac9abb4560e",
        "structData": {
          "images": [
            {
              "width": "1024",
              "uri": "https://storage.googleapis.com/csm-dataset/products_images_dataset/dataset/Bath Robe/3/img3.png",
              "height": "1024"
            }
          ],
          "availableTime": "2023-08-26 23:00:17 UTC",
          "title": "White Cotton Robe for Men - Soft and Absorbent Bathrobe with Shawl Collar",
          "id": "18",
          "availableQuantity": "15",
          "categories": "Bath Robe",
          "priceInfo": {
            "price": 24.34,
            "originalPrice": 24.34,
            "currencyCode": "USD",
            "cost": 4.87
          },
          "language_code": "en"
        }
      }
    },
    {
      "id": "6da58ee88f2a0167e780c847f85d6c67",
      "document": {
        "name": "projects/389071638346/locations/global/collections/default_collection/dataStores/recommend_products_nuttee-lab-00/branches/0/documents/6da58ee88f2a0167e780c847f85d6c67",
        "id": "6da58ee88f2a0167e780c847f85d6c67",
        "structData": {
          "title": "Modern Hotel Room Furniture with Large Bed and Lamp",
          "categories": "Bed",
          "id": "143",
          "language_code": "en",
          "images": [
            {
              "uri": "https://storage.googleapis.com/csm-dataset/products_images_dataset/dataset/Bed/9/img8.png",
              "height": "1024",
              "width": "1024"
            }
          ],
          "availableQuantity": "45",
          "priceInfo": {
            "cost": 36.08,
            "price": 180.39,
            "currencyCode": "USD",
            "originalPrice": 180.39
          },
          "availableTime": "2023-08-26 23:00:17 UTC"
        }
      }
    },
    {
      "id": "cf357daf81cfee30ec10b0b5c9c88bb9",
      "document": {
        "name": "projects/389071638346/locations/global/collections/default_collection/dataStores/recommend_products_nuttee-lab-00/branches/0/documents/cf357daf81cfee30ec10b0b5c9c88bb9",
        "id": "cf357daf81cfee30ec10b0b5c9c88bb9",
        "structData": {
          "title": "Single Bed with Nightstand - Perfect for Small Spaces",
          "id": "120",
          "availableQuantity": "52",
          "language_code": "en",
          "categories": "Bed",
          "availableTime": "2023-08-26 23:00:17 UTC",
          "priceInfo": {
            "currencyCode": "USD",
            "price": 159.51,
            "originalPrice": 159.51,
            "cost": 31.9
          },
          "images": [
            {
              "uri": "https://storage.googleapis.com/csm-dataset/products_images_dataset/dataset/Bed/7/img1.png",
              "width": "1024",
              "height": "1024"
            }
          ]
        }
      }
    },
    {
      "id": "6eb1f8790870f65a10165a8adf0ae638",
      "document": {
        "name": "projects/389071638346/locations/global/collections/default_collection/dataStores/recommend_products_nuttee-lab-00/branches/0/documents/6eb1f8790870f65a10165a8adf0ae638",
        "id": "6eb1f8790870f65a10165a8adf0ae638",
        "structData": {
          "language_code": "en",
          "priceInfo": {
            "originalPrice": 127.49,
            "price": 127.49,
            "currencyCode": "USD",
            "cost": 25.5
          },
          "title": "Black and White Bed Set",
          "id": "75",
          "availableQuantity": "90",
          "availableTime": "2023-08-26 23:00:17 UTC",
          "categories": "Bed",
          "images": [
            {
              "height": "1024",
              "width": "1024",
              "uri": "https://storage.googleapis.com/csm-dataset/products_images_dataset/dataset/Bed/10/img4.png"
            }
          ]
        }
      }
    },
    {
      "id": "bb8f1ed6aa97448d85103d986be7709c",
      "document": {
        "name": "projects/389071638346/locations/global/collections/default_collection/dataStores/recommend_products_nuttee-lab-00/branches/0/documents/bb8f1ed6aa97448d85103d986be7709c",
        "id": "bb8f1ed6aa97448d85103d986be7709c",
        "structData": {
          "priceInfo": {
            "originalPrice": 42.48,
            "price": 42.48,
            "currencyCode": "USD",
            "cost": 8.5
          },
          "availableTime": "2023-08-26 23:00:17 UTC",
          "title": "Women's Black Plush Robe - Soft and Comfortable Bathrobe for a Relaxing Spa Experience",
          "language_code": "en",
          "categories": "Bath Robe",
          "id": "32",
          "availableQuantity": "94",
          "images": [
            {
              "height": "1024",
              "width": "1024",
              "uri": "https://storage.googleapis.com/csm-dataset/products_images_dataset/dataset/Bath Robe/5/img1.png"
            }
          ]
        }
      }
    },
    {
      "id": "1a873b37ba30a8bac409187bb146ad9d",
      "document": {
        "name": "projects/389071638346/locations/global/collections/default_collection/dataStores/recommend_products_nuttee-lab-00/branches/0/documents/1a873b37ba30a8bac409187bb146ad9d",
        "id": "1a873b37ba30a8bac409187bb146ad9d",
        "structData": {
          "availableTime": "2023-08-26 23:00:17 UTC",
          "categories": "Bath Robe",
          "id": "33",
          "availableQuantity": "24",
          "title": "Black plush robe, soft and comfortable, perfect for a relaxing day at home",
          "images": [
            {
              "width": "1024",
              "height": "1024",
              "uri": "https://storage.googleapis.com/csm-dataset/products_images_dataset/dataset/Bath Robe/5/img2.png"
            }
          ],
          "priceInfo": {
            "cost": 5.62,
            "originalPrice": 28.1,
            "currencyCode": "USD",
            "price": 28.1
          },
          "language_code": "en"
        }
      }
    },
    {
      "id": "e7644e104ba820cb468b71e62904d31e",
      "document": {
        "name": "projects/389071638346/locations/global/collections/default_collection/dataStores/recommend_products_nuttee-lab-00/branches/0/documents/e7644e104ba820cb468b71e62904d31e",
        "id": "e7644e104ba820cb468b71e62904d31e",
        "structData": {
          "priceInfo": {
            "cost": 22.14,
            "currencyCode": "USD",
            "originalPrice": 110.71,
            "price": 110.71
          },
          "categories": "Bed",
          "availableQuantity": "74",
          "availableTime": "2023-08-26 23:00:17 UTC",
          "title": "Modern Minimalist Bedroom Furniture Set with King Size Bed and Ceiling Fan",
          "language_code": "en",
          "id": "73",
          "images": [
            {
              "width": "1024",
              "uri": "https://storage.googleapis.com/csm-dataset/products_images_dataset/dataset/Bed/10/img2.png",
              "height": "1024"
            }
          ]
        }
      }
    },
    {
      "id": "31faa67d87d8c03ec43dd3c95eb65993",
      "document": {
        "name": "projects/389071638346/locations/global/collections/default_collection/dataStores/recommend_products_nuttee-lab-00/branches/0/documents/31faa67d87d8c03ec43dd3c95eb65993",
        "id": "31faa67d87d8c03ec43dd3c95eb65993",
        "structData": {
          "priceInfo": {
            "cost": 16.06,
            "originalPrice": 80.32,
            "price": 80.32,
            "currencyCode": "USD"
          },
          "id": "35",
          "language_code": "en",
          "images": [
            {
              "height": "1024",
              "width": "1024",
              "uri": "https://storage.googleapis.com/csm-dataset/products_images_dataset/dataset/Bath Robe/5/img4.png"
            }
          ],
          "availableQuantity": "60",
          "categories": "Bath Robe",
          "title": "Women's Black Plush Robe - Soft and Comfortable Bathrobe with Hood and Pockets",
          "availableTime": "2023-08-26 23:00:17 UTC"
        }
      }
    },
    {
      "id": "bc8929fdcab292e082c25f4b571cb3aa",
      "document": {
        "name": "projects/389071638346/locations/global/collections/default_collection/dataStores/recommend_products_nuttee-lab-00/branches/0/documents/bc8929fdcab292e082c25f4b571cb3aa",
        "id": "bc8929fdcab292e082c25f4b571cb3aa",
        "structData": {
          "availableQuantity": "72",
          "language_code": "en",
          "title": "Women's Zebra Print Plush Robe - Soft and Comfy Bathrobe",
          "priceInfo": {
            "cost": 11.56,
            "originalPrice": 57.79,
            "currencyCode": "USD",
            "price": 57.79
          },
          "id": "28",
          "categories": "Bath Robe",
          "availableTime": "2023-08-26 23:00:17 UTC",
          "images": [
            {
              "height": "1024",
              "width": "1024",
              "uri": "https://storage.googleapis.com/csm-dataset/products_images_dataset/dataset/Bath Robe/4/img5.png"
            }
          ]
        }
      }
    }
  ],
  "totalSize": 9,
  "attributionToken": "fvB9CgsI49P-swYQstDXUBIkNjY3ZDg5ZmEtMDAwMC0yODRkLWFlYmYtMjQwNTg4NzdmYjY4IgdHRU5FUklDKkCAspoijr6dFd6PmiLFy_MXt7eMLaOAlyKuxIot24-aIsLwnhXe7Ygt5-2ILYOymiLb7Ygt1LKdFeTtiC2rxIot",
  "summary": {}
}
```

## Testing

Then run app locally, listen on port 8080

You will need to wait until FastAPI completely started and ready to servce requests.

Example
```bash
INFO:     Uvicorn running on http://0.0.0.0:8080 (Press CTRL+C to quit)
INFO:     Started reloader process [80230] using WatchFiles
INFO:     Started server process [80403]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

```bash {"background":"true","id":"01J1HSJRA7J0D6P6QC6PP6TYE7","interactive":"true"}
python3.10 -m venv venv
source venv/bin/activate
#pip install pip-tools
#pip-compile requirements.in
pip install --quiet -r requirements.txt

python main.py
```

Run testing REST API Call for query = bigbed

You can also open FastAPI docs on http://127.0.0.1:8080/docs/

```bash {"id":"01J1HWQE3FY4D34GSGYE4NKFAW"}
curl -X GET "http://127.0.0.1:8080/search?query=bigbed"
```

## Deploy to Cloud Run

Deploy to Cloud Run by using current directory as source to build.
Then the built container will deploy to Cloud Run with Required Environment Variables, and attached Service Account created at the beginning.

```bash {"id":"01J1HSJRA7J0D6P6QC6QYZ0VG3"}
gcloud run deploy $CLOUDRUN_INSTANCE_NAME \
  --source . \
  --project $PROJECT_ID \
  --region $LOCATION \
  --allow-unauthenticated \
  --service-account $CLOUDRUN_SA_EMAIL \
  --set-env-vars="PROJECT_ID=${PROJECT_ID},LOCATION=${LOCATION},SEARCH_ENGINE_ID=${SEARCH_ENGINE_ID},DATA_STORE_LOCATION=${DATA_STORE_LOCATION},DATA_STORE_ID=${DATA_STORE_ID},MAX_DOCUMENTS=${MAX_DOCUMENTS},ENGINE_DATA_TYPE=${ENGINE_DATA_TYPE}"
```

Get Cloud Run Service URL

```bash {"id":"01J1HX9DG25ABJ6ENZ76Y2V7J7","name":"CLOUDRUN_URL"}
gcloud run services describe $CLOUDRUN_INSTANCE_NAME --platform managed --region $LOCATION --format 'value(status.url)' | tr -d '\n'

```

You can also open FastAPI Docs webui for testing and see api specs

```bash {"id":"01J1HXAZZMBE7KKQQPH48NRQ1S"}
CLOUDRUN_DOCS_URL="${CLOUDRUN_URL}/docs"
echo $CLOUDRUN_DOCS_URL
```

Test search requests with query and filter parameters

```bash {"id":"01J1HY8NX1PBHQKNDJN1MY160V"}
curl -X 'GET' \
  "${CLOUDRUN_URL}"'/search_with_filters?query=big%20bed&filters=categories%3A%20ANY%28%22Bed%22%29%20AND%20priceInfo.price%3C1000' \
  -H 'accept: application/json'
```

## FastAPI Testing

1. run locally and test with curl

```sh {"id":"01J1HSJRA7J0D6P6QC6T6RGVCF"}
curl -X GET http://127.0.0.1:8080/search?query=bigbed
```

Example response:

```json {"id":"01J1HSJRA7J0D6P6QC6Y3XV4ZM"}
[
  {
    "id":119,
    "categories":"Bed",
    "availableTime":"2023-08-26 23:00:17 UTC",
    "image_uri":"https://storage.googleapis.com/csm-dataset/products_images_dataset/dataset/Bed/6/img8.png",
    "language_code":"en",
    "price":239.6,
    "currency_code":"USD",
    "title":"Bed in a bedroom with a picture on the wall",
    "availableQuantity":57
  },
  {
    "id":116,
    "categories":"Bed",
    "availableTime":"2023-08-26 23:00:17 UTC",
    "image_uri":"https://storage.googleapis.com/csm-dataset/products_images_dataset/dataset/Bed/6/img5.png",
    "language_code":"en",
    "price":397.21,
    "currency_code":"USD",
    "title":"Bedart Deer Bed",
    "availableQuantity":27
  }
]
```

2. FastAPI Docs, open https:///docs/ or local test http://127.0.0.1:8080/docs/

## Example Open API Spec to use with Agent Builder

You need to edit:

- server url to match your API Endpoint deployed in Cloud Run/Cloud Function/GKE/etc.
- paths, parameters/responses schema based on your Datastore Type (Unstructure/Structure/BigQuery Table)

```json {"id":"01J1HSJRA7J0D6P6QC6ZW6K9N4"}
{
  "openapi": "3.1.0",
  "info": {
        "title": "An API for /search with query string to get a list of products list related to the query",
        "version": "0.1.0"
    },
  "servers": [
        {
            "url": "https://fast-api-search-products-hz63qipzyq-uc.a.run.app"
        }
    ],
  "paths": {
    "/search": {
      "get": {
        "summary": "Data Store Search",
        "operationId": "data_store_search_search_get",
        "parameters": [
          {
            "required": true,
            "schema": {
              "type": "string",
              "title": "Query"
            },
            "name": "query",
            "in": "query"
          }
        ],
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "items": {
                    "$ref": "#/components/schemas/Item"
                  },
                  "type": "array",
                  "title": "Response Data Store Search Search Get"
                }
              }
            }
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        }
      }
    }
  },
  "components": {
    "schemas": {
      "HTTPValidationError": {
        "properties": {
          "detail": {
            "items": {
              "$ref": "#/components/schemas/ValidationError"
            },
            "type": "array",
            "title": "Detail"
          }
        },
        "type": "object",
        "title": "HTTPValidationError"
      },
      "Product": {
        "properties": {
          "id": {
            "type": "integer",
            "title": "Id"
          },
          "categories": {
            "type": "string",
            "title": "Categories"
          },
          "availableTime": {
            "type": "string",
            "title": "Availabletime"
          },
          "image_uri": {
            "type": "string",
            "title": "Image Uri"
          },
          "language_code": {
            "type": "string",
            "title": "Language Code"
          },
          "price": {
            "type": "number",
            "title": "Price"
          },
          "currency_code": {
            "type": "string",
            "title": "Currency Code"
          },
          "title": {
            "type": "string",
            "title": "Title"
          },
          "availableQuantity": {
            "type": "integer",
            "title": "Availablequantity"
          }
        },
        "type": "object",
        "required": [
          "id",
          "categories",
          "availableTime",
          "image_uri",
          "language_code",
          "price",
          "currency_code",
          "title",
          "availableQuantity"
        ],
        "title": "Product"
      },
      "ValidationError": {
        "properties": {
          "loc": {
            "items": {
              "anyOf": [
                {
                  "type": "string"
                },
                {
                  "type": "integer"
                }
              ]
            },
            "type": "array",
            "title": "Location"
          },
          "msg": {
            "type": "string",
            "title": "Message"
          },
          "type": {
            "type": "string",
            "title": "Error Type"
          }
        },
        "type": "object",
        "required": [
          "loc",
          "msg",
          "type"
        ],
        "title": "ValidationError"
      }
    }
  }
}
```