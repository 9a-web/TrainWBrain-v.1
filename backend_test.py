"""
TrainWithBrain Phase 1 Backend Tests
Tests exercises catalog, program templates, and plans endpoints.
"""
import requests
import json
from typing import Dict, Any, List

# Backend URL - using localhost since external URL has routing issues
# External URL: https://avatar-loader-1.preview.emergentagent.com/api returns 404
BASE_URL = "http://localhost:8001/api"

# Fresh test telegram_id to avoid collisions
TEST_TELEGRAM_ID = 770001

def print_test(name: str):
    """Print test name"""
    print(f"\n{'='*80}")
    print(f"TEST: {name}")
    print('='*80)

def print_result(success: bool, message: str, response: Any = None):
    """Print test result"""
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status}: {message}")
    if response and not success:
        print(f"Response: {json.dumps(response, indent=2, ensure_ascii=False)}")

def validate_uuid(value: str, field_name: str) -> bool:
    """Validate that a value is a UUID string (not ObjectId)"""
    if not isinstance(value, str):
        print(f"❌ {field_name} is not a string: {type(value)}")
        return False
    if len(value) != 36 or value.count('-') != 4:
        print(f"❌ {field_name} is not a valid UUID format: {value}")
        return False
    return True

def validate_datetime(value: str, field_name: str) -> bool:
    """Validate that a value is an ISO datetime string"""
    if not isinstance(value, str):
        print(f"❌ {field_name} is not a string: {type(value)}")
        return False
    # Basic ISO format check (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
    if 'T' in value or len(value) >= 10:
        return True
    print(f"❌ {field_name} is not a valid ISO datetime: {value}")
    return False

# ===========================================================================
# PHASE 1 TESTS
# ===========================================================================

def test_exercises_catalog():
    """Test 1: Exercises catalog endpoints"""
    
    # 1.1: GET /api/exercises → must return exactly 24 built-in exercises
    print_test("1.1: GET /api/exercises - List all built-in exercises")
    response = requests.get(f"{BASE_URL}/exercises")
    
    if response.status_code != 200:
        print_result(False, f"Expected status 200, got {response.status_code}", response.json())
        return False
    
    exercises = response.json()
    if len(exercises) != 24:
        print_result(False, f"Expected exactly 24 exercises, got {len(exercises)}", exercises)
        return False
    
    # Validate first exercise structure
    ex = exercises[0]
    checks = [
        ('id' in ex, "Exercise has 'id' field"),
        (validate_uuid(ex.get('id', ''), 'id'), "Exercise id is UUID"),
        ('slug' in ex, "Exercise has 'slug' field"),
        ('name' in ex, "Exercise has 'name' field"),
        ('muscle_groups' in ex, "Exercise has 'muscle_groups' field"),
        (isinstance(ex.get('muscle_groups', None), list), "muscle_groups is a list"),
        (ex.get('is_builtin') == True, "Exercise is_builtin=true"),
        ('_id' not in ex, "No MongoDB _id field leaked"),
    ]
    
    all_passed = all(check[0] for check in checks)
    for passed, msg in checks:
        print_result(passed, msg)
    
    if not all_passed:
        print(f"Sample exercise: {json.dumps(ex, indent=2, ensure_ascii=False)}")
        return False
    
    print_result(True, f"All 24 built-in exercises returned with correct structure")
    
    # 1.2: GET /api/exercises?query=жим → name filter (case-insensitive)
    print_test("1.2: GET /api/exercises?query=жим - Filter by name")
    response = requests.get(f"{BASE_URL}/exercises", params={"query": "жим"})
    
    if response.status_code != 200:
        print_result(False, f"Expected status 200, got {response.status_code}", response.json())
        return False
    
    filtered = response.json()
    if len(filtered) == 0:
        print_result(False, "Expected at least 1 exercise with 'жим' in name", filtered)
        return False
    
    # Check that all returned exercises have 'жим' in name (case-insensitive)
    all_match = all('жим' in ex['name'].lower() for ex in filtered)
    if not all_match:
        print_result(False, "Not all exercises contain 'жим' in name", filtered)
        return False
    
    print_result(True, f"Found {len(filtered)} exercises with 'жим' in name")
    
    # 1.3: GET /api/exercises?muscle=chest → filter by muscle group
    print_test("1.3: GET /api/exercises?muscle=chest - Filter by muscle group")
    response = requests.get(f"{BASE_URL}/exercises", params={"muscle": "chest"})
    
    if response.status_code != 200:
        print_result(False, f"Expected status 200, got {response.status_code}", response.json())
        return False
    
    chest_exercises = response.json()
    if len(chest_exercises) == 0:
        print_result(False, "Expected at least 1 exercise with 'chest' muscle group", chest_exercises)
        return False
    
    # Check that all returned exercises have 'chest' in muscle_groups
    all_match = all('chest' in ex['muscle_groups'] for ex in chest_exercises)
    if not all_match:
        print_result(False, "Not all exercises contain 'chest' in muscle_groups", chest_exercises)
        return False
    
    print_result(True, f"Found {len(chest_exercises)} exercises with 'chest' muscle group")
    
    # 1.4: POST /api/exercises - Create custom exercise
    print_test("1.4: POST /api/exercises - Create custom exercise")
    custom_exercise = {
        "name": "Тест-упражнение",
        "muscle_groups": ["chest"],
        "equipment": "barbell",
        "category": "compound",
        "owner_telegram_id": TEST_TELEGRAM_ID
    }
    response = requests.post(f"{BASE_URL}/exercises", json=custom_exercise)
    
    if response.status_code != 200:
        print_result(False, f"Expected status 200, got {response.status_code}", response.json())
        return False
    
    created = response.json()
    checks = [
        ('id' in created, "Created exercise has 'id' field"),
        (validate_uuid(created.get('id', ''), 'id'), "Created exercise id is UUID"),
        (created.get('name') == "Тест-упражнение", "Name matches"),
        (created.get('muscle_groups') == ["chest"], "Muscle groups match"),
        (created.get('is_builtin') == False, "is_builtin=false for custom exercise"),
        (created.get('owner_telegram_id') == TEST_TELEGRAM_ID, "owner_telegram_id matches"),
        ('_id' not in created, "No MongoDB _id field leaked"),
    ]
    
    all_passed = all(check[0] for check in checks)
    for passed, msg in checks:
        print_result(passed, msg)
    
    if not all_passed:
        print(f"Created exercise: {json.dumps(created, indent=2, ensure_ascii=False)}")
        return False
    
    print_result(True, "Custom exercise created successfully")
    return True


def test_program_templates():
    """Test 2: Program templates endpoints"""
    
    # 2.1: GET /api/programs/templates → must return exactly 3 built-in templates
    print_test("2.1: GET /api/programs/templates - List all built-in templates")
    response = requests.get(f"{BASE_URL}/programs/templates")
    
    if response.status_code != 200:
        print_result(False, f"Expected status 200, got {response.status_code}", response.json())
        return False
    
    templates = response.json()
    if len(templates) != 3:
        print_result(False, f"Expected exactly 3 templates, got {len(templates)}", templates)
        return False
    
    # Validate template names and weeks_count
    expected_templates = {
        "Full Body для новичка": 4,
        "Upper/Lower (гипертрофия)": 4,
        "Powerlifting Peaking": 3
    }
    
    found_templates = {t['name']: t['weeks_count'] for t in templates}
    
    for name, weeks in expected_templates.items():
        if name not in found_templates:
            print_result(False, f"Expected template '{name}' not found", found_templates)
            return False
        if found_templates[name] != weeks:
            print_result(False, f"Template '{name}' expected {weeks} weeks, got {found_templates[name]}")
            return False
        print_result(True, f"Found template '{name}' with {weeks} weeks")
    
    # Validate first template structure
    tpl = templates[0]
    checks = [
        ('id' in tpl, "Template has 'id' field"),
        (validate_uuid(tpl.get('id', ''), 'id'), "Template id is UUID"),
        ('name' in tpl, "Template has 'name' field"),
        ('weeks_count' in tpl, "Template has 'weeks_count' field"),
        (tpl.get('is_builtin') == True, "Template is_builtin=true"),
        ('_id' not in tpl, "No MongoDB _id field leaked"),
    ]
    
    all_passed = all(check[0] for check in checks)
    for passed, msg in checks:
        print_result(passed, msg)
    
    if not all_passed:
        return False
    
    # Store template IDs for later tests
    global FULL_BODY_TEMPLATE_ID, UPPER_LOWER_TEMPLATE_ID
    FULL_BODY_TEMPLATE_ID = next(t['id'] for t in templates if t['name'] == "Full Body для новичка")
    UPPER_LOWER_TEMPLATE_ID = next(t['id'] for t in templates if t['name'] == "Upper/Lower (гипертрофия)")
    
    print_result(True, "All 3 built-in templates returned with correct structure")
    
    # 2.2: GET /api/programs/templates/{id} - Get template detail
    print_test("2.2: GET /api/programs/templates/{id} - Get Full Body template detail")
    response = requests.get(f"{BASE_URL}/programs/templates/{FULL_BODY_TEMPLATE_ID}")
    
    if response.status_code != 200:
        print_result(False, f"Expected status 200, got {response.status_code}", response.json())
        return False
    
    detail = response.json()
    checks = [
        ('weeks' in detail, "Template has 'weeks' field"),
        (isinstance(detail.get('weeks'), list), "weeks is a list"),
        (len(detail.get('weeks', [])) == 4, "Full Body has 4 weeks"),
        (len(detail['weeks'][0].get('days', [])) > 0, "Week 1 has days"),
        (len(detail['weeks'][0]['days'][0].get('exercises', [])) > 0, "Day 1 has exercises"),
    ]
    
    all_passed = all(check[0] for check in checks)
    for passed, msg in checks:
        print_result(passed, msg)
    
    if not all_passed:
        print(f"Template detail: {json.dumps(detail, indent=2, ensure_ascii=False)[:500]}")
        return False
    
    # Validate exercise structure
    ex = detail['weeks'][0]['days'][0]['exercises'][0]
    ex_checks = [
        ('exercise_name' in ex, "Exercise has 'exercise_name' field"),
        ('target_sets' in ex, "Exercise has 'target_sets' field"),
        ('target_reps' in ex, "Exercise has 'target_reps' field"),
    ]
    
    all_passed = all(check[0] for check in ex_checks)
    for passed, msg in ex_checks:
        print_result(passed, msg)
    
    if not all_passed:
        return False
    
    print_result(True, "Template detail returned with full weeks->days->exercises structure")
    
    # 2.3: GET /api/programs/templates/{bad_id} - 404 for non-existent template
    print_test("2.3: GET /api/programs/templates/{bad_id} - 404 for non-existent template")
    bad_id = "00000000-0000-0000-0000-000000000000"
    response = requests.get(f"{BASE_URL}/programs/templates/{bad_id}")
    
    if response.status_code != 404:
        print_result(False, f"Expected status 404, got {response.status_code}", response.json())
        return False
    
    print_result(True, "Returns 404 for non-existent template")
    
    # 2.4: POST /api/programs/templates - Create custom template
    print_test("2.4: POST /api/programs/templates - Create custom template")
    custom_template = {
        "name": "Тестовая программа",
        "level": "beginner",
        "goal": "strength",
        "days_per_week": 1,
        "weeks": [
            {
                "week_index": 1,
                "days": [
                    {
                        "day_index": 1,
                        "title": "D1",
                        "is_rest": False,
                        "exercises": [
                            {
                                "exercise_name": "Жим лёжа",
                                "target_sets": 3,
                                "target_reps": "5"
                            }
                        ]
                    }
                ]
            }
        ],
        "owner_telegram_id": TEST_TELEGRAM_ID
    }
    response = requests.post(f"{BASE_URL}/programs/templates", json=custom_template)
    
    if response.status_code != 200:
        print_result(False, f"Expected status 200, got {response.status_code}", response.json())
        return False
    
    created = response.json()
    checks = [
        ('id' in created, "Created template has 'id' field"),
        (validate_uuid(created.get('id', ''), 'id'), "Created template id is UUID"),
        (created.get('name') == "Тестовая программа", "Name matches"),
        (created.get('weeks_count') == 1, "weeks_count=1"),
        (created.get('is_builtin') == False, "is_builtin=false for custom template"),
        (created.get('owner_telegram_id') == TEST_TELEGRAM_ID, "owner_telegram_id matches"),
        ('_id' not in created, "No MongoDB _id field leaked"),
    ]
    
    all_passed = all(check[0] for check in checks)
    for passed, msg in checks:
        print_result(passed, msg)
    
    if not all_passed:
        print(f"Created template: {json.dumps(created, indent=2, ensure_ascii=False)}")
        return False
    
    print_result(True, "Custom template created successfully")
    return True


def test_plans():
    """Test 3: Plans endpoints"""
    
    # 3.1: POST /api/plans - Create plan from Full Body template
    print_test("3.1: POST /api/plans - Create plan from Full Body template")
    plan_data = {
        "athlete_telegram_id": TEST_TELEGRAM_ID,
        "template_id": FULL_BODY_TEMPLATE_ID
    }
    response = requests.post(f"{BASE_URL}/plans", json=plan_data)
    
    if response.status_code != 200:
        print_result(False, f"Expected status 200, got {response.status_code}", response.json())
        return False
    
    plan = response.json()
    checks = [
        ('id' in plan, "Plan has 'id' field"),
        (validate_uuid(plan.get('id', ''), 'id'), "Plan id is UUID"),
        (plan.get('status') == 'active', "Plan status='active'"),
        (plan.get('name') == "Full Body для новичка", "Plan name from template"),
        ('weeks' in plan, "Plan has 'weeks' field (snapshot)"),
        (len(plan.get('weeks', [])) == 4, "Plan has 4 weeks (snapshot from template)"),
        (plan.get('athlete_telegram_id') == TEST_TELEGRAM_ID, "athlete_telegram_id matches"),
        ('_id' not in plan, "No MongoDB _id field leaked"),
    ]
    
    all_passed = all(check[0] for check in checks)
    for passed, msg in checks:
        print_result(passed, msg)
    
    if not all_passed:
        print(f"Created plan: {json.dumps(plan, indent=2, ensure_ascii=False)[:500]}")
        return False
    
    global FIRST_PLAN_ID
    FIRST_PLAN_ID = plan['id']
    print_result(True, f"Plan created successfully with id={FIRST_PLAN_ID}")
    
    # 3.2: GET /api/plans/active/{telegram_id} - Get active plan
    print_test("3.2: GET /api/plans/active/{telegram_id} - Get active plan")
    response = requests.get(f"{BASE_URL}/plans/active/{TEST_TELEGRAM_ID}")
    
    if response.status_code != 200:
        print_result(False, f"Expected status 200, got {response.status_code}", response.json())
        return False
    
    active_plan = response.json()
    if active_plan.get('id') != FIRST_PLAN_ID:
        print_result(False, f"Expected active plan id={FIRST_PLAN_ID}, got {active_plan.get('id')}", active_plan)
        return False
    
    print_result(True, f"Active plan returned correctly (id={FIRST_PLAN_ID})")
    
    # 3.3: Create SECOND plan - first plan should become inactive
    print_test("3.3: POST /api/plans - Create second plan (first should become inactive)")
    plan_data2 = {
        "athlete_telegram_id": TEST_TELEGRAM_ID,
        "template_id": UPPER_LOWER_TEMPLATE_ID
    }
    response = requests.post(f"{BASE_URL}/plans", json=plan_data2)
    
    if response.status_code != 200:
        print_result(False, f"Expected status 200, got {response.status_code}", response.json())
        return False
    
    plan2 = response.json()
    global SECOND_PLAN_ID
    SECOND_PLAN_ID = plan2['id']
    
    if plan2.get('status') != 'active':
        print_result(False, f"Second plan should be active, got status={plan2.get('status')}", plan2)
        return False
    
    print_result(True, f"Second plan created with id={SECOND_PLAN_ID}")
    
    # 3.4: Verify GET /api/plans/active/{telegram_id} now returns SECOND plan
    print_test("3.4: GET /api/plans/active/{telegram_id} - Should return second plan")
    response = requests.get(f"{BASE_URL}/plans/active/{TEST_TELEGRAM_ID}")
    
    if response.status_code != 200:
        print_result(False, f"Expected status 200, got {response.status_code}", response.json())
        return False
    
    active_plan = response.json()
    if active_plan.get('id') != SECOND_PLAN_ID:
        print_result(False, f"Expected active plan id={SECOND_PLAN_ID}, got {active_plan.get('id')}", active_plan)
        return False
    
    print_result(True, f"Active plan now returns second plan (id={SECOND_PLAN_ID})")
    
    # 3.5: GET /api/plans/{id} - Get plan by ID
    print_test("3.5: GET /api/plans/{id} - Get plan by ID")
    response = requests.get(f"{BASE_URL}/plans/{FIRST_PLAN_ID}")
    
    if response.status_code != 200:
        print_result(False, f"Expected status 200, got {response.status_code}", response.json())
        return False
    
    plan_detail = response.json()
    if plan_detail.get('id') != FIRST_PLAN_ID:
        print_result(False, f"Expected plan id={FIRST_PLAN_ID}, got {plan_detail.get('id')}", plan_detail)
        return False
    
    print_result(True, f"Plan detail returned correctly")
    
    # 3.6: GET /api/plans/{bad_id} - 404 for non-existent plan
    print_test("3.6: GET /api/plans/{bad_id} - 404 for non-existent plan")
    bad_id = "00000000-0000-0000-0000-000000000000"
    response = requests.get(f"{BASE_URL}/plans/{bad_id}")
    
    if response.status_code != 404:
        print_result(False, f"Expected status 404, got {response.status_code}", response.json())
        return False
    
    print_result(True, "Returns 404 for non-existent plan")
    
    # 3.7: GET /api/plans/{id}/day?week=1&day=1 - Get workout day
    print_test("3.7: GET /api/plans/{id}/day?week=1&day=1 - Get workout day (Full Body Mon)")
    response = requests.get(f"{BASE_URL}/plans/{FIRST_PLAN_ID}/day", params={"week": 1, "day": 1})
    
    if response.status_code != 200:
        print_result(False, f"Expected status 200, got {response.status_code}", response.json())
        return False
    
    day = response.json()
    checks = [
        ('day_index' in day, "Day has 'day_index' field"),
        (day.get('day_index') == 1, "day_index=1"),
        ('is_rest' in day, "Day has 'is_rest' field"),
        (day.get('is_rest') == False, "is_rest=false (workout day)"),
        ('exercises' in day, "Day has 'exercises' field"),
        (len(day.get('exercises', [])) > 0, "Day has exercises"),
    ]
    
    all_passed = all(check[0] for check in checks)
    for passed, msg in checks:
        print_result(passed, msg)
    
    if not all_passed:
        print(f"Day detail: {json.dumps(day, indent=2, ensure_ascii=False)}")
        return False
    
    # Validate exercise structure
    ex = day['exercises'][0]
    ex_checks = [
        ('exercise_name' in ex, "Exercise has 'exercise_name' field"),
        ('target_sets' in ex, "Exercise has 'target_sets' field"),
        ('target_reps' in ex, "Exercise has 'target_reps' field"),
    ]
    
    all_passed = all(check[0] for check in ex_checks)
    for passed, msg in ex_checks:
        print_result(passed, msg)
    
    if not all_passed:
        return False
    
    print_result(True, f"Workout day returned with {len(day['exercises'])} exercises")
    
    # 3.8: GET /api/plans/{id}/day?week=1&day=2 - Get rest day
    print_test("3.8: GET /api/plans/{id}/day?week=1&day=2 - Get rest day (Full Body Tue)")
    response = requests.get(f"{BASE_URL}/plans/{FIRST_PLAN_ID}/day", params={"week": 1, "day": 2})
    
    if response.status_code != 200:
        print_result(False, f"Expected status 200, got {response.status_code}", response.json())
        return False
    
    rest_day = response.json()
    checks = [
        (rest_day.get('is_rest') == True, "is_rest=true"),
        (len(rest_day.get('exercises', [])) == 0, "exercises is empty"),
    ]
    
    all_passed = all(check[0] for check in checks)
    for passed, msg in checks:
        print_result(passed, msg)
    
    if not all_passed:
        print(f"Rest day: {json.dumps(rest_day, indent=2, ensure_ascii=False)}")
        return False
    
    print_result(True, "Rest day returned correctly")
    
    # 3.9: GET /api/plans/{id}/week-progress?week=1 - Get week progress
    print_test("3.9: GET /api/plans/{id}/week-progress?week=1 - Get week progress")
    response = requests.get(f"{BASE_URL}/plans/{FIRST_PLAN_ID}/week-progress", params={"week": 1})
    
    if response.status_code != 200:
        print_result(False, f"Expected status 200, got {response.status_code}", response.json())
        return False
    
    progress = response.json()
    checks = [
        ('days' in progress, "Progress has 'days' field"),
        (len(progress.get('days', [])) == 7, "Progress has 7 days (Mon-Sun)"),
    ]
    
    all_passed = all(check[0] for check in checks)
    for passed, msg in checks:
        print_result(passed, msg)
    
    if not all_passed:
        print(f"Week progress: {json.dumps(progress, indent=2, ensure_ascii=False)}")
        return False
    
    # Validate day structure and Full Body schedule (Mon/Wed/Fri workouts)
    days = progress['days']
    expected_workouts = {1: True, 2: False, 3: True, 4: False, 5: True, 6: False, 7: False}
    
    for day in days:
        day_idx = day.get('day_index')
        is_workout = day.get('is_workout')
        expected = expected_workouts.get(day_idx)
        
        if is_workout != expected:
            print_result(False, f"Day {day_idx}: expected is_workout={expected}, got {is_workout}", day)
            return False
        
        if is_workout:
            if day.get('planned_sets', 0) <= 0:
                print_result(False, f"Day {day_idx}: workout day should have planned_sets>0", day)
                return False
            print_result(True, f"Day {day_idx} (workout): planned_sets={day.get('planned_sets')}")
        else:
            print_result(True, f"Day {day_idx} (rest)")
    
    print_result(True, "Week progress returned correctly with 7 days and correct workout schedule")
    
    # 3.10: POST /api/plans with NO template_id and NO weeks - expect 400
    print_test("3.10: POST /api/plans - No template_id and no weeks (expect 400)")
    invalid_plan = {
        "athlete_telegram_id": TEST_TELEGRAM_ID
    }
    response = requests.post(f"{BASE_URL}/plans", json=invalid_plan)
    
    if response.status_code != 400:
        print_result(False, f"Expected status 400, got {response.status_code}", response.json())
        return False
    
    print_result(True, "Returns 400 when neither template_id nor weeks provided")
    
    return True


def test_idempotency():
    """Test 4: Verify idempotent seed (counts should remain stable)"""
    print_test("4: Verify idempotent seed - counts should remain 24 exercises / 3 templates")
    
    # Check exercises count
    response = requests.get(f"{BASE_URL}/exercises")
    if response.status_code != 200:
        print_result(False, f"Failed to get exercises: {response.status_code}")
        return False
    
    exercises = response.json()
    builtin_exercises = [ex for ex in exercises if ex.get('is_builtin') == True]
    
    if len(builtin_exercises) != 24:
        print_result(False, f"Expected 24 built-in exercises, got {len(builtin_exercises)}")
        return False
    
    print_result(True, f"Built-in exercises count stable: {len(builtin_exercises)}")
    
    # Check templates count
    response = requests.get(f"{BASE_URL}/programs/templates")
    if response.status_code != 200:
        print_result(False, f"Failed to get templates: {response.status_code}")
        return False
    
    templates = response.json()
    builtin_templates = [tpl for tpl in templates if tpl.get('is_builtin') == True]
    
    if len(builtin_templates) != 3:
        print_result(False, f"Expected 3 built-in templates, got {len(builtin_templates)}")
        return False
    
    print_result(True, f"Built-in templates count stable: {len(builtin_templates)}")
    
    return True


# ===========================================================================
# MAIN TEST RUNNER
# ===========================================================================

def main():
    print("\n" + "="*80)
    print("TrainWithBrain Phase 1 Backend Tests")
    print(f"Backend URL: {BASE_URL}")
    print(f"Test Telegram ID: {TEST_TELEGRAM_ID}")
    print("="*80)
    
    results = {}
    
    # Run tests
    results['Exercises Catalog'] = test_exercises_catalog()
    results['Program Templates'] = test_program_templates()
    results['Plans'] = test_plans()
    results['Idempotency'] = test_idempotency()
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    all_passed = all(results.values())
    print("\n" + "="*80)
    if all_passed:
        print("✅ ALL TESTS PASSED")
    else:
        print("❌ SOME TESTS FAILED")
    print("="*80)
    
    return all_passed


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
