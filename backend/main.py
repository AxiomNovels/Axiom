from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes.auth import router as auth_router
from routes.novels import router as novels_router
from routes.search import router as search_router
from routes.reading_lists import router as reading_lists_router
from core.config import FRONTEND_ORIGIN


app = FastAPI(title="Axiom Backend")

# Both addresses refer to the local frontend, but browsers treat them as
# different origins. Supporting both avoids a confusing CORS failure when the
# frontend is opened with the numeric loopback address.
frontend_origins = list(dict.fromkeys([
    FRONTEND_ORIGIN,
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]))

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(novels_router)
app.include_router(search_router)
app.include_router(reading_lists_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
