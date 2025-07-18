#!/usr/bin/env python3
"""
Test script for content service endpoints
"""
import asyncio
import aiohttp
import json
from datetime import datetime

BASE_URL = "http://localhost:8002"

async def test_health_check():
    """Test health check endpoint"""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/health") as resp:
            data = await resp.json()
            print(f"✓ Health check: {data}")
            return resp.status == 200

async def test_direct_content_submission():
    """Test direct content submission"""
    content = {
        "title": "Test Article",
        "content_type": "article",
        "original_content": "<h1>Test Article</h1><p>This is a test article with <strong>bold text</strong> and <a href='#'>links</a>.</p>",
        "target_audience": "Tech professionals",
        "keywords": ["test", "content", "optimization"],
        "metadata": {
            "test": True,
            "timestamp": datetime.utcnow().isoformat()
        }
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{BASE_URL}/api/content_input/direct",
            json=content,
            headers={"Content-Type": "application/json"}
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                print(f"✓ Direct content submission: Content ID = {data.get('id')}")
                return True
            else:
                error = await resp.text()
                print(f"✗ Direct content submission failed: {resp.status} - {error}")
                return False

async def test_url_submission():
    """Test URL submission"""
    urls_data = {
        "urls": [
            "https://example.com/article1",
            "https://example.com/article2"
        ],
        "content_type": "article",
        "metadata": {
            "test": True
        }
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{BASE_URL}/api/content_input/urls",
            json=urls_data,
            headers={"Content-Type": "application/json"}
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                print(f"✓ URL submission: Job ID = {data.get('job_id')}")
                return data.get('job_id')
            else:
                error = await resp.text()
                print(f"✗ URL submission failed: {resp.status} - {error}")
                return None

async def test_batch_upload():
    """Test batch file upload"""
    # Create a test CSV content
    csv_content = """title,content,keywords,target_audience
"First Article","This is the first article content that needs optimization.","seo,content","marketers"
"Second Article","Another piece of content for testing the batch upload feature.","testing,batch","developers"
"""
    
    # Create form data
    form = aiohttp.FormData()
    form.add_field('file',
                   csv_content.encode('utf-8'),
                   filename='test_batch.csv',
                   content_type='text/csv')
    form.add_field('content_type', 'article')
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{BASE_URL}/api/content_input/batch",
            data=form
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                print(f"✓ Batch upload: Job ID = {data.get('job_id')}")
                return data.get('job_id')
            else:
                error = await resp.text()
                print(f"✗ Batch upload failed: {resp.status} - {error}")
                return None

async def test_job_status(job_id: str):
    """Test job status endpoint"""
    if not job_id:
        print("✗ No job ID to test status")
        return
    
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/api/content_input/jobs/{job_id}") as resp:
            if resp.status == 200:
                data = await resp.json()
                print(f"✓ Job status for {job_id}: {data.get('status')}")
                return True
            else:
                error = await resp.text()
                print(f"✗ Job status check failed: {resp.status} - {error}")
                return False

async def test_websocket_connection():
    """Test WebSocket connection"""
    ws_url = f"ws://localhost:8002/ws/test_user"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(ws_url) as ws:
                print(f"✓ WebSocket connected to {ws_url}")
                
                # Send ping
                await ws.send_json({"type": "ping"})
                
                # Wait for response
                msg = await ws.receive_json(timeout=5)
                print(f"✓ WebSocket received: {msg}")
                
                await ws.close()
                return True
    except Exception as e:
        print(f"✗ WebSocket connection failed: {e}")
        return False

async def main():
    """Run all tests"""
    print("Content Service API Tests")
    print("=" * 50)
    
    # Test health check
    await test_health_check()
    print()
    
    # Test direct content submission
    await test_direct_content_submission()
    print()
    
    # Test URL submission
    url_job_id = await test_url_submission()
    print()
    
    # Test batch upload
    batch_job_id = await test_batch_upload()
    print()
    
    # Test job status
    if url_job_id:
        await asyncio.sleep(1)  # Wait a bit for processing
        await test_job_status(url_job_id)
        print()
    
    if batch_job_id:
        await asyncio.sleep(1)  # Wait a bit for processing
        await test_job_status(batch_job_id)
        print()
    
    # Test WebSocket
    await test_websocket_connection()
    
    print("\n" + "=" * 50)
    print("Tests completed!")

if __name__ == "__main__":
    asyncio.run(main())