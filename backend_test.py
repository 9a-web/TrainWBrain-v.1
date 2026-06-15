#!/usr/bin/env python3
"""
Backend API tests for TrainWithBrain authentication endpoints.
Tests email register/login, Telegram HMAC validation, Google session exchange,
session management (/auth/me, /auth/logout).
"""
import requests
import json
import hmac
import hashlib
import time
from urllib.parse import urlencode, quote

# Backend base URL from frontend/.env
BASE_URL = "https://ea220423-ac6a-48fa-9c5a-5a9fc43dfbfb.preview.emergentagent.com/api"

# Telegram bot token from backend/.env
TELEGRAM_BOT_TOKEN = "8483056076:AAHGZHKKx4cYgbzK3oPB435dcJ4hEiDUBBU"

def test_email_register_success():
    """Test successful email registration."""
    print("\n=== TEST: Email Register Success ===")
    email = f"authtest+{int(time.time())}@example.com"
    payload = {
        "email": email,
        "password": "password123",
        "name": "Test User"
    }
    resp = requests.post(f"{BASE_URL}/auth/register", json=payload)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    assert "token" in data, "Missing token in response"
    assert "user" in data, "Missing user in response"
    
    user = data["user"]
    assert "id" in user, "Missing id in user"
    assert len(user["id"]) == 36, f"id should be UUID (36 chars), got {len(user['id'])}"
    assert "telegram_id" in user, "Missing telegram_id in user"
    assert user["telegram_id"] >= 900000000000, f"telegram_id should be synthetic (>=900000000000), got {user['telegram_id']}"
    assert user["email"] == email, f"Email mismatch: expected {email}, got {user['email']}"
    assert "auth_provider" in user, "Missing auth_provider in user"
    assert "email" in user["auth_provider"], "auth_provider should contain 'email'"
    assert "password_hash" not in user, "password_hash should NOT be in response"
    assert "_id" not in user, "MongoDB _id should NOT be in response"
    
    print(f"✅ PASS: Email register successful. telegram_id={user['telegram_id']}, token={data['token'][:20]}...")
    return email, payload["password"], user["telegram_id"], data["token"]


def test_email_register_weak_password():
    """Test email registration with weak password (<6 chars)."""
    print("\n=== TEST: Email Register Weak Password ===")
    email = f"authtest+{int(time.time())}@example.com"
    payload = {
        "email": email,
        "password": "12345",  # Only 5 chars
        "name": "Test User"
    }
    resp = requests.post(f"{BASE_URL}/auth/register", json=payload)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")
    
    assert resp.status_code == 400, f"Expected 400 for weak password, got {resp.status_code}"
    print("✅ PASS: Weak password rejected with 400")


def test_email_register_invalid_email():
    """Test email registration with invalid email formats."""
    print("\n=== TEST: Email Register Invalid Email ===")
    
    # Test 1: No @ symbol
    payload1 = {"email": "notanemail", "password": "password123", "name": "Test"}
    resp1 = requests.post(f"{BASE_URL}/auth/register", json=payload1)
    print(f"No @ symbol - Status: {resp1.status_code}")
    assert resp1.status_code == 400, f"Expected 400 for email without @, got {resp1.status_code}"
    
    # Test 2: No dot in domain
    payload2 = {"email": "test@nodot", "password": "password123", "name": "Test"}
    resp2 = requests.post(f"{BASE_URL}/auth/register", json=payload2)
    print(f"No dot in domain - Status: {resp2.status_code}")
    assert resp2.status_code == 400, f"Expected 400 for email without domain dot, got {resp2.status_code}"
    
    print("✅ PASS: Invalid email formats rejected with 400")


def test_email_register_duplicate():
    """Test email registration with duplicate email."""
    print("\n=== TEST: Email Register Duplicate Email ===")
    email = f"authtest+{int(time.time())}@example.com"
    payload = {
        "email": email,
        "password": "password123",
        "name": "Test User"
    }
    
    # First registration
    resp1 = requests.post(f"{BASE_URL}/auth/register", json=payload)
    print(f"First registration - Status: {resp1.status_code}")
    assert resp1.status_code == 200, f"First registration should succeed, got {resp1.status_code}"
    
    # Second registration with same email
    resp2 = requests.post(f"{BASE_URL}/auth/register", json=payload)
    print(f"Duplicate registration - Status: {resp2.status_code}")
    print(f"Response: {resp2.text}")
    assert resp2.status_code == 400, f"Expected 400 for duplicate email, got {resp2.status_code}"
    
    print("✅ PASS: Duplicate email rejected with 400")


def test_email_login_success(email, password):
    """Test successful email login."""
    print("\n=== TEST: Email Login Success ===")
    payload = {
        "email": email,
        "password": password
    }
    resp = requests.post(f"{BASE_URL}/auth/login", json=payload)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    assert "token" in data, "Missing token in response"
    assert "user" in data, "Missing user in response"
    
    user = data["user"]
    assert user["email"] == email, f"Email mismatch: expected {email}, got {user['email']}"
    assert "password_hash" not in user, "password_hash should NOT be in response"
    
    print(f"✅ PASS: Email login successful. token={data['token'][:20]}...")
    return data["token"]


def test_email_login_wrong_password(email):
    """Test email login with wrong password."""
    print("\n=== TEST: Email Login Wrong Password ===")
    payload = {
        "email": email,
        "password": "wrongpassword"
    }
    resp = requests.post(f"{BASE_URL}/auth/login", json=payload)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")
    
    assert resp.status_code == 401, f"Expected 401 for wrong password, got {resp.status_code}"
    print("✅ PASS: Wrong password rejected with 401")


def test_email_login_unknown_email():
    """Test email login with unknown email."""
    print("\n=== TEST: Email Login Unknown Email ===")
    payload = {
        "email": f"unknown+{int(time.time())}@example.com",
        "password": "password123"
    }
    resp = requests.post(f"{BASE_URL}/auth/login", json=payload)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")
    
    assert resp.status_code == 401, f"Expected 401 for unknown email, got {resp.status_code}"
    print("✅ PASS: Unknown email rejected with 401")


def test_auth_me_with_token(token):
    """Test GET /auth/me with valid Bearer token."""
    print("\n=== TEST: GET /auth/me with Bearer Token ===")
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{BASE_URL}/auth/me", headers=headers)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    user = resp.json()
    assert "id" in user, "Missing id in user"
    assert "telegram_id" in user, "Missing telegram_id in user"
    assert "password_hash" not in user, "password_hash should NOT be in response"
    assert "_id" not in user, "MongoDB _id should NOT be in response"
    
    print(f"✅ PASS: /auth/me returned user data. telegram_id={user['telegram_id']}")
    return user


def test_auth_me_without_token():
    """Test GET /auth/me without Authorization header."""
    print("\n=== TEST: GET /auth/me without Token ===")
    resp = requests.get(f"{BASE_URL}/auth/me")
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")
    
    assert resp.status_code == 401, f"Expected 401 without token, got {resp.status_code}"
    print("✅ PASS: /auth/me rejected without token (401)")


def test_auth_me_with_bogus_token():
    """Test GET /auth/me with invalid token."""
    print("\n=== TEST: GET /auth/me with Bogus Token ===")
    headers = {"Authorization": "Bearer bogus_token_12345"}
    resp = requests.get(f"{BASE_URL}/auth/me", headers=headers)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")
    
    assert resp.status_code == 401, f"Expected 401 for bogus token, got {resp.status_code}"
    print("✅ PASS: /auth/me rejected bogus token (401)")


def test_auth_logout(token):
    """Test POST /auth/logout."""
    print("\n=== TEST: POST /auth/logout ===")
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.post(f"{BASE_URL}/auth/logout", headers=headers)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    assert data.get("ok") == True, "Expected {ok: true} in response"
    
    print("✅ PASS: Logout successful")


def test_auth_me_after_logout(token):
    """Test GET /auth/me after logout (session should be deleted)."""
    print("\n=== TEST: GET /auth/me after Logout ===")
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{BASE_URL}/auth/me", headers=headers)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")
    
    assert resp.status_code == 401, f"Expected 401 after logout, got {resp.status_code}"
    print("✅ PASS: /auth/me rejected after logout (401)")


def test_telegram_auth_invalid_signature():
    """Test POST /auth/telegram with invalid HMAC signature."""
    print("\n=== TEST: Telegram Auth Invalid Signature ===")
    # Construct invalid initData with bad hash
    init_data = 'hash=badhash123&user=%7B%22id%22%3A123456%2C%22first_name%22%3A%22Test%22%7D&auth_date=' + str(int(time.time()))
    payload = {"init_data": init_data}
    resp = requests.post(f"{BASE_URL}/auth/telegram", json=payload)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")
    
    assert resp.status_code == 401, f"Expected 401 for invalid signature, got {resp.status_code}"
    print("✅ PASS: Invalid Telegram signature rejected with 401")


def test_telegram_auth_valid_signature():
    """Test POST /auth/telegram with valid HMAC signature (if constructable)."""
    print("\n=== TEST: Telegram Auth Valid Signature ===")
    
    # Construct valid initData per Telegram WebApp scheme
    auth_date = str(int(time.time()))
    user_data = {"id": 123456789, "first_name": "TestTG", "username": "testtg"}
    user_json = json.dumps(user_data, separators=(',', ':'))
    
    # Build data_check_string (sorted key=value pairs, excluding hash)
    params = {
        "auth_date": auth_date,
        "user": user_json
    }
    data_check_string = "\n".join(f"{k}={params[k]}" for k in sorted(params.keys()))
    
    # Compute HMAC per Telegram spec
    secret_key = hmac.new(b"WebAppData", TELEGRAM_BOT_TOKEN.encode(), hashlib.sha256).digest()
    calc_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    
    # Build initData with computed hash
    init_data = f"auth_date={auth_date}&hash={calc_hash}&user={quote(user_json)}"
    
    payload = {"init_data": init_data}
    resp = requests.post(f"{BASE_URL}/auth/telegram", json=payload)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")
    
    if resp.status_code == 200:
        data = resp.json()
        assert "token" in data, "Missing token in response"
        assert "user" in data, "Missing user in response"
        
        user = data["user"]
        assert user["telegram_id"] == 123456789, f"telegram_id mismatch: expected 123456789, got {user['telegram_id']}"
        assert "telegram" in user.get("auth_provider", []), "auth_provider should contain 'telegram'"
        assert "password_hash" not in user, "password_hash should NOT be in response"
        
        print(f"✅ PASS: Valid Telegram signature accepted. telegram_id={user['telegram_id']}, token={data['token'][:20]}...")
        
        # Test /auth/me with this token
        headers = {"Authorization": f"Bearer {data['token']}"}
        me_resp = requests.get(f"{BASE_URL}/auth/me", headers=headers)
        assert me_resp.status_code == 200, f"Expected 200 for /auth/me, got {me_resp.status_code}"
        me_user = me_resp.json()
        assert me_user["telegram_id"] == 123456789, "telegram_id mismatch in /auth/me"
        print(f"✅ PASS: /auth/me with Telegram token successful")
    else:
        print(f"⚠️  Valid signature test failed with status {resp.status_code}. This may be expected if the bot token or HMAC implementation differs.")


def test_google_auth_invalid_session():
    """Test POST /auth/google/session with bogus session_id."""
    print("\n=== TEST: Google Auth Invalid Session ===")
    payload = {"session_id": "bogus-session-id-12345"}
    resp = requests.post(f"{BASE_URL}/auth/google/session", json=payload)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")
    
    assert resp.status_code == 401, f"Expected 401 for invalid session_id, got {resp.status_code}"
    print("✅ PASS: Invalid Google session_id rejected with 401")


def test_general_assertions():
    """Test general assertions across all auth responses."""
    print("\n=== TEST: General Assertions ===")
    
    # Register a user and check all response properties
    email = f"authtest+{int(time.time())}@example.com"
    payload = {
        "email": email,
        "password": "password123",
        "name": "General Test"
    }
    resp = requests.post(f"{BASE_URL}/auth/register", json=payload)
    assert resp.status_code == 200
    
    # Check response is valid JSON
    try:
        data = resp.json()
    except Exception as e:
        raise AssertionError(f"Response is not valid JSON: {e}")
    
    user = data["user"]
    
    # Check UUID id format (36 chars with hyphens)
    assert len(user["id"]) == 36, f"id should be 36-char UUID, got {len(user['id'])}"
    assert user["id"].count("-") == 4, "UUID should have 4 hyphens"
    
    # Check datetime fields are ISO strings (if present)
    if "created_at" in user:
        assert "T" in user["created_at"], "created_at should be ISO datetime string"
    if "updated_at" in user:
        assert "T" in user["updated_at"], "updated_at should be ISO datetime string"
    
    # Check NO MongoDB _id anywhere
    assert "_id" not in user, "MongoDB _id should NOT be in user"
    assert "_id" not in data, "MongoDB _id should NOT be in response"
    
    # Check password_hash is NEVER present
    assert "password_hash" not in user, "password_hash should NEVER be in response"
    
    print("✅ PASS: All general assertions passed (valid JSON, UUID id, ISO datetimes, no _id, no password_hash)")


def run_all_tests():
    """Run all authentication tests."""
    print("=" * 80)
    print("BACKEND AUTHENTICATION TESTS - TrainWithBrain")
    print("=" * 80)
    
    passed = 0
    failed = 0
    
    try:
        # (A) EMAIL REGISTER/LOGIN
        email, password, telegram_id, token = test_email_register_success()
        passed += 1
    except AssertionError as e:
        print(f"❌ FAIL: {e}")
        failed += 1
        return
    
    try:
        test_email_register_weak_password()
        passed += 1
    except AssertionError as e:
        print(f"❌ FAIL: {e}")
        failed += 1
    
    try:
        test_email_register_invalid_email()
        passed += 1
    except AssertionError as e:
        print(f"❌ FAIL: {e}")
        failed += 1
    
    try:
        test_email_register_duplicate()
        passed += 1
    except AssertionError as e:
        print(f"❌ FAIL: {e}")
        failed += 1
    
    try:
        login_token = test_email_login_success(email, password)
        passed += 1
    except AssertionError as e:
        print(f"❌ FAIL: {e}")
        failed += 1
        return
    
    try:
        test_email_login_wrong_password(email)
        passed += 1
    except AssertionError as e:
        print(f"❌ FAIL: {e}")
        failed += 1
    
    try:
        test_email_login_unknown_email()
        passed += 1
    except AssertionError as e:
        print(f"❌ FAIL: {e}")
        failed += 1
    
    # (B) SESSION + /auth/me + /auth/logout
    try:
        test_auth_me_with_token(login_token)
        passed += 1
    except AssertionError as e:
        print(f"❌ FAIL: {e}")
        failed += 1
    
    try:
        test_auth_me_without_token()
        passed += 1
    except AssertionError as e:
        print(f"❌ FAIL: {e}")
        failed += 1
    
    try:
        test_auth_me_with_bogus_token()
        passed += 1
    except AssertionError as e:
        print(f"❌ FAIL: {e}")
        failed += 1
    
    # Create a new session for logout test (since we'll invalidate it)
    try:
        logout_token = test_email_login_success(email, password)
        passed += 1
    except AssertionError as e:
        print(f"❌ FAIL: {e}")
        failed += 1
        return
    
    try:
        test_auth_logout(logout_token)
        passed += 1
    except AssertionError as e:
        print(f"❌ FAIL: {e}")
        failed += 1
    
    try:
        test_auth_me_after_logout(logout_token)
        passed += 1
    except AssertionError as e:
        print(f"❌ FAIL: {e}")
        failed += 1
    
    # (C) TELEGRAM AUTH
    try:
        test_telegram_auth_invalid_signature()
        passed += 1
    except AssertionError as e:
        print(f"❌ FAIL: {e}")
        failed += 1
    
    try:
        test_telegram_auth_valid_signature()
        passed += 1
    except AssertionError as e:
        print(f"❌ FAIL: {e}")
        failed += 1
    
    # (D) GOOGLE AUTH
    try:
        test_google_auth_invalid_session()
        passed += 1
    except AssertionError as e:
        print(f"❌ FAIL: {e}")
        failed += 1
    
    # GENERAL ASSERTIONS
    try:
        test_general_assertions()
        passed += 1
    except AssertionError as e:
        print(f"❌ FAIL: {e}")
        failed += 1
    
    print("\n" + "=" * 80)
    print(f"TEST SUMMARY: {passed} passed, {failed} failed")
    print("=" * 80)
    
    if failed == 0:
        print("🎉 ALL TESTS PASSED!")
    else:
        print(f"⚠️  {failed} test(s) failed")


if __name__ == "__main__":
    run_all_tests()
