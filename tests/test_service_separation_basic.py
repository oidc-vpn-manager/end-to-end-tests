#!/usr/bin/env python3
"""
Basic service separation test that can be run independently.
"""

import requests
import time
import sys


def test_services_are_running():
    """Test that all three services are accessible."""
    services = [
        ("Combined", "http://localhost"),
        ("User", "http://localhost:8450"), 
        ("Admin", "http://localhost:8540")
    ]
    
    print("🔍 Testing service accessibility...")
    for name, base_url in services:
        try:
            response = requests.get(f"{base_url}/health", timeout=5)
            if response.status_code == 200:
                print(f"  ✅ {name} service ({base_url}) - Healthy")
            else:
                print(f"  ❌ {name} service ({base_url}) - HTTP {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"  ❌ {name} service ({base_url}) - Connection failed: {e}")
            return False
    
    return True


def test_service_separation_basic():
    """Test basic service separation functionality."""
    print("\n🔒 Testing service separation...")
    
    # Test 1: User service rejects admin routes
    print("  Testing user service rejects admin routes...")
    response = requests.get("http://localhost:8450/admin/psk", allow_redirects=False)
    if response.status_code == 403:
        print("    ✅ Admin route correctly rejected (403)")
    else:
        print(f"    ❌ Expected 403, got {response.status_code}")
        return False
    
    # Test 2: Admin service redirects user routes
    print("  Testing admin service redirects user routes...")
    response = requests.get("http://localhost:8540/profile/certificates", allow_redirects=False)
    if response.status_code == 301 and "localhost:8450" in response.headers.get('Location', ''):
        print("    ✅ User route correctly redirected to user service (301)")
    else:
        print(f"    ❌ Expected 301 redirect to user service, got {response.status_code}")
        print(f"    Location header: {response.headers.get('Location', 'None')}")
        return False
    
    # Test 3: Combined service allows all routes
    print("  Testing combined service allows all routes...")
    response = requests.get("http://localhost/admin/psk", allow_redirects=False)
    if response.status_code == 302:  # Should redirect to login, not reject with 403
        print("    ✅ Admin route accessible (redirects to login)")
    else:
        print(f"    ❌ Expected 302 (login redirect), got {response.status_code}")
        return False
    
    return True


def test_api_separation():
    """Test API endpoint separation."""
    print("\n🔌 Testing API endpoint separation...")
    
    # Test 1: User service API endpoints
    print("  Testing user service API endpoints...")
    
    # Should reject server bundle (admin function) - returns 403 (forbidden)
    response = requests.get(
        "http://localhost:8450/api/v1/server/bundle",
        headers={"Authorization": "Bearer invalid-key"},
        allow_redirects=False
    )
    if response.status_code == 403:
        print("    ✅ Server bundle API correctly forbidden (403)")
    else:
        print(f"    ❌ Expected 403 (forbidden), got {response.status_code}")
        return False
    
    # Test 2: Admin service API endpoints
    print("  Testing admin service API endpoints...")
    
    # Should accept server bundle (admin function) - returns 401 (exists but unauthorized) 
    response = requests.get(
        "http://localhost:8540/api/v1/server/bundle",
        headers={"Authorization": "Bearer invalid-key"},
        allow_redirects=False
    )
    if response.status_code == 401:
        print("    ✅ Server bundle API available (401 - endpoint exists)")
    else:
        print(f"    ❌ Expected 401 (endpoint exists), got {response.status_code}")
        return False
    
    return True


def main():
    """Run all service separation tests."""
    print("🚀 Service Separation Test Suite\n")
    
    tests = [
        ("Service Accessibility", test_services_are_running),
        ("Basic Service Separation", test_service_separation_basic),
        ("API Endpoint Separation", test_api_separation),
    ]
    
    failed_tests = []
    
    for test_name, test_func in tests:
        print(f"\n📋 Running: {test_name}")
        try:
            if test_func():
                print(f"✅ {test_name} - PASSED")
            else:
                print(f"❌ {test_name} - FAILED")
                failed_tests.append(test_name)
        except Exception as e:
            print(f"❌ {test_name} - ERROR: {e}")
            failed_tests.append(test_name)
    
    print(f"\n📊 Test Results:")
    if not failed_tests:
        print("🎉 All tests passed! Service separation is working correctly.")
        sys.exit(0)
    else:
        print(f"💥 {len(failed_tests)} test(s) failed:")
        for test in failed_tests:
            print(f"  - {test}")
        print("\nEnsure all services are running with correct configuration:")
        print("  docker-compose -f tests/docker-compose.yml up")
        sys.exit(1)


if __name__ == "__main__":
    main()