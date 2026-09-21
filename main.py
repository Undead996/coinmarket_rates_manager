from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from src.db.database import engine
from src.models.models import Base
from routers import service
from src.exception.exception_handler import global_exception_handler

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI()

# Add global exception handler
app.add_exception_handler(Exception, global_exception_handler)

# Include routers
app.include_router(service.router)

# Serve index.html at root path
@app.get("/")
async def read_index():
    return FileResponse('static/index.html')

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
