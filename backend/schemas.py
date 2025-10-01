from pydantic import BaseModel, Field
from typing import List

class ScrapeRequest(BaseModel):
    urls: List[str] = []
    render: bool = False
    concurrency: int = 5
    timeout_ms: int = 12000

class JobCreate(BaseModel):
    urls: List[str]
    render: bool = False
    concurrency: int = 5
    timeout_ms: int = 12000

class ExportRequest(BaseModel):
    rows: List[dict]

class SearchRequest(BaseModel):
    query: str
    count: int = 10
