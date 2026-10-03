from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from src.db.database import engine
from src.models.models import Base
from routers import service
from src.exception.exception_handler import global_exception_handler
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
logger = logging.getLogger("coinmarket")

Base.metadata.create_all(bind=engine)

app = FastAPI()

# ── Глобальный middleware на ВСЕ эндпоинты: замер времени ──
@app.middleware("http")
async def add_process_time_header(request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    response.headers["X-Process-Time"] = f"{elapsed:.4f}"
    logger.info("%s %s → %s [%.3fs]", request.method, request.url.path, response.status_code, elapsed)
    return response

app.add_exception_handler(Exception, global_exception_handler)
app.include_router(service.router)

@app.get("/")
async def read_index():
    return FileResponse('static/index.html')

app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)