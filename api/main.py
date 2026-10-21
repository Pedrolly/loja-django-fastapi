from fastapi import FastAPI

from api.routers import auth, orders, products

app = FastAPI(
    title="Loja API",
    version="1.0.0",
    description="API FastAPI da loja, usando models e autenticação do Django.",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.include_router(auth.router, prefix="/api")
app.include_router(products.router, prefix="/api")
app.include_router(orders.router, prefix="/api")


@app.get("/api/health", tags=["infra"])
def health():
    return {"status": "ok"}
