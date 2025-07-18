from datetime import datetime
from typing import List, Optional, Dict, Any
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, status
from pydantic import BaseModel, Field, HttpUrl
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
import aiofiles
import csv
import json
import io

from ..services.content_processor import ContentProcessor
from ..services.url_extractor import URLExtractor
from ..services.batch_processor import BatchProcessor
from ..services.websocket_manager import manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/content_input", tags=["content_input"])

# Models
class DirectContentInput(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content_type: str
    original_content: str = Field(..., min_length=1)
    target_audience: Optional[str] = None
    keywords: Optional[List[str]] = []
    metadata: Optional[Dict[str, Any]] = {}

class URLSubmission(BaseModel):
    urls: List[HttpUrl]
    content_type: str = "article"
    metadata: Optional[Dict[str, Any]] = {}

class URLSubmissionResponse(BaseModel):
    job_id: str
    status: str
    results: Optional[List[Dict[str, Any]]] = None

class BatchUploadResponse(BaseModel):
    job_id: str
    status: str
    items_processed: int = 0
    items_failed: int = 0
    errors: Optional[List[str]] = None

# Dependencies
async def get_db() -> AsyncIOMotorDatabase:
    # This should be injected from the main app
    from main import app
    return app.state.db

async def get_current_user():
    # Mock user for now - in production, validate JWT
    return {"id": "user123", "email": "user@example.com"}

# Initialize services
content_processor = ContentProcessor()
url_extractor = URLExtractor()
batch_processor = BatchProcessor()

@router.post("/direct", response_model=Dict[str, Any])
async def submit_direct_content(
    content_input: DirectContentInput,
    background_tasks: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Submit content directly for processing"""
    try:
        # Process content
        processed_content = await content_processor.process_content(
            content=content_input.original_content,
            content_type=content_input.content_type,
            metadata=content_input.metadata
        )
        
        # Create content document
        content_doc = {
            "user_id": current_user["id"],
            "title": content_input.title,
            "content_type": content_input.content_type,
            "original_content": content_input.original_content,
            "processed_content": processed_content.get("sanitized_content"),
            "target_audience": content_input.target_audience,
            "keywords": content_input.keywords,
            "metadata": {
                **content_input.metadata,
                **processed_content.get("metadata", {}),
                "source": "direct_input",
                "language": processed_content.get("language"),
                "content_stats": processed_content.get("stats")
            },
            "status": "pending_optimization",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Insert into database
        result = await db.content.insert_one(content_doc)
        
        # Queue for optimization (background task)
        background_tasks.add_task(
            queue_for_optimization,
            str(result.inserted_id),
            db
        )
        
        return {
            "id": str(result.inserted_id),
            "status": "accepted",
            "message": "Content submitted successfully for optimization"
        }
        
    except Exception as e:
        logger.error(f"Error submitting direct content: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process content submission"
        )

@router.post("/urls", response_model=URLSubmissionResponse)
async def submit_urls(
    url_submission: URLSubmission,
    background_tasks: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Submit URLs for content extraction and processing"""
    try:
        # Create job document
        job_doc = {
            "user_id": current_user["id"],
            "type": "url_extraction",
            "status": "processing",
            "urls": [str(url) for url in url_submission.urls],
            "content_type": url_submission.content_type,
            "metadata": url_submission.metadata,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        job_result = await db.jobs.insert_one(job_doc)
        job_id = str(job_result.inserted_id)
        
        # Process URLs in background
        background_tasks.add_task(
            process_urls_batch,
            job_id,
            url_submission.urls,
            url_submission.content_type,
            current_user["id"],
            db
        )
        
        return URLSubmissionResponse(
            job_id=job_id,
            status="processing"
        )
        
    except Exception as e:
        logger.error(f"Error submitting URLs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process URL submission"
        )

@router.post("/batch", response_model=BatchUploadResponse)
async def upload_batch(
    file: UploadFile = File(...),
    content_type: str = Form("article"),
    background_tasks: BackgroundTasks = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Upload batch file (CSV, TXT, JSON) for processing"""
    try:
        # Validate file type
        allowed_types = ["text/csv", "text/plain", "application/json"]
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type. Allowed types: {', '.join(allowed_types)}"
            )
        
        # Read file content
        content = await file.read()
        
        # Create job document
        job_doc = {
            "user_id": current_user["id"],
            "type": "batch_upload",
            "status": "processing",
            "filename": file.filename,
            "file_type": file.content_type,
            "content_type": content_type,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        job_result = await db.jobs.insert_one(job_doc)
        job_id = str(job_result.inserted_id)
        
        # Process batch in background
        background_tasks.add_task(
            process_batch_file,
            job_id,
            content,
            file.content_type,
            content_type,
            current_user["id"],
            db
        )
        
        return BatchUploadResponse(
            job_id=job_id,
            status="processing"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing batch upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process batch upload"
        )

@router.get("/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get job processing status"""
    try:
        job = await db.jobs.find_one({
            "_id": ObjectId(job_id),
            "user_id": current_user["id"]
        })
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found"
            )
        
        job["_id"] = str(job["_id"])
        return job
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get job status"
        )

# Background task functions
async def queue_for_optimization(content_id: str, db: AsyncIOMotorDatabase):
    """Queue content for LLM optimization"""
    try:
        # Here you would typically send to a message queue (Redis, RabbitMQ, etc.)
        # For now, we'll just update the status
        await db.content.update_one(
            {"_id": ObjectId(content_id)},
            {
                "$set": {
                    "status": "queued_for_optimization",
                    "queued_at": datetime.utcnow()
                }
            }
        )
    except Exception as e:
        logger.error(f"Error queuing content for optimization: {e}")

async def process_urls_batch(
    job_id: str,
    urls: List[HttpUrl],
    content_type: str,
    user_id: str,
    db: AsyncIOMotorDatabase
):
    """Process multiple URLs in batch"""
    results = []
    total_urls = len(urls)
    
    # Send initial job start notification
    await manager.send_job_update(
        user_id, job_id, "started", 0,
        {"total_urls": total_urls, "processed": 0}
    )
    
    for idx, url in enumerate(urls):
        try:
            # Extract content from URL
            extracted = await url_extractor.extract_from_url(str(url))
            
            if extracted["success"]:
                # Process the extracted content
                processed = await content_processor.process_content(
                    content=extracted["content"],
                    content_type=content_type,
                    metadata={"url": str(url), **extracted.get("metadata", {})}
                )
                
                # Save to database
                content_doc = {
                    "user_id": user_id,
                    "title": extracted.get("title", f"Content from {url}"),
                    "content_type": content_type,
                    "original_content": extracted["content"],
                    "processed_content": processed.get("sanitized_content"),
                    "metadata": {
                        "source": "url_extraction",
                        "url": str(url),
                        **processed.get("metadata", {})
                    },
                    "status": "pending_optimization",
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
                
                result = await db.content.insert_one(content_doc)
                
                results.append({
                    "url": str(url),
                    "success": True,
                    "content_id": str(result.inserted_id)
                })
            else:
                results.append({
                    "url": str(url),
                    "success": False,
                    "error": extracted.get("error", "Failed to extract content")
                })
                
        except Exception as e:
            logger.error(f"Error processing URL {url}: {e}")
            results.append({
                "url": str(url),
                "success": False,
                "error": str(e)
            })
        
        # Send progress update
        progress = (idx + 1) / total_urls
        await manager.send_job_update(
            user_id, job_id, "processing", progress,
            {"total_urls": total_urls, "processed": idx + 1, "current_url": str(url)}
        )
    
    # Update job status
    await db.jobs.update_one(
        {"_id": ObjectId(job_id)},
        {
            "$set": {
                "status": "completed",
                "results": results,
                "completed_at": datetime.utcnow()
            }
        }
    )
    
    # Send completion notification
    successful = sum(1 for r in results if r["success"])
    await manager.send_job_update(
        user_id, job_id, "completed", 1.0,
        {
            "total_urls": total_urls,
            "successful": successful,
            "failed": total_urls - successful,
            "results": results
        }
    )

async def process_batch_file(
    job_id: str,
    content: bytes,
    file_type: str,
    content_type: str,
    user_id: str,
    db: AsyncIOMotorDatabase
):
    """Process batch file upload"""
    items_processed = 0
    items_failed = 0
    errors = []
    
    try:
        items = await batch_processor.parse_file(content, file_type)
        
        for item in items:
            try:
                # Process each item
                processed = await content_processor.process_content(
                    content=item.get("content", ""),
                    content_type=content_type,
                    metadata=item.get("metadata", {})
                )
                
                # Save to database
                content_doc = {
                    "user_id": user_id,
                    "title": item.get("title", "Untitled"),
                    "content_type": content_type,
                    "original_content": item.get("content", ""),
                    "processed_content": processed.get("sanitized_content"),
                    "target_audience": item.get("target_audience"),
                    "keywords": item.get("keywords", []),
                    "metadata": {
                        "source": "batch_upload",
                        **processed.get("metadata", {})
                    },
                    "status": "pending_optimization",
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
                
                await db.content.insert_one(content_doc)
                items_processed += 1
                
            except Exception as e:
                logger.error(f"Error processing batch item: {e}")
                items_failed += 1
                errors.append(str(e))
        
        # Update job status
        await db.jobs.update_one(
            {"_id": ObjectId(job_id)},
            {
                "$set": {
                    "status": "completed",
                    "items_processed": items_processed,
                    "items_failed": items_failed,
                    "errors": errors if errors else None,
                    "completed_at": datetime.utcnow()
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Error processing batch file: {e}")
        await db.jobs.update_one(
            {"_id": ObjectId(job_id)},
            {
                "$set": {
                    "status": "failed",
                    "error": str(e),
                    "completed_at": datetime.utcnow()
                }
            }
        )