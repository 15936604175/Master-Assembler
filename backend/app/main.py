from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.optimize import router as optimize_router

app = FastAPI(title="装配大师 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(optimize_router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}
