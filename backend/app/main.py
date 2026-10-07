"""
Student Chatbot Backend API Service (student-api)
HackQubit 2.0 - Problem 18
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.config import settings
from backend.routes.chat import router as chat_router
from backend.routes.health import router as health_router
from backend.routes.logs import router as logs_router
from backend.routes.simulate import router as simulate_router
from backend.routes.tools import router as tools_router
from backend.routes.incidents import router as incidents_router
from database.init_db import main as init_database

app = FastAPI(
    title="Student Chatbot Backend API",
    description="Vectorless Structured RAG Backend with Diagnostic and Failure Simulation Suite for Incident Response",
    version="1.0.0",
)

# Enable CORS for Frontend UI (Dumani's client)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all route blueprints
app.include_router(chat_router)
app.include_router(health_router)
app.include_router(logs_router)
app.include_router(simulate_router)
app.include_router(tools_router)
app.include_router(incidents_router)

@app.on_event("startup")
def on_startup():
    print("[INIT] Starting Student Chatbot Backend API...")
    try:
        init_database()
        print("[INIT] Database initialized successfully.")
    except Exception as e:
        print(f"[INIT WARNING] Database auto-init error: {e}")

@app.get("/")
def root():
    return {
        "service": "student-api",
        "status": "online",
        "version": "1.0.0",
        "documentation": "/docs",
        "endpoints": {
            "chat": "POST /chat",
            "health": "GET /health",
            "metrics": "GET /metrics",
            "students": "GET /students",
            "logs": "GET /logs",
            "simulate": "/simulate/*",
            "tools": "/tools/*",
            "incidents": "/incidents/*"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host=settings.BACKEND_HOST, port=settings.BACKEND_PORT, reload=settings.DEBUG)

