#!/usr/bin/env python3
"""
TrainWithBrain Phase 2 Backend Testing
Tests workout sessions, %1RM enrichment, and stats endpoints
"""
import requests
import json
from datetime import datetime

# Backend URL from frontend/.env
BASE_URL = "https://1b1e8c30-249f-4dd6-8a12-b704edc01188.preview.emergentagent.com/api"

# Test athlete
ATHLETE_ID = 880099

def print_section(title):
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")

def print_test(name, passed, details=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status}: {name}")
    if details:
        print(f"  → {details}")

def test_phase2_plan_enrichment():
    """Test A: Plan day enrichment + %1RM"""
    print_section("TEST A: Plan Day Enrichment + %1RM")
    
    # 1. Find powerlifting-peaking template
    print("1. Finding 'powerlifting-peaking' template...")
    resp = requests.get(f"{BASE_URL}/programs/templates")
    assert resp.status_code == 200, f"GET templates failed: {resp.status_code}"
    templates = resp.json()
    
    pl_template = None
    for t in templates:
        if t.get("slug") == "powerlifting-peaking":
            pl_template = t
            break
    
    test_passed = pl_template is not None
    print_test("Found powerlifting-peaking template", test_passed, 
               f"Template ID: {pl_template['id']}" if test_passed else "Template not found")
    if not test_passed:
        return False
    
    template_id = pl_template["id"]
    
    # 2. Create plan for athlete 880099
    print("\n2. Creating plan from powerlifting-peaking template...")
    plan_payload = {
        "athlete_telegram_id": ATHLETE_ID,
        "template_id": template_id
    }
    resp = requests.post(f"{BASE_URL}/plans", json=plan_payload)
    assert resp.status_code == 200, f"POST plan failed: {resp.status_code} - {resp.text}"
    plan = resp.json()
    plan_id = plan["id"]
    
    # Verify one_rep_max is populated
    orm = plan.get("one_rep_max", {})
    has_orm = len(orm) > 0 and "bench-press" in orm and "back-squat" in orm and "deadlift" in orm
    print_test("Plan has one_rep_max populated", has_orm,
               f"ORM keys: {list(orm.keys())[:5]}... (bench-press:{orm.get('bench-press')}, back-squat:{orm.get('back-squat')}, deadlift:{orm.get('deadlift')})")
    
    # Verify expected values
    expected_orm = {"bench-press": 140, "back-squat": 170, "deadlift": 200}
    orm_correct = all(orm.get(k) == v for k, v in expected_orm.items())
    print_test("ORM values match expected", orm_correct,
               f"Expected: {expected_orm}, Got: {orm.get('bench-press')}, {orm.get('back-squat')}, {orm.get('deadlift')}")
    
    # 3. GET day 1 (heavy day with 7 exercises)
    print("\n3. Getting plan day week=1, day=1 (heavy day)...")
    resp = requests.get(f"{BASE_URL}/plans/{plan_id}/day", params={"week": 1, "day": 1})
    assert resp.status_code == 200, f"GET day failed: {resp.status_code}"
    day = resp.json()
    
    # Verify is_rest=false
    is_workout = not day.get("is_rest", True)
    print_test("Day 1 is workout day (not rest)", is_workout, f"is_rest={day.get('is_rest')}")
    
    # Verify 7 exercises
    exercises = day.get("exercises", [])
    has_7_exercises = len(exercises) == 7
    print_test("Day has exactly 7 exercises", has_7_exercises, f"Count: {len(exercises)}")
    
    # Verify day-level group and difficulty
    day_group = day.get("group", "")
    day_difficulty = day.get("difficulty")
    has_day_meta = bool(day_group) and day_difficulty is not None
    print_test("Day has group and difficulty", has_day_meta,
               f"group='{day_group}', difficulty='{day_difficulty}'")
    
    # Expected: group like "Н+Г+С+Р+К" and difficulty "Тяжело"
    group_correct = "Н" in day_group and "Г" in day_group and "С" in day_group
    difficulty_correct = day_difficulty == "Тяжело"
    print_test("Day group contains Н+Г+С", group_correct, f"group='{day_group}'")
    print_test("Day difficulty is 'Тяжело'", difficulty_correct, f"difficulty='{day_difficulty}'")
    
    # 4. Verify each exercise has required fields
    print("\n4. Verifying exercise structure...")
    all_exercises_valid = True
    for i, ex in enumerate(exercises):
        has_muscle_letter = "muscle_letter" in ex and ex["muscle_letter"]
        has_difficulty = "difficulty" in ex
        has_tonnage = "tonnage" in ex
        has_sets_scheme = "sets_scheme" in ex and isinstance(ex["sets_scheme"], list)
        
        if not (has_muscle_letter and has_difficulty and has_tonnage and has_sets_scheme):
            all_exercises_valid = False
            print(f"  Exercise {i} ({ex.get('exercise_name')}): missing fields")
        
        # Check sets_scheme structure
        if has_sets_scheme:
            for s in ex["sets_scheme"]:
                if "percent_1rm" not in s:
                    all_exercises_valid = False
                    print(f"  Exercise {i} set missing percent_1rm")
    
    print_test("All exercises have muscle_letter, difficulty, tonnage, sets_scheme with percent_1rm",
               all_exercises_valid)
    
    # 5. Verify specific percent_1rm calculations
    print("\n5. Verifying specific %1RM calculations...")
    
    # Find "Жим лёжа (без ног)" - bench-no-legs
    bench_ex = None
    for ex in exercises:
        if "без ног" in ex.get("exercise_name", ""):
            bench_ex = ex
            break
    
    if bench_ex:
        sets = bench_ex.get("sets_scheme", [])
        if len(sets) >= 2:
            # First set: 127.5kg -> 91% (127.5/140*100 = 91.07)
            set1 = sets[0]
            set1_weight = set1.get("weight")
            set1_pct = set1.get("percent_1rm")
            set1_correct = set1_weight == 127.5 and set1_pct == 91
            print_test("Bench (no legs) set 1: 127.5kg -> 91%", set1_correct,
                       f"weight={set1_weight}, percent_1rm={set1_pct}")
            
            # Second set: 115kg -> 82% (115/140*100 = 82.14)
            set2 = sets[1]
            set2_weight = set2.get("weight")
            set2_pct = set2.get("percent_1rm")
            set2_correct = set2_weight == 115 and set2_pct == 82
            print_test("Bench (no legs) set 2: 115kg -> 82%", set2_correct,
                       f"weight={set2_weight}, percent_1rm={set2_pct}")
        else:
            print_test("Bench (no legs) has 2+ sets", False, f"Only {len(sets)} sets found")
    else:
        print_test("Found 'Жим лёжа (без ног)' exercise", False, "Exercise not found")
    
    # Find "Присед (с паузой)" - squat-paused
    squat_ex = None
    for ex in exercises:
        if "паузой" in ex.get("exercise_name", ""):
            squat_ex = ex
            break
    
    if squat_ex:
        sets = squat_ex.get("sets_scheme", [])
        if len(sets) >= 2:
            # First set: 160kg -> 94% (160/170*100 = 94.12)
            set1 = sets[0]
            set1_weight = set1.get("weight")
            set1_pct = set1.get("percent_1rm")
            set1_correct = set1_weight == 160 and set1_pct == 94
            print_test("Squat (paused) set 1: 160kg -> 94%", set1_correct,
                       f"weight={set1_weight}, percent_1rm={set1_pct}")
            
            # Second set: 142.5kg -> 84% (142.5/170*100 = 83.82)
            set2 = sets[1]
            set2_weight = set2.get("weight")
            set2_pct = set2.get("percent_1rm")
            set2_correct = set2_weight == 142.5 and set2_pct == 84
            print_test("Squat (paused) set 2: 142.5kg -> 84%", set2_correct,
                       f"weight={set2_weight}, percent_1rm={set2_pct}")
        else:
            print_test("Squat (paused) has 2+ sets", False, f"Only {len(sets)} sets found")
    else:
        print_test("Found 'Присед (с паузой)' exercise", False, "Exercise not found")
    
    # 6. GET day 3 (rest day)
    print("\n6. Getting plan day week=1, day=3 (rest day)...")
    resp = requests.get(f"{BASE_URL}/plans/{plan_id}/day", params={"week": 1, "day": 3})
    assert resp.status_code == 200, f"GET day 3 failed: {resp.status_code}"
    day3 = resp.json()
    
    is_rest = day3.get("is_rest", False)
    print_test("Day 3 is rest day", is_rest, f"is_rest={is_rest}")
    
    return plan_id


def test_phase2_sessions(plan_id):
    """Test B: Workout sessions lifecycle"""
    print_section("TEST B: Workout Sessions Lifecycle")
    
    # 1. Start session for week=1, day=1
    print("1. Starting session for week=1, day=1...")
    session_payload = {
        "plan_id": plan_id,
        "athlete_telegram_id": ATHLETE_ID,
        "week": 1,
        "day": 1
    }
    resp = requests.post(f"{BASE_URL}/sessions/start", json=session_payload)
    assert resp.status_code == 200, f"POST sessions/start failed: {resp.status_code} - {resp.text}"
    session = resp.json()
    session_id = session["id"]
    
    # Verify session structure
    status_correct = session.get("status") == "in_progress"
    print_test("Session status is 'in_progress'", status_correct, f"status={session.get('status')}")
    
    exercises = session.get("exercises", [])
    has_exercises = len(exercises) > 0
    print_test("Session has exercises", has_exercises, f"Count: {len(exercises)}")
    
    # Verify first exercise is in_progress, others pending
    if exercises:
        ex0_status = exercises[0].get("status")
        ex0_correct = ex0_status == "in_progress"
        print_test("Exercise 0 status is 'in_progress'", ex0_correct, f"status={ex0_status}")
        
        if len(exercises) > 1:
            other_pending = all(e.get("status") == "pending" for e in exercises[1:])
            print_test("Other exercises are 'pending'", other_pending)
    
    # Verify stats
    stats = session.get("stats", {})
    total_count = stats.get("total_count", 0)
    tonnage = stats.get("tonnage", 0)
    group = stats.get("group", "")
    
    print_test("Stats total_count is 7", total_count == 7, f"total_count={total_count}")
    print_test("Stats tonnage is 0 (no exercises done yet)", tonnage == 0, f"tonnage={tonnage}")
    print_test("Stats has group", bool(group), f"group='{group}'")
    
    # 2. Test idempotency - start again
    print("\n2. Testing idempotency (starting same session again)...")
    resp2 = requests.post(f"{BASE_URL}/sessions/start", json=session_payload)
    assert resp2.status_code == 200, f"POST sessions/start (2nd) failed: {resp2.status_code}"
    session2 = resp2.json()
    session2_id = session2["id"]
    
    same_session = session_id == session2_id
    print_test("Returns same session ID (idempotent)", same_session,
               f"First: {session_id[:8]}..., Second: {session2_id[:8]}...")
    
    # 3. Try to start session for rest day (day=3) - should fail with 400
    print("\n3. Trying to start session for rest day (day=3)...")
    rest_payload = {
        "plan_id": plan_id,
        "athlete_telegram_id": ATHLETE_ID,
        "week": 1,
        "day": 3
    }
    resp3 = requests.post(f"{BASE_URL}/sessions/start", json=rest_payload)
    rest_day_blocked = resp3.status_code == 400
    print_test("Starting session for rest day returns 400", rest_day_blocked,
               f"status_code={resp3.status_code}")
    
    # 4. Mark exercise 0 as done
    print("\n4. Marking exercise 0 as done...")
    resp = requests.patch(f"{BASE_URL}/sessions/{session_id}/exercise/0", params={"action": "done"})
    assert resp.status_code == 200, f"PATCH exercise/0 done failed: {resp.status_code}"
    session = resp.json()
    
    exercises = session.get("exercises", [])
    ex0_done = exercises[0].get("status") == "done" if exercises else False
    print_test("Exercise 0 status is 'done'", ex0_done)
    
    # Next pending (exercise 1) should become in_progress
    if len(exercises) > 1:
        ex1_in_progress = exercises[1].get("status") == "in_progress"
        print_test("Exercise 1 status is 'in_progress'", ex1_in_progress,
                   f"status={exercises[1].get('status')}")
    
    stats = session.get("stats", {})
    done_count = stats.get("done_count", 0)
    tonnage = stats.get("tonnage", 0)
    progress_pct = stats.get("progress_pct", 0)
    
    print_test("Stats done_count is 1", done_count == 1, f"done_count={done_count}")
    print_test("Stats tonnage > 0", tonnage > 0, f"tonnage={tonnage}")
    print_test("Stats progress_pct is 14 (1/7*100)", progress_pct == 14, f"progress_pct={progress_pct}")
    
    # 5. Skip exercise 1
    print("\n5. Skipping exercise 1...")
    resp = requests.patch(f"{BASE_URL}/sessions/{session_id}/exercise/1", params={"action": "skip"})
    assert resp.status_code == 200, f"PATCH exercise/1 skip failed: {resp.status_code}"
    session = resp.json()
    
    exercises = session.get("exercises", [])
    ex1_skipped = exercises[1].get("status") == "skipped" if len(exercises) > 1 else False
    print_test("Exercise 1 status is 'skipped'", ex1_skipped)
    
    # Exercise 2 should be in_progress
    if len(exercises) > 2:
        ex2_in_progress = exercises[2].get("status") == "in_progress"
        print_test("Exercise 2 status is 'in_progress'", ex2_in_progress,
                   f"status={exercises[2].get('status')}")
    
    stats = session.get("stats", {})
    skipped_count = stats.get("skipped_count", 0)
    done_count = stats.get("done_count", 0)
    
    print_test("Stats skipped_count is 1", skipped_count == 1, f"skipped_count={skipped_count}")
    print_test("Stats done_count still 1", done_count == 1, f"done_count={done_count}")
    
    # 6. Reset exercise 1
    print("\n6. Resetting exercise 1...")
    resp = requests.patch(f"{BASE_URL}/sessions/{session_id}/exercise/1", params={"action": "reset"})
    assert resp.status_code == 200, f"PATCH exercise/1 reset failed: {resp.status_code}"
    session = resp.json()
    
    exercises = session.get("exercises", [])
    ex1_pending = exercises[1].get("status") == "pending" if len(exercises) > 1 else False
    print_test("Exercise 1 status is 'pending' (reset)", ex1_pending,
               f"status={exercises[1].get('status') if len(exercises) > 1 else 'N/A'}")
    
    # 7. Mark all remaining exercises as done
    print("\n7. Marking all remaining exercises (1-6) as done...")
    for order in range(1, 7):
        resp = requests.patch(f"{BASE_URL}/sessions/{session_id}/exercise/{order}", params={"action": "done"})
        assert resp.status_code == 200, f"PATCH exercise/{order} done failed: {resp.status_code}"
    
    # Get final session state
    resp = requests.get(f"{BASE_URL}/sessions/{session_id}")
    assert resp.status_code == 200, f"GET session failed: {resp.status_code}"
    session = resp.json()
    
    # Session should auto-finish when all exercises are done/skipped
    status = session.get("status")
    finished_at = session.get("finished_at")
    auto_finished = status == "finished" and finished_at is not None
    print_test("Session auto-finished when all exercises done", auto_finished,
               f"status={status}, finished_at={finished_at is not None}")
    
    stats = session.get("stats", {})
    progress_pct = stats.get("progress_pct", 0)
    print_test("Stats progress_pct reflects done/total", progress_pct > 0,
               f"progress_pct={progress_pct}")
    
    # 8. GET session by ID
    print("\n8. Getting session by ID...")
    resp = requests.get(f"{BASE_URL}/sessions/{session_id}")
    assert resp.status_code == 200, f"GET session failed: {resp.status_code}"
    session_get = resp.json()
    
    has_stats = "stats" in session_get
    print_test("GET /sessions/{id} returns session with stats", has_stats)
    
    # 9. GET active session
    print("\n9. Getting active session...")
    params = {
        "plan_id": plan_id,
        "week": 1,
        "day": 1,
        "athlete": ATHLETE_ID
    }
    resp = requests.get(f"{BASE_URL}/sessions/active", params=params)
    assert resp.status_code == 200, f"GET active session failed: {resp.status_code}"
    active_session = resp.json()
    
    is_same = active_session is not None and active_session.get("id") == session_id
    print_test("GET /sessions/active returns same session", is_same,
               f"ID match: {is_same}")
    
    # 10. POST finish (idempotent)
    print("\n10. Calling POST /sessions/{id}/finish (idempotent)...")
    resp = requests.post(f"{BASE_URL}/sessions/{session_id}/finish")
    assert resp.status_code == 200, f"POST finish failed: {resp.status_code}"
    session = resp.json()
    
    status = session.get("status")
    print_test("Session status is 'finished'", status == "finished", f"status={status}")
    
    # 11. Pause/resume
    print("\n11. Testing pause/resume...")
    resp = requests.post(f"{BASE_URL}/sessions/{session_id}/pause", params={"resume": False})
    assert resp.status_code == 200, f"POST pause failed: {resp.status_code}"
    session = resp.json()
    
    paused = session.get("paused", False)
    print_test("Session paused=true after pause", paused, f"paused={paused}")
    
    resp = requests.post(f"{BASE_URL}/sessions/{session_id}/pause", params={"resume": True})
    assert resp.status_code == 200, f"POST resume failed: {resp.status_code}"
    session = resp.json()
    
    not_paused = not session.get("paused", True)
    print_test("Session paused=false after resume", not_paused, f"paused={session.get('paused')}")
    
    # 12. Edit exercise
    print("\n12. Testing exercise edit...")
    edit_payload = {
        "sets_scheme": [
            {"weight": 150, "sets": 2, "reps": 3}
        ]
    }
    resp = requests.patch(f"{BASE_URL}/sessions/{session_id}/exercise/0/edit", json=edit_payload)
    assert resp.status_code == 200, f"PATCH exercise/0/edit failed: {resp.status_code}"
    session = resp.json()
    
    exercises = session.get("exercises", [])
    if exercises:
        ex0 = exercises[0]
        sets_scheme = ex0.get("sets_scheme", [])
        tonnage = ex0.get("tonnage", 0)
        
        # Expected tonnage: 150 * 2 * 3 = 900
        tonnage_correct = tonnage == 900
        print_test("Exercise 0 tonnage updated to 900", tonnage_correct, f"tonnage={tonnage}")
        
        # Check percent_1rm computed (150/170 for squat ~88%)
        if sets_scheme:
            pct = sets_scheme[0].get("percent_1rm")
            has_pct = pct is not None
            print_test("Exercise 0 percent_1rm computed", has_pct, f"percent_1rm={pct}")
    
    return session_id


def test_phase2_stats(plan_id):
    """Test C: Stats + week-progress from sessions"""
    print_section("TEST C: Stats + Week Progress")
    
    # 1. GET athlete stats
    print("1. Getting athlete stats...")
    resp = requests.get(f"{BASE_URL}/stats/{ATHLETE_ID}")
    assert resp.status_code == 200, f"GET stats failed: {resp.status_code}"
    stats = resp.json()
    
    streak_days = stats.get("streak_days", 0)
    total_workouts = stats.get("total_workouts", 0)
    
    has_streak = streak_days >= 1
    print_test("Streak days >= 1 (finished session exists)", has_streak,
               f"streak_days={streak_days}, total_workouts={total_workouts}")
    
    # 2. GET week progress
    print("\n2. Getting week progress for week=1...")
    resp = requests.get(f"{BASE_URL}/plans/{plan_id}/week-progress", params={"week": 1})
    assert resp.status_code == 200, f"GET week-progress failed: {resp.status_code}"
    progress = resp.json()
    
    days = progress.get("days", [])
    has_7_days = len(days) == 7
    print_test("Week progress has 7 days", has_7_days, f"Count: {len(days)}")
    
    # Find day_index 1 (Monday - the day we did a session)
    day1 = None
    for d in days:
        if d.get("day_index") == 1:
            day1 = d
            break
    
    if day1:
        progress_pct = day1.get("progress_pct", 0)
        is_done = day1.get("is_done", False)
        has_session = day1.get("has_session", False)
        
        print_test("Day 1 has progress_pct > 0", progress_pct > 0, f"progress_pct={progress_pct}")
        print_test("Day 1 is_done=true", is_done, f"is_done={is_done}")
        print_test("Day 1 has_session=true", has_session, f"has_session={has_session}")
    else:
        print_test("Found day_index 1 in week progress", False, "Day 1 not found")
    
    # Check rest days
    day3 = None
    for d in days:
        if d.get("day_index") == 3:
            day3 = d
            break
    
    if day3:
        is_workout = day3.get("is_workout", True)
        print_test("Day 3 (rest day) is_workout=false", not is_workout, f"is_workout={is_workout}")
    else:
        print_test("Found day_index 3 in week progress", False, "Day 3 not found")


def test_data_integrity():
    """Test general data integrity requirements"""
    print_section("TEST D: Data Integrity")
    
    # Get a plan to check
    print("1. Checking UUID format and no ObjectId leaks...")
    resp = requests.get(f"{BASE_URL}/programs/templates")
    assert resp.status_code == 200
    templates = resp.json()
    
    if templates:
        t = templates[0]
        # Check ID is UUID string (not ObjectId)
        has_id = "id" in t and isinstance(t["id"], str)
        no_underscore_id = "_id" not in t
        
        print_test("Template has 'id' field (UUID string)", has_id, f"id type: {type(t.get('id'))}")
        print_test("No '_id' field (MongoDB ObjectId) leaked", no_underscore_id)
        
        # Check datetime is ISO string
        created_at = t.get("created_at")
        is_iso_string = isinstance(created_at, str)
        print_test("Datetime fields are ISO strings", is_iso_string,
                   f"created_at type: {type(created_at)}")


def main():
    print("\n" + "="*80)
    print("  TrainWithBrain Phase 2 Backend Testing")
    print("  Testing athlete: 880099")
    print("  Template: powerlifting-peaking")
    print("="*80)
    
    try:
        # Test A: Plan enrichment + %1RM
        plan_id = test_phase2_plan_enrichment()
        
        # Test B: Sessions lifecycle
        test_phase2_sessions(plan_id)
        
        # Test C: Stats + week progress
        test_phase2_stats(plan_id)
        
        # Test D: Data integrity
        test_data_integrity()
        
        print_section("ALL TESTS COMPLETED")
        print("✅ Phase 2 backend testing complete!")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
