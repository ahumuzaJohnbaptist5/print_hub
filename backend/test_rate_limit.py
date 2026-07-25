#!/usr/bin/env python
"""
Test script for rate limiting
Run: python test_rate_limit.py
"""
import requests
import time

def test_rate_limit():
    """Test rate limiting by making multiple requests."""
    base_url = "http://localhost:8000"
    login_url = f"{base_url}/auth/login/"
    
    print("🧪 Testing Rate Limiting...")
    print("=" * 50)
    
    # Test login rate limiting
    print("\n📝 Testing login rate limiting...")
    
    for i in range(1, 8):
        print(f"  Attempt {i}...")
        response = requests.post(login_url, data={
            'username': 'test',
            'password': 'wrong_password'
        })
        
        print(f"  Status: {response.status_code}")
        
        if response.status_code == 429:
            print(f"  ✅ Rate limit triggered after {i} attempts!")
            print(f"  Message: {response.json().get('message', '')}")
            break
        
        time.sleep(0.5)
    
    print("\n✅ Rate limiting test complete!")

if __name__ == '__main__':
    test_rate_limit()
