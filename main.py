from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.exceptions import add_exception_handlers
from app.core.router import routers

app = FastAPI(title="PrestigeI Staff API", version="1.0.0")

API_PREFIX = "/api/v1"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4300"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router, path in routers:
    app.include_router(router, prefix=f"{API_PREFIX}{path}")

add_exception_handlers(app)


@app.get("/health")
async def health():
    return {"status": "ok"}
