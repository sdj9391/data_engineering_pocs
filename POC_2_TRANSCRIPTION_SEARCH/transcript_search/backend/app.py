import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from google.api_core.client_options import ClientOptions
from google.cloud import discoveryengine_v1 as de


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

PROJECT_ID = os.environ["PROJECT_ID"]
LOCATION = os.getenv("LOCATION", "global")
APP_ID = os.environ["APP_ID"]

app = FastAPI(title="Training Transcript Search")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

endpoint = (
    None
    if LOCATION == "global"
    else f"{LOCATION}-discoveryengine.googleapis.com"
)
client_options = ClientOptions(api_endpoint=endpoint) if endpoint else None
client = de.SearchServiceClient(client_options=client_options)
serving_config = (
    f"projects/{PROJECT_ID}/locations/{LOCATION}/collections/default_collection"
    f"/engines/{APP_ID}/servingConfigs/default_search"
)


@app.get("/search")
def search(
    q: str = Query(..., min_length=2, max_length=300),
    page_size: int = Query(10, ge=1, le=100),
):
    request = de.SearchRequest(
        serving_config=serving_config,
        query=q,
        page_size=page_size,
        query_expansion_spec=de.SearchRequest.QueryExpansionSpec(
            condition=de.SearchRequest.QueryExpansionSpec.Condition.AUTO
        ),
        spell_correction_spec=de.SearchRequest.SpellCorrectionSpec(
            mode=de.SearchRequest.SpellCorrectionSpec.Mode.AUTO
        ),
        content_search_spec=de.SearchRequest.ContentSearchSpec(
            snippet_spec=de.SearchRequest.ContentSearchSpec.SnippetSpec(
                return_snippet=True
            ),
            extractive_content_spec=(
                de.SearchRequest.ContentSearchSpec.ExtractiveContentSpec(
                    max_extractive_answer_count=1
                )
            ),
            summary_spec=de.SearchRequest.ContentSearchSpec.SummarySpec(
                summary_result_count=3,
                include_citations=True,
            ),
        ),
    )
    try:
        response = client.search(request)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Search failed: {exc}") from exc

    results = []
    for result in response.results:
        data = dict(result.document.derived_struct_data)
        snippets = [item.get("snippet", "") for item in data.get("snippets", [])]
        answers = [
            item.get("content", "") for item in data.get("extractive_answers", [])
        ]
        results.append(
            {
                "id": result.document.id,
                "title": data.get("title", result.document.id),
                "link": data.get("link", ""),
                "snippets": snippets,
                "answers": answers,
            }
        )

    summary = response.summary.summary_text if response.summary else ""
    return {"query": q, "summary": summary, "results": results}


@app.get("/")
def index():
    return FileResponse(PROJECT_ROOT / "transcript_search" / "ui" / "index.html")
