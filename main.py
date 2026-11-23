# main.py

import logging

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, field_validator

from app.database import init_db
from app.operations import add, subtract, multiply, divide
from app.routers import calculations, users

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="FastAPI Calculator",
    description=(
        "Register, log in to get a JWT, then click **Authorize** and paste the token "
        "to use the calculation routes."
    ),
    version="1.0.0",
    openapi_tags=[
        {"name": "Users", "description": "Register and log in."},
        {"name": "Calculations", "description": "Browse, Read, Edit, Add, and Delete your calculations. Requires a token."},
        {"name": "Calculator", "description": "Stateless arithmetic used by the web page."},
        {"name": "Health", "description": "Used by the Docker health check."},
    ],
)

# Create any tables that do not yet exist.
init_db()

app.include_router(users.router)
app.include_router(calculations.router)

logger.info("Calculator API started.")

# Setup templates directory
templates = Jinja2Templates(directory="templates")


# Pydantic model for request data
class OperationRequest(BaseModel):
    a: float = Field(..., description="The first number")
    b: float = Field(..., description="The second number")

    @field_validator('a', 'b')
    def validate_numbers(cls, value):
        if not isinstance(value, (int, float)):
            raise ValueError('Both a and b must be numbers.')
        return value


# Pydantic model for successful response
class OperationResponse(BaseModel):
    result: float = Field(..., description="The result of the operation")


# Pydantic model for error response
class ErrorResponse(BaseModel):
    error: str = Field(..., description="Error message")


# Custom Exception Handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.error(f"HTTPException on {request.url.path}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
        headers=exc.headers,  # keeps WWW-Authenticate on 401 responses
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    error_messages = "; ".join([f"{err['loc'][-1]}: {err['msg']}" for err in exc.errors()])
    logger.error(f"ValidationError on {request.url.path}: {error_messages}")
    return JSONResponse(
        status_code=400,
        content={"error": error_messages},
    )


@app.get("/", include_in_schema=False)
async def read_root(request: Request):
    """
    Serve the index.html template.
    """
    logger.info("Serving calculator homepage.")
    return templates.TemplateResponse(request, "index.html")


@app.get("/health", tags=["Health"])
async def health():
    """
    Report that the app is running.
    """
    return {"status": "ok"}


@app.post("/add", response_model=OperationResponse, responses={400: {"model": ErrorResponse}},
          tags=["Calculator"])
async def add_route(operation: OperationRequest):
    """
    Add two numbers.
    """
    try:
        result = add(operation.a, operation.b)
        logger.info(f"Add: {operation.a} + {operation.b} = {result}")
        return OperationResponse(result=result)
    except Exception as e:
        logger.error(f"Add Operation Error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/subtract", response_model=OperationResponse, responses={400: {"model": ErrorResponse}},
          tags=["Calculator"])
async def subtract_route(operation: OperationRequest):
    """
    Subtract two numbers.
    """
    try:
        result = subtract(operation.a, operation.b)
        logger.info(f"Subtract: {operation.a} - {operation.b} = {result}")
        return OperationResponse(result=result)
    except Exception as e:
        logger.error(f"Subtract Operation Error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/multiply", response_model=OperationResponse, responses={400: {"model": ErrorResponse}},
          tags=["Calculator"])
async def multiply_route(operation: OperationRequest):
    """
    Multiply two numbers.
    """
    try:
        result = multiply(operation.a, operation.b)
        logger.info(f"Multiply: {operation.a} * {operation.b} = {result}")
        return OperationResponse(result=result)
    except Exception as e:
        logger.error(f"Multiply Operation Error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/divide", response_model=OperationResponse, responses={400: {"model": ErrorResponse}},
          tags=["Calculator"])
async def divide_route(operation: OperationRequest):
    """
    Divide two numbers.
    """
    try:
        result = divide(operation.a, operation.b)
        logger.info(f"Divide: {operation.a} / {operation.b} = {result}")
        return OperationResponse(result=result)
    except ValueError as e:
        logger.error(f"Divide Operation Error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Divide Operation Internal Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)