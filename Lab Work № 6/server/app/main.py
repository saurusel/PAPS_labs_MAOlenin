from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.orders import router as orders_router
from app.api.products import router as products_router
from app.db import init_db_and_seed

app = FastAPI(title="Corporate Merch Store API (Lab 6)", version="2.0")


@app.exception_handler(HTTPException)
async def http_exc_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "HTTP_ERROR", "message": str(exc.detail), "details": {}}},
    )


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Ошибка валидации входных данных.",
                "details": exc.errors(),
            }
        },
    )


@app.on_event("startup")
def startup():
    init_db_and_seed()


@app.get("/health")
def health():
    return {"ok": True}


app.include_router(products_router)
app.include_router(orders_router)
