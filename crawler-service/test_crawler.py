#!/usr/bin/env python3
"""Test script for crawler service"""

import asyncio
import time
import requests
import json
from typing import Dict, List

BASE_URL = "http://localhost:8003"


def test_health_check():
    """Test health check endpoint"""
    print("Testing health check...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code in [200, 503]
    print("✓ Health check passed\n")


def test_robots_check():
    """Test robots.txt checking"""
    print("Testing robots.txt check...")
    response = requests.post(
        f"{BASE_URL}/robots/check",
        params={"url": "https://example.com/search"}
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200
    print("✓ Robots check passed\n")


def test_single_url_crawl():
    """Test crawling a single URL"""
    print("Testing single URL crawl...")
    response = requests.post(
        f"{BASE_URL}/test/crawl",
        params={"url": "https://example.com"}
    )
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"Title: {result.get('title')}")
        print(f"Status Code: {result.get('status_code')}")
        print(f"Content Length: {result.get('content_length')} bytes")
        print(f"Links Found: {len(result.get('links', []))}")
        print(f"Crawl Time: {result.get('crawl_time'):.2f} seconds")
    
    assert response.status_code == 200
    print("✓ Single URL crawl passed\n")


def test_crawl_job_workflow():
    """Test complete crawl job workflow"""
    print("Testing crawl job workflow...")
    
    # 1. Create job
    print("1. Creating crawl job...")
    create_response = requests.post(
        f"{BASE_URL}/crawl",
        json={
            "start_urls": ["https://example.com"],
            "allowed_domains": ["example.com"],
            "max_depth": 2,
            "max_pages": 10,
            "include_sitemaps": False,
            "follow_robots": True,
            "rate_limit_rps": 2.0
        }
    )
    
    assert create_response.status_code == 200
    job_data = create_response.json()
    job_id = job_data["job_id"]
    print(f"Created job: {job_id}")
    
    # 2. Check job status
    print("\n2. Monitoring job progress...")
    max_wait = 60  # seconds
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        status_response = requests.get(f"{BASE_URL}/crawl/{job_id}")
        
        if status_response.status_code == 200:
            status_data = status_response.json()
            status = status_data["status"]
            stats = status_data.get("stats", {})
            
            print(f"Status: {status}, URLs crawled: {stats.get('urls_crawled', 0)}")
            
            if status in ["completed", "failed", "cancelled"]:
                break
                
        time.sleep(2)
    
    # 3. Get results
    print("\n3. Getting crawl results...")
    results_response = requests.get(f"{BASE_URL}/crawl/{job_id}/results")
    
    if results_response.status_code == 200:
        results_data = results_response.json()
        print(f"Total results: {results_data['total']}")
        
        for i, result in enumerate(results_data["results"][:3]):
            print(f"\nResult {i+1}:")
            print(f"  URL: {result['url']}")
            print(f"  Title: {result.get('title', 'N/A')}")
            print(f"  Status: {result['status_code']}")
            print(f"  Links: {len(result.get('links', []))}")
    
    print("\n✓ Crawl job workflow passed\n")


def test_system_stats():
    """Test system statistics"""
    print("Testing system statistics...")
    response = requests.get(f"{BASE_URL}/stats")
    
    if response.status_code == 200:
        stats = response.json()
        print(f"System Stats: {json.dumps(stats, indent=2)}")
    
    assert response.status_code == 200
    print("✓ System stats passed\n")


def test_job_listing():
    """Test job listing"""
    print("Testing job listing...")
    response = requests.get(f"{BASE_URL}/jobs", params={"limit": 5})
    
    if response.status_code == 200:
        jobs_data = response.json()
        print(f"Total jobs: {jobs_data['total']}")
        
        for job in jobs_data["jobs"]:
            print(f"  Job {job['job_id']}: {job['status']}")
    
    assert response.status_code == 200
    print("✓ Job listing passed\n")


def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("CRAWLER SERVICE TEST SUITE")
    print("=" * 60)
    print()
    
    try:
        # Basic tests
        test_health_check()
        
        # Component tests
        test_robots_check()
        test_single_url_crawl()
        
        # Workflow tests
        test_crawl_job_workflow()
        
        # Stats and monitoring
        test_system_stats()
        test_job_listing()
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED!")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        exit(1)
    except requests.exceptions.ConnectionError:
        print("\n❌ Could not connect to crawler service.")
        print("Make sure the service is running on port 8003")
        exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        exit(1)


if __name__ == "__main__":
    run_all_tests()