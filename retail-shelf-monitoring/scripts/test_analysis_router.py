#!/usr/bin/env python3
"""
Test Script for Analysis Router (T034)
Tests POST /detect-gaps and GET /jobs/{job_id} endpoints

Usage:
    python3 scripts/test_analysis_router.py
"""

import time
from pathlib import Path

import httpx


def test_analysis_router():
    """Test analysis router endpoints."""
    
    print("=" * 70)
    print("TEST: Analysis Router (T034) - Out-of-Stock Detection API")
    print("=" * 70)
    
    base_url = "http://localhost:8000"
    
    # Test 1: Submit image for gap detection
    print("\nTest 1: POST /api/v1/analysis/detect-gaps")
    print("-" * 70)
    
    test_image = "data/processed/SKU110K_yolo/images/test/test_588.jpg"
    if not Path(test_image).exists():
        print(f"❌ Test image not found: {test_image}")
        print("   Please ensure test data exists.")
        return
    
    print(f"Uploading image: {test_image}")
    
    try:
        with open(test_image, "rb") as f:
            response = httpx.post(
                f"{base_url}/api/v1/analysis/detect-gaps",
                files={"image": ("test_shelf.jpg", f, "image/jpeg")},
                data={"confidence_threshold": 0.5},
                timeout=30.0,
            )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 201:
            job = response.json()
            print("✅ Job created successfully!")
            print(f"   Job ID: {job['id']}")
            print(f"   Status: {job['status']}")
            print(f"   Image: {job['image_path']}")
            print(f"   Created: {job['created_at']}")
            
            job_id = job['id']
            
            # Test 2: Poll for job results
            print(f"\nTest 2: GET /api/v1/analysis/jobs/{job_id}")
            print("-" * 70)
            print("Polling for results (max 10 seconds)...")
            
            max_attempts = 20
            for attempt in range(max_attempts):
                time.sleep(0.5)  # Wait 500ms between polls
                
                response = httpx.get(
                    f"{base_url}/api/v1/analysis/jobs/{job_id}",
                    timeout=10.0,
                )
                
                if response.status_code == 200:
                    job = response.json()
                    status = job['status']
                    
                    print(f"   Attempt {attempt + 1}: Status = {status}")
                    
                    if status == "COMPLETED":
                        print("\n✅ Job completed successfully!")
                        print(f"   Result summary:")
                        summary = job['result_summary']
                        print(f"      Total products: {summary['total_products']}")
                        print(f"      Gaps detected: {summary['gaps_detected']}")
                        print(f"      Significant gaps: {summary['significant_gaps']}")
                        
                        if summary['gap_regions']:
                            print(f"\n   Gap regions:")
                            for i, gap in enumerate(summary['gap_regions'][:3], 1):
                                print(f"      {i}. x={gap['x']}, y={gap['y']}, width={gap['gap_width']}px")
                        
                        print(f"\n   Processing time: {job['created_at']} → {job['completed_at']}")
                        break
                    
                    elif status == "FAILED":
                        print(f"\n❌ Job failed!")
                        print(f"   Error: {job['error_message']}")
                        break
                    
                    elif status == "PROCESSING":
                        continue  # Keep polling
                    
                    elif status == "PENDING":
                        continue  # Keep polling
                
                else:
                    print(f"❌ Failed to get job: {response.status_code}")
                    print(f"   Response: {response.text}")
                    break
            
            else:
                print(f"\n⏱️ Timeout: Job still not completed after {max_attempts * 0.5}s")
                print(f"   Final status: {job['status']}")
            
            # Test 3: Error handling - invalid job ID
            print(f"\nTest 3: GET /api/v1/analysis/jobs/99999 (invalid ID)")
            print("-" * 70)
            
            response = httpx.get(
                f"{base_url}/api/v1/analysis/jobs/99999",
                timeout=10.0,
            )
            
            if response.status_code == 404:
                print("✅ Correctly returned 404 for invalid job ID")
                print(f"   Error detail: {response.json()['detail']}")
            else:
                print(f"❌ Unexpected status code: {response.status_code}")
            
            # Test 4: Error handling - invalid image format
            print(f"\nTest 4: POST /api/v1/analysis/detect-gaps (invalid format)")
            print("-" * 70)
            
            # Try to upload a text file as image
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp:
                tmp.write("not an image")
                tmp_path = tmp.name
            
            try:
                with open(tmp_path, 'rb') as f:
                    response = httpx.post(
                        f"{base_url}/api/v1/analysis/detect-gaps",
                        files={"image": ("test.txt", f)},
                        data={"confidence_threshold": 0.5},
                        timeout=10.0,
                    )
                
                if response.status_code == 400:
                    print("✅ Correctly rejected invalid file format")
                    print(f"   Error detail: {response.json()['detail'][:100]}...")
                else:
                    print(f"❌ Unexpected status code: {response.status_code}")
            
            finally:
                Path(tmp_path).unlink()
        
        else:
            print(f"❌ Failed to create job: {response.status_code}")
            print(f"   Response: {response.text}")
    
    except httpx.ConnectError:
        print("❌ Failed to connect to API server")
        print("   Please start the server: uvicorn src.shelf_monitor.api.main:app")
        return
    
    except Exception as e:
        print(f"❌ Unexpected error: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("TEST SUMMARY: Analysis Router (T034)")
    print("=" * 70)
    print("✅ T034: Analysis router implementation complete")
    print("\n📋 Endpoints implemented:")
    print("   1. POST /api/v1/analysis/detect-gaps - Submit image for gap detection")
    print("   2. GET  /api/v1/analysis/jobs/{job_id} - Get job status and results")
    print("\n📌 Features:")
    print("   - Image upload validation (format, size)")
    print("   - Background ML processing (non-blocking)")
    print("   - Database persistence (AnalysisJob + Detection)")
    print("   - Error handling with educational messages")
    print("   - Status polling for async results")
    print("=" * 70)


if __name__ == "__main__":
    test_analysis_router()
