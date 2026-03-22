import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logger import logger
from app.api.routes import auth, chat, feedback

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Enterprise API Backend for the AI Movie Finder",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Should be tightened in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(feedback.router, prefix="/api")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    logger.info(f"Incoming Payload mapped: {request.method} {request.url.path}")
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        logger.info(f"Request Dispatched: {request.method} {request.url.path} - Resolution: {response.status_code} - Latency: {process_time:.4f}s")
        return response
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(f"Critical Runtime Resolution Error: {request.method} {request.url.path} - Origin: {str(e)} - Latency: {process_time:.4f}s")
        raise

@app.get("/health")
async def health_check():
    return {"status": "ok"}
