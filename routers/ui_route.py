from fastapi.responses import HTMLResponse
from fastapi import APIRouter

router = APIRouter()

@router.get("/", include_in_schema=False, response_class=HTMLResponse)
def home():
    return "<h1>Hello World!</h>"