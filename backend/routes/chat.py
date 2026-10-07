"""
Chat endpoint: Vectorless Structured RAG (Text-to-SQL + Grounded Synthesis).
"""
import time
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.database.connection import db_manager
from backend.services.sql_guard import sanitize_and_validate_sql
from backend.services.llm_service import llm_service
from backend.services.metrics_service import metrics_service
from backend.app.logger import logger

router = APIRouter(tags=["Chat"])

class ChatRequest(BaseModel):
    query: str = Field(..., description="Natural language user query")

class ChatResponseMetadata(BaseModel):
    generated_sql: str
    row_count: int
    latency_ms: float

class ChatSuccessResponse(BaseModel):
    status: str = "success"
    query: str
    response: str
    data: List[Dict[str, Any]]
    metadata: ChatResponseMetadata

class ChatErrorResponse(BaseModel):
    status: str = "error"
    error_code: str
    message: str
    request_id: str

@router.post(
    "/chat",
    response_model=ChatSuccessResponse,
    responses={
        500: {"model": ChatErrorResponse, "description": "Database or generation error"},
        400: {"description": "Invalid input query"}
    }
)
async def chat(request: ChatRequest):
    req_id = f"req-{uuid.uuid4().hex[:8]}"
    start_time = time.time()
    user_query = request.query.strip()
    generated_sql = ""

    if not user_query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    try:
        # Step 1: Text-to-SQL translation
        raw_sql = await llm_service.generate_sql(user_query)

        # Check for simulated invalid SQL failure
        if db_manager.force_invalid_sql:
            raw_sql = "SELECT * FROM non_existent_students_table WHERE syntax error;"

        # Step 2: Validate SQL safety
        generated_sql = sanitize_and_validate_sql(raw_sql)

        # Step 3: Execute query against PostgreSQL / SQLite
        rows = db_manager.execute_query(generated_sql)

        # Step 4: Grounded Response Synthesis
        answer = await llm_service.synthesize_response(user_query, rows)

        latency_ms = (time.time() - start_time) * 1000
        pool_status = db_manager.get_pool_status()

        # Log successful event
        logger.log_event(
            endpoint="/chat",
            status=200,
            request_id=req_id,
            user_query=user_query,
            generated_sql=generated_sql,
            db_pool_active=pool_status["active_connections"],
            db_pool_max=pool_status["max_pool_size"],
            latency_ms=latency_ms,
        )
        metrics_service.record_request(latency_ms=latency_ms, is_error=False)

        return ChatSuccessResponse(
            status="success",
            query=user_query,
            response=answer,
            data=rows,
            metadata=ChatResponseMetadata(
                generated_sql=generated_sql,
                row_count=len(rows),
                latency_ms=round(latency_ms, 2)
            )
        )

    except TimeoutError as te:
        latency_ms = (time.time() - start_time) * 1000
        pool_status = db_manager.get_pool_status()
        err_msg = str(te)
        logger.log_event(
            endpoint="/chat",
            status=500,
            request_id=req_id,
            user_query=user_query,
            generated_sql=generated_sql or "N/A",
            db_pool_active=pool_status["active_connections"],
            db_pool_max=pool_status["max_pool_size"],
            latency_ms=latency_ms,
            error=f"TimeoutError: {err_msg}",
        )
        metrics_service.record_request(latency_ms=latency_ms, is_error=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "error_code": "DB_CONNECTION_TIMEOUT",
                "message": f"Failed to execute database query: connection pool exhausted ({err_msg})",
                "request_id": req_id
            }
        )

    except ConnectionError as ce:
        latency_ms = (time.time() - start_time) * 1000
        pool_status = db_manager.get_pool_status()
        err_msg = str(ce)
        logger.log_event(
            endpoint="/chat",
            status=500,
            request_id=req_id,
            user_query=user_query,
            generated_sql=generated_sql or "N/A",
            db_pool_active=pool_status["active_connections"],
            db_pool_max=pool_status["max_pool_size"],
            latency_ms=latency_ms,
            error=f"ConnectionError: {err_msg}",
        )
        metrics_service.record_request(latency_ms=latency_ms, is_error=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "error_code": "DB_UNAVAILABLE",
                "message": f"Database host unreachable: {err_msg}",
                "request_id": req_id
            }
        )

    except Exception as exc:
        latency_ms = (time.time() - start_time) * 1000
        pool_status = db_manager.get_pool_status()
        err_msg = str(exc)
        logger.log_event(
            endpoint="/chat",
            status=500,
            request_id=req_id,
            user_query=user_query,
            generated_sql=generated_sql or "N/A",
            db_pool_active=pool_status["active_connections"],
            db_pool_max=pool_status["max_pool_size"],
            latency_ms=latency_ms,
            error=f"{type(exc).__name__}: {err_msg}",
        )
        metrics_service.record_request(latency_ms=latency_ms, is_error=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "error_code": "INTERNAL_SERVER_ERROR",
                "message": f"Query processing failed: {err_msg}",
                "request_id": req_id
            }
        )

