from fastapi.responses import JSONResponse

async def global_exception_handler(exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "result": 9999,
            "result_text": str(exc)
        }
    )
