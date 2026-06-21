#!/usr/bin/env python3
"""
Debug script to investigate the date-aware progress issue
"""

import requests
import json
import random

BASE_URL = "https://1db6bd65-9d5b-4875-a5d8-adc82ec9d902.preview.emergentagent.com/api"

def main():
    # Generate unique test email
    timestamp = random.randint(1000000000, 9999999999)
    email = f"debugtest{timestamp}@example.com"
    password = "testpass123"
    name = "Debug Test User"
    
    # Register
    resp = requests.post(f"{BASE_URL}/auth/register", json={
        "email": email,
        "password": password,
        "name": name
    })
    data = resp.json()
    token = data["token"]
    athlete_telegram_id = data["user"]["telegram_id"]
    print(f"Registered: telegram_id={athlete_telegram_id}")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Find template
    resp = requests.get(f"{BASE_URL}/programs/templates")
    templates = resp.json()
    template = next((t for t in templates if t["slug"] == "full-body-beginner"), None)
    template_id = template["id"]
    
    # Create plan
    resp = requests.post(f"{BASE_URL}/plans", headers=headers, json={
        "athlete_telegram_id": athlete_telegram_id,
        "template_id": template_id
    })
    plan = resp.json()
    plan_id = plan["id"]
    print(f"Plan ID: {plan_id}")
    
    # Start session with date
    session_date = "2026-06-17"
    resp = requests.post(f"{BASE_URL}/sessions/start", headers=headers, json={
        "plan_id": plan_id,
        "athlete_telegram_id": athlete_telegram_id,
        "week": 1,
        "day": 1,
        "date": session_date
    })
    session = resp.json()
    session_id = session["id"]
    print(f"Session ID: {session_id}")
    print(f"Session date: {session['date']}")
    
    # Mark all exercises done
    for i in range(len(session["exercises"])):
        requests.patch(
            f"{BASE_URL}/sessions/{session_id}/exercise/{i}?action=done",
            headers=headers
        )
    
    # Get session to verify it's finished
    resp = requests.get(f"{BASE_URL}/sessions/{session_id}", headers=headers)
    session = resp.json()
    print(f"Session status: {session['status']}")
    print(f"Session date: {session['date']}")
    print(f"Session week_index: {session['week_index']}")
    print(f"Session day_index: {session['day_index']}")
    
    # Current week dates (2026-06-17 is Wednesday, day_index 3)
    # But we started session on day=1 (Monday)
    # So 2026-06-17 should be day_index 3, not day_index 1
    # Let me recalculate...
    
    # Actually, the issue is: we started session with day=1 and date="2026-06-17"
    # But 2026-06-17 is a Wednesday (day_index 3 in Mon-Sun week)
    # So the dates array should have 2026-06-17 at index 0 (for day_index 1)
    
    # Let's try with the correct mapping:
    # If day_index=1 and date=2026-06-17, then:
    # day_index 1 = 2026-06-17 (Mon)
    # day_index 2 = 2026-06-18 (Tue)
    # day_index 3 = 2026-06-19 (Wed)
    # etc.
    
    current_week_dates = [
        "2026-06-17",  # Mon (day_index 1)
        "2026-06-18",  # Tue (day_index 2)
        "2026-06-19",  # Wed (day_index 3)
        "2026-06-20",  # Thu (day_index 4)
        "2026-06-21",  # Fri (day_index 5)
        "2026-06-22",  # Sat (day_index 6)
        "2026-06-23",  # Sun (day_index 7)
    ]
    
    print("\n--- Testing with current week dates ---")
    dates_param = ",".join(current_week_dates)
    resp = requests.get(
        f"{BASE_URL}/plans/{plan_id}/week-progress",
        params={"week": 1, "viewer": athlete_telegram_id, "dates": dates_param}
    )
    progress = resp.json()
    print(f"Week progress response:")
    print(json.dumps(progress, indent=2))
    
    # Previous week dates
    previous_week_dates = [
        "2026-06-10",  # Mon (day_index 1)
        "2026-06-11",  # Tue (day_index 2)
        "2026-06-12",  # Wed (day_index 3)
        "2026-06-13",  # Thu (day_index 4)
        "2026-06-14",  # Fri (day_index 5)
        "2026-06-15",  # Sat (day_index 6)
        "2026-06-16",  # Sun (day_index 7)
    ]
    
    print("\n--- Testing with previous week dates ---")
    dates_param = ",".join(previous_week_dates)
    resp = requests.get(
        f"{BASE_URL}/plans/{plan_id}/week-progress",
        params={"week": 1, "viewer": athlete_telegram_id, "dates": dates_param}
    )
    progress = resp.json()
    print(f"Week progress response:")
    print(json.dumps(progress, indent=2))
    
    print("\n--- Testing without dates (backward compat) ---")
    resp = requests.get(
        f"{BASE_URL}/plans/{plan_id}/week-progress",
        params={"week": 1, "viewer": athlete_telegram_id}
    )
    progress = resp.json()
    print(f"Week progress response:")
    print(json.dumps(progress, indent=2))

if __name__ == "__main__":
    main()
