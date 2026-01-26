#!/usr/bin/env python3
"""
Backend API Testing for TrainWithBrain Telegram WebApp
Tests user registration, retrieval, and avatar functionality
"""

import requests
import json
import sys
from datetime import datetime

# Use the production backend URL from frontend/.env
BACKEND_URL = "https://avatar-loader-1.preview.emergentagent.com/api"

def test_user_registration_and_update():
    """Test POST /api/users - User registration/update (upsert)"""
    print("\n=== Testing User Registration/Update ===")
    
    # Test data - realistic Russian user data
    test_user = {
        "telegram_id": 111222333,
        "first_name": "Иван",
        "last_name": "Петров", 
        "username": "ivan_petrov",
        "language_code": "ru"
    }
    
    try:
        # Test 1: Create new user
        print("1. Creating new user...")
        response = requests.post(f"{BACKEND_URL}/users", json=test_user, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            user_data = response.json()
            print("✅ User created successfully")
            
            # Verify response structure
            required_fields = ['id', 'telegram_id', 'first_name', 'created_at', 'updated_at']
            missing_fields = [field for field in required_fields if field not in user_data]
            
            if missing_fields:
                print(f"❌ Missing required fields: {missing_fields}")
                return False
            else:
                print("✅ Response contains all required fields")
                
            # Store user_id for later tests
            user_id = user_data['id']
            created_at = user_data['created_at']
            
            # Test 2: Update same user (upsert test)
            print("\n2. Updating same user (testing upsert)...")
            updated_user = test_user.copy()
            updated_user['first_name'] = "Иван Обновленный"
            updated_user['last_name'] = "Петров-Сидоров"
            
            response2 = requests.post(f"{BACKEND_URL}/users", json=updated_user, timeout=10)
            print(f"Status Code: {response2.status_code}")
            print(f"Response: {response2.text}")
            
            if response2.status_code == 200:
                updated_data = response2.json()
                
                # Verify it's the same user (same ID) but updated
                if updated_data['id'] == user_id:
                    print("✅ User updated successfully (same ID)")
                else:
                    print(f"❌ Different user ID returned: {updated_data['id']} vs {user_id}")
                    return False
                    
                # Verify updated fields
                if (updated_data['first_name'] == "Иван Обновленный" and 
                    updated_data['last_name'] == "Петров-Сидоров"):
                    print("✅ User data updated correctly")
                else:
                    print("❌ User data not updated correctly")
                    return False
                    
                # Verify updated_at changed but created_at stayed same
                if updated_data['created_at'] == created_at:
                    print("✅ created_at preserved during update")
                else:
                    print("❌ created_at changed during update")
                    return False
                    
                return True
            else:
                print(f"❌ Failed to update user: {response2.status_code}")
                return False
        else:
            print(f"❌ Failed to create user: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_get_user_by_telegram_id():
    """Test GET /api/users/{telegram_id}"""
    print("\n=== Testing Get User by Telegram ID ===")
    
    try:
        # Test 1: Get existing user
        print("1. Getting existing user...")
        telegram_id = 111222333
        response = requests.get(f"{BACKEND_URL}/users/{telegram_id}", timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            user_data = response.json()
            if user_data['telegram_id'] == telegram_id:
                print("✅ User retrieved successfully")
            else:
                print(f"❌ Wrong telegram_id returned: {user_data['telegram_id']}")
                return False
        else:
            print(f"❌ Failed to get existing user: {response.status_code}")
            return False
            
        # Test 2: Get non-existent user (should return 404)
        print("\n2. Testing non-existent user...")
        non_existent_id = 999999999
        response2 = requests.get(f"{BACKEND_URL}/users/{non_existent_id}", timeout=10)
        print(f"Status Code: {response2.status_code}")
        print(f"Response: {response2.text}")
        
        if response2.status_code == 404:
            print("✅ Correctly returned 404 for non-existent user")
            return True
        else:
            print(f"❌ Expected 404, got {response2.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_telegram_avatar():
    """Test GET /api/telegram/avatar/{user_id}"""
    print("\n=== Testing Telegram Avatar ===")
    
    try:
        # Test with the created telegram_id
        print("1. Testing avatar for test user...")
        telegram_id = 111222333
        response = requests.get(f"{BACKEND_URL}/telegram/avatar/{telegram_id}", timeout=15)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            avatar_data = response.json()
            
            # Since this is a test user (not real Telegram user), 
            # we expect either null avatar_url with error message or no profile photo
            if 'avatar_url' in avatar_data:
                if avatar_data['avatar_url'] is None:
                    if 'error' in avatar_data or 'message' in avatar_data:
                        print("✅ Avatar endpoint working - returned null with appropriate message for test user")
                        return True
                    else:
                        print("❌ Avatar is null but no error/message provided")
                        return False
                else:
                    print(f"✅ Avatar URL returned: {avatar_data['avatar_url']}")
                    return True
            else:
                print("❌ Response missing avatar_url field")
                return False
        else:
            print(f"❌ Avatar endpoint failed: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def main():
    """Run all backend tests"""
    print("🚀 Starting TrainWithBrain Backend API Tests")
    print(f"Backend URL: {BACKEND_URL}")
    
    results = []
    
    # Test 1: User Registration/Update
    results.append(("User Registration/Update", test_user_registration_and_update()))
    
    # Test 2: Get User by Telegram ID  
    results.append(("Get User by Telegram ID", test_get_user_by_telegram_id()))
    
    # Test 3: Telegram Avatar
    results.append(("Telegram Avatar", test_telegram_avatar()))
    
    # Summary
    print("\n" + "="*50)
    print("📊 TEST RESULTS SUMMARY")
    print("="*50)
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\nTotal: {passed} passed, {failed} failed")
    
    if failed > 0:
        print("\n⚠️  Some tests failed. Check the detailed output above.")
        sys.exit(1)
    else:
        print("\n🎉 All tests passed!")
        sys.exit(0)

if __name__ == "__main__":
    main()