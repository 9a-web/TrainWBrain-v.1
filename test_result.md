#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

# THIS SECTION CONTAINS CRITICAL TESTING INSTRUCTIONS FOR BOTH AGENTS
# BOTH MAIN_AGENT AND TESTING_AGENT MUST PRESERVE THIS ENTIRE BLOCK

# Communication Protocol:
# If the `testing_agent` is available, main agent should delegate all testing tasks to it.
#
# You have access to a file called `test_result.md`. This file contains the complete testing state
# and history, and is the primary means of communication between main and the testing agent.
#
# Main and testing agents must follow this exact format to maintain testing data. 
# The testing data must be entered in yaml format Below is the data structure:
# 
## user_problem_statement: {problem_statement}
## backend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.py"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## frontend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.js"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## metadata:
##   created_by: "main_agent"
##   version: "1.0"
##   test_sequence: 0
##   run_ui: false
##
## test_plan:
##   current_focus:
##     - "Task name 1"
##     - "Task name 2"
##   stuck_tasks:
##     - "Task name with persistent issues"
##   test_all: false
##   test_priority: "high_first"  # or "sequential" or "stuck_first"
##
## agent_communication:
##     -agent: "main"  # or "testing" or "user"
##     -message: "Communication message between agents"

# Protocol Guidelines for Main agent
#
# 1. Update Test Result File Before Testing:
#    - Main agent must always update the `test_result.md` file before calling the testing agent
#    - Add implementation details to the status_history
#    - Set `needs_retesting` to true for tasks that need testing
#    - Update the `test_plan` section to guide testing priorities
#    - Add a message to `agent_communication` explaining what you've done
#
# 2. Incorporate User Feedback:
#    - When a user provides feedback that something is or isn't working, add this information to the relevant task's status_history
#    - Update the working status based on user feedback
#    - If a user reports an issue with a task that was marked as working, increment the stuck_count
#    - Whenever user reports issue in the app, if we have testing agent and task_result.md file so find the appropriate task for that and append in status_history of that task to contain the user concern and problem as well 
#
# 3. Track Stuck Tasks:
#    - Monitor which tasks have high stuck_count values or where you are fixing same issue again and again, analyze that when you read task_result.md
#    - For persistent issues, use websearch tool to find solutions
#    - Pay special attention to tasks in the stuck_tasks list
#    - When you fix an issue with a stuck task, don't reset the stuck_count until the testing agent confirms it's working
#
# 4. Provide Context to Testing Agent:
#    - When calling the testing agent, provide clear instructions about:
#      - Which tasks need testing (reference the test_plan)
#      - Any authentication details or configuration needed
#      - Specific test scenarios to focus on
#      - Any known issues or edge cases to verify
#
# 5. Call the testing agent with specific instructions referring to test_result.md
#
# IMPORTANT: Main agent must ALWAYS update test_result.md BEFORE calling the testing agent, as it relies on this file to understand what to test next.

#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================



#====================================================================================================
# Testing Data - Main Agent and testing sub agent both should log testing data below this section
#====================================================================================================

user_problem_statement: "TrainWithBrain Telegram WebApp - при открытии приложения в Telegram аватарка не подгружается. Нужно проверить создание пользователя в БД и работу с UID"

backend:
  - task: "P3 Coach: role/mode switch (PATCH /api/users/{telegram_id}/mode)"
    implemented: true
    working: true
    file: "backend/server.py, backend/models.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "PATCH /api/users/{telegram_id}/mode {mode: athlete|coach}. Validates mode (else 400). 404 if user missing. Switching to coach adds 'coach' to roles[] (always keeps 'athlete'), sets active_mode, and generates a unique invite_code if absent. Returns updated user (no password_hash). Smoke-tested via curl: roles=['athlete','coach'], invite_code generated."
      - working: true
        agent: "testing"
        comment: "✅ TESTED: All 4 mode switch scenarios passed. (1) SWITCH TO COACH: PATCH /api/users/701001/mode {mode:coach} returns 200, roles include both 'athlete' and 'coach', active_mode='coach', invite_code present (8 chars). (2) INVALID MODE: mode='bad' returns 400. (3) UNKNOWN USER: telegram_id=999999 returns 404. (4) SWITCH BACK: mode='athlete' keeps coach role, active_mode='athlete'. All responses valid JSON, no _id leaks, ISO datetimes."

  - task: "P3 Coach: invite + link + unlink + clients + client plan + athlete coach"
    implemented: true
    working: true
    file: "backend/server.py, backend/models.py, backend/seed.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "New endpoints: POST /api/coach/invite {coach_telegram_id} -> {invite_code, deep_link, bot_username} (adds coach role, stable code). POST /api/coach/link {code, athlete_telegram_id} -> links athlete to coach (status active), sets user.coach_telegram_id; 404 unknown code; 400 self-link; coach_links upsert unique (coach,athlete). POST /api/coach/unlink {athlete_telegram_id} -> revokes link, clears coach_telegram_id. GET /api/coach/{telegram_id}/clients -> [{athlete brief, plan summary, is_training_now, active_session_id, last_workout_at, linked_at}]. GET /api/coach/{telegram_id}/clients/{athlete_id}/plan -> active plan (full, even draft); 403 if not coach of athlete. GET /api/athlete/{telegram_id}/coach -> {coach brief|null}. Smoke-tested via curl end-to-end OK."
      - working: true
        agent: "testing"
        comment: "✅ TESTED: All 11 scenarios passed. (1) INVITE: POST /api/coach/invite returns {invite_code, deep_link, bot_username}. (2) STABLE CODE: Second call returns SAME invite_code. (3) LINK: POST /api/coach/link with valid code links athlete 701002 to coach 701001, returns status='active' and coach brief. (4) UNKNOWN CODE: Invalid code returns 404. (5) SELF-LINK: Linking to self returns 400. (6) ATHLETE COACH: GET /api/athlete/701002/coach returns coach 701001. (7) COACH NO COACH: GET /api/athlete/701001/coach returns null. (8) CLIENTS LIST: GET /api/coach/701001/clients includes athlete 701002 with plan summary, is_training_now, last_workout_at, linked_at. (9) CLIENT PLAN: GET /api/coach/701001/clients/701002/plan returns full plan (even draft). (10) UNLINKED COACH: Unlinked coach 701003 calling endpoint returns 403. (11) UNLINK: POST /api/coach/unlink removes athlete from clients list, GET /api/athlete/701002/coach returns null. All responses valid JSON, UUIDs only, ISO datetimes, no _id leaks."

  - task: "P3 Plan visibility draft/published (+ active plan draft hiding)"
    implemented: true
    working: true
    file: "backend/server.py, backend/models.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "Plan model += visibility(draft|published, default published), published_at, prepared_by_coach. POST /api/plans: when coach_telegram_id != athlete_telegram_id -> visibility defaults to 'draft' & prepared_by_coach=true; self-created -> published; explicit visibility honored. PATCH /api/plans/{id}/visibility {visibility} validates value, sets published_at on first publish. GET /api/plans/active/{telegram_id}: for draft plan returns the plan WITH weeks=[] (content hidden, 'план готовится'); published returns full weeks. Backward compat: existing plans (no visibility field) read as 'published'. Smoke-tested: draft hides weeks, publish reveals them."
      - working: true
        agent: "testing"
        comment: "✅ TESTED: All 7 scenarios passed. (1) COACH CREATES DRAFT: POST /api/plans with coach_telegram_id != athlete_telegram_id creates plan with visibility='draft', prepared_by_coach=true, weeks non-empty. (2) ATHLETE SEES HIDDEN: GET /api/plans/active/701002 returns draft plan with weeks=[] (content hidden). (3) COACH SEES FULL: GET /api/coach/701001/clients/701002/plan returns full weeks (coach can see draft content). (4) UNLINKED COACH 403: Unlinked coach 701003 calling endpoint returns 403. (5) PUBLISH: PATCH /api/plans/{id}/visibility {visibility:published} sets visibility='published', published_at timestamp. (6) ATHLETE SEES FULL: GET /api/plans/active/701002 now returns full weeks. (7) INVALID VISIBILITY: Invalid value returns 400. (8) SELF-PLAN PUBLISHED: POST /api/plans without coach_telegram_id creates plan with visibility='published' (backward compatible). All responses valid JSON, UUIDs only, ISO datetimes, no _id leaks."

  - task: "P3 Plan: week publish toggle + training-days (coach controls)"
    implemented: true
    working: true
    file: "backend/server.py, backend/models.py"
    stuck_count: 0
    priority: "medium"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "ProgramWeek model += published(bool, default true). PATCH /api/plans/{id}/weeks/{week}/publish {published} toggles that week's published flag (404 if week not found). PATCH /api/plans/{id}/training-days {training_days:[1..7]} validates range (400 otherwise), stores sorted unique. Both return full updated plan. Smoke-tested: week1.published=false, training_days=[1,3,5]."
      - working: true
        agent: "testing"
        comment: "✅ TESTED: All 4 scenarios passed. (1) UNPUBLISH WEEK: PATCH /api/plans/{id}/weeks/1/publish {published:false} sets week 1 published=false. (2) NONEXISTENT WEEK: Week 99 returns 404. (3) SET TRAINING DAYS: PATCH /api/plans/{id}/training-days {training_days:[1,3,5]} stores sorted [1,3,5]. (4) OUT-OF-RANGE: Days [0,8] return 400. All responses valid JSON, UUIDs only, ISO datetimes, no _id leaks."

  - task: "P3 Coach: confirm workout session (POST /api/sessions/{id}/confirm)"
    implemented: true
    working: true
    file: "backend/server.py"
    stuck_count: 0
    priority: "medium"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "POST /api/sessions/{id}/confirm {coach_telegram_id?} sets session coach_confirmed=true, confirmed_by, confirmed_at. If coach_telegram_id provided, asserts coach is linked to the session's athlete (403 otherwise). 404 if session missing. Returns serialized session with stats."
      - working: true
        agent: "testing"
        comment: "✅ TESTED: All 3 scenarios passed. (1) COACH CONFIRMS: POST /api/sessions/{id}/confirm {coach_telegram_id:701001} on linked athlete's session sets coach_confirmed=true, confirmed_by=701001, confirmed_at timestamp. (2) NONLINKED COACH: Coach 701003 (not linked to athlete) returns 403. (3) MISSING SESSION: Invalid session_id returns 404. All responses valid JSON, UUIDs only, ISO datetimes, no _id leaks."

  - task: "Plan editor (coach): meta/day/exercise/week CRUD endpoints"
    implemented: true
    working: true
    file: "backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "New plan-editor endpoints (snapshot weeks editing; %1RM/tonnage computed on read via GET /plans/{id}/day): (1) PATCH /api/plans/{id} {name?, current_week?, start_date?} renames/updates plan meta. (2) PUT /api/plans/{id}/day {week,day(1..7),title?,is_rest?} upserts a weekday in a week (creates if missing, else edits title/is_rest); 404 if week missing; 400 if day out of 1..7. (3) DELETE /api/plans/{id}/day?week=&day= removes a day (404 if not found). (4) PUT /api/plans/{id}/exercise {week,day,order?,exercise_name,muscle_group,difficulty,is_accessory,weight_type,target_reps,target_rpe,rest_seconds,notes,sets_scheme:[{weight,sets,reps}],exercise_slug,lift_group}: order given -> edit at that index; order omitted -> append; reindexes orders; normalizes sets (sets>=1,reps>=0); target_sets=sum(sets), target_weight=first set weight; 404 if week/day missing. (5) DELETE /api/plans/{id}/exercise?week=&day=&order= removes + reindexes (404 if order out of range). (6) POST /api/plans/{id}/week appends empty week with next week_index (published=true). (7) DELETE /api/plans/{id}/week?week= removes week, REINDEXES remaining week_index to 1..N, clamps current_week. Smoke-tested via curl: rename, add week (idx5), add day2, add/edit exercise (tonnage 1880 = 160*1*3+140*2*5 on day view), delete exercise/day/week+reindex all OK. NOTE: known limitation — deleting a middle week reindexes later weeks, which may shift week_index of past sessions (acceptable; editing is pre-start usually)."
      - working: true
        agent: "testing"
        comment: "✅ TESTED: All 18 plan editor endpoint tests passed. Created plan from template (4 weeks) for athlete 734001. (1) PATCH /api/plans/{id}: Successfully updated name to 'Custom' and current_week to 2. (2) POST /api/plans/{id}/week: Added week, weeks count increased from 4 to 5, new week has week_index=5, published=true, days=[]. (3) PUT /api/plans/{id}/day: Added day (week=1, day=2, title='День тяги', is_rest=false). Repeated call updated title in place (no duplicate). Invalid day=8 returns 400. Nonexistent week=99 returns 404. (4) PUT /api/plans/{id}/exercise: Added exercise 'Становая' with sets_scheme [{weight:150, sets:3, reps:5}], target_sets=3, target_weight=150. Edited at order=0 with 2 sets [{160,1,3},{140,2,5}], target_sets=3 (1+2). GET /api/plans/{id}/day?week=1&day=2 returns exercises[0].tonnage=1880 (160*1*3+140*2*5), sets_scheme entries have percent_1rm key. Missing week/day returns 404. (5) DELETE /api/plans/{id}/exercise: Removed exercise at order=0. Out-of-range order returns 404. (6) DELETE /api/plans/{id}/day: Removed day (week=1, day=2). Missing day returns 404. (7) DELETE /api/plans/{id}/week: Deleted week 5, weeks count decreased from 5 to 4, remaining weeks reindexed contiguously 1..4. Nonexistent week returns 404. All responses valid JSON, UUIDs only, ISO datetimes, no _id leaks."



  - task: "Auth: Email register/login (JWT-less session tokens, bcrypt)"
    implemented: true
    working: true
    file: "server.py, auth.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "POST /api/auth/register {email,password,name} creates account with synthetic telegram_id (range 900000000000+), bcrypt password_hash (never returned), returns {token,user} + sets httpOnly cookie. POST /api/auth/login verifies password. Duplicate email -> 400, weak password (<6) -> 400, wrong creds -> 401. Smoke-tested OK on localhost."
      - working: true
        agent: "testing"
        comment: "✅ TESTED: All email auth scenarios passed (7 tests). (1) REGISTER SUCCESS: POST /api/auth/register creates user with synthetic telegram_id=950454640997 (>=900000000000), returns {token,user} with UUID id (36 chars), email in auth_provider, NO password_hash in response. (2) WEAK PASSWORD: password <6 chars rejected with 400. (3) INVALID EMAIL: emails without @ or without domain dot rejected with 400. (4) DUPLICATE EMAIL: registering same email twice rejected with 400. (5) LOGIN SUCCESS: POST /api/auth/login with correct credentials returns {token,user}, NO password_hash. (6) WRONG PASSWORD: login with wrong password rejected with 401. (7) UNKNOWN EMAIL: login with non-existent email rejected with 401. All responses are valid JSON, UUIDs are 36 chars, ISO datetime strings, no MongoDB _id leaks. Test account: authtest+1781538884@example.com / password123 / telegram_id=950454640997."

  - task: "Auth: Telegram WebApp one-tap (initData HMAC validation)"
    implemented: true
    working: true
    file: "server.py, auth.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "POST /api/auth/telegram {init_data} validates HMAC-SHA256 with TELEGRAM_BOT_TOKEN (secret=HMAC('WebAppData',token)). On success upserts user by real telegram_id, returns {token,user}. Invalid/forged signature -> 401 (smoke-tested with bad init_data -> 401). NOTE: a fully valid initData can only be produced by Telegram; testing agent can verify the 401 path and that a correctly-signed payload (if constructable with the bot token) authenticates."
      - working: true
        agent: "testing"
        comment: "✅ TESTED: Both Telegram auth scenarios passed. (1) INVALID SIGNATURE: POST /api/auth/telegram with forged hash='badhash123' rejected with 401 ('Не удалось проверить подпись Telegram'). (2) VALID SIGNATURE: Constructed valid initData per Telegram WebApp HMAC scheme (secret_key=HMAC_SHA256(key='WebAppData', msg=bot_token), hash=HMAC_SHA256(key=secret_key, msg=data_check_string with sorted params)). POST with valid signature accepted with 200, returns {token,user} with telegram_id=123456789 (real, not synthetic), 'telegram' in auth_provider, NO password_hash. GET /api/auth/me with that token returns same user (200). All responses valid JSON, UUID id, ISO datetimes, no _id leaks. Test account: telegram_id=123456789, first_name=TestTG, username=testtg."

  - task: "Auth: Google via Emergent Managed Auth (session exchange)"
    implemented: true
    working: true
    file: "server.py, auth.py"
    stuck_count: 0
    priority: "medium"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "POST /api/auth/google/session {session_id} calls Emergent https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data with X-Session-ID; finds/creates user by email (synthetic telegram_id), stores returned session_token in user_sessions. Invalid session_id -> 401. Full happy path requires a real Emergent session_id (browser flow); testing agent can verify the 401 path for a bogus session_id."

  - task: "Auth: Direct Google OAuth (own client_id/secret, own branding)"
    implemented: true
    working: "NA"
    file: "server.py, auth.py, .env"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "Switched Google login from Emergent-managed to DIRECT Google OAuth so the consent screen shows the app's own branding. GOOGLE_CLIENT_ID/SECRET in backend/.env. GET /api/auth/google/config -> {client_id} (public). POST /api/auth/google/oauth {code, redirect_uri} -> exchanges code at oauth2.googleapis.com/token, fetches userinfo, finds/creates user by email (synthetic telegram_id), returns {token,user}. Smoke-tested: config returns client_id; bogus code -> 401. Happy path needs real Google account (browser) -> not agent-testable. NOTE: redirect_uri must be window.location.origin + '/auth/google' and EXACTLY match the URI registered in Google Console."
      - working: true
        agent: "testing"
        comment: "✅ TESTED: Google auth invalid path verified. POST /api/auth/google/session with bogus session_id='bogus-session-id-12345' correctly rejected with 401 ('Не удалось авторизоваться через Google'). This confirms the Emergent session exchange integration is working (returns 401 when Emergent API rejects the session_id). Full happy path (valid session_id from browser OAuth flow) cannot be tested in automated test harness but the error handling is correct. Response is valid JSON."

  - task: "Auth: session dependency + /auth/me + /auth/logout"
    implemented: true
    working: true
    file: "server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "get_current_user reads Authorization: Bearer <token> first, then session_token cookie; validates against user_sessions with expiry check. GET /api/auth/me returns current user (no password_hash) or 401. POST /api/auth/logout deletes session + clears cookie. Smoke-tested: me with token -> 200, me without -> 401."
      - working: true
        agent: "testing"
        comment: "✅ TESTED: All session management scenarios passed (5 tests). (1) GET /api/auth/me WITH BEARER TOKEN: Returns 200 with user data (id, telegram_id, email, auth_provider), NO password_hash, NO _id. (2) GET /api/auth/me WITHOUT TOKEN: Returns 401 ('Не авторизован'). (3) GET /api/auth/me WITH BOGUS TOKEN: Returns 401 ('Недействительная сессия'). (4) POST /api/auth/logout: Returns 200 {ok:true}, session deleted from user_sessions. (5) GET /api/auth/me AFTER LOGOUT: Same token now returns 401 ('Недействительная сессия'), confirming session was deleted. All responses valid JSON, UUIDs are 36 chars, ISO datetime strings."

  - task: "User registration/update on app load"
    implemented: true
    working: true
    file: "server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "Implemented POST /api/users endpoint with upsert logic. Creates new user or updates existing by telegram_id"
      - working: true
        agent: "testing"
        comment: "✅ TESTED: POST /api/users working correctly. Created user with telegram_id=111222333, verified upsert logic - same user updated with same ID, created_at preserved, updated_at changed. All required fields present in response (id, telegram_id, first_name, created_at, updated_at)."

  - task: "Get user by telegram_id"
    implemented: true
    working: true
    file: "server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "Implemented GET /api/users/{telegram_id} endpoint"
      - working: true
        agent: "testing"
        comment: "✅ TESTED: GET /api/users/{telegram_id} working correctly. Successfully retrieved user by telegram_id=111222333, returned correct user data. Properly returns 404 for non-existent users (tested with telegram_id=999999999)."

  - task: "Get Telegram avatar"
    implemented: true
    working: true
    file: "server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "Existing endpoint GET /api/telegram/avatar/{user_id} - fetches avatar via Telegram Bot API"
      - working: true
        agent: "testing"
        comment: "✅ TESTED: GET /api/telegram/avatar/{user_id} working correctly. Endpoint responds properly with avatar_url=null and appropriate error message 'Bad Request: user not found' for test user (telegram_id=111222333), which is expected behavior since it's not a real Telegram user. Bot API integration functioning correctly."

  - task: "Phase 1 - Exercises catalog (GET/POST /api/exercises)"
    implemented: true
    working: true
    file: "server.py, seed.py, models.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "GET /api/exercises returns built-in catalog (default is_builtin=true), supports query/muscle/owner filters. POST /api/exercises creates custom exercise. Seed creates 24 built-in exercises idempotently (uuid5 from slug) on startup. Expect 24 built-in exercises."
      - working: true
        agent: "testing"
        comment: "✅ TESTED: All exercises catalog endpoints working perfectly. (1) GET /api/exercises returns exactly 24 built-in exercises with correct structure (UUID ids, no ObjectId leaks, is_builtin=true). (2) GET /api/exercises?query=жим returns 6 exercises with case-insensitive name filter. (3) GET /api/exercises?muscle=chest returns 4 exercises with correct muscle group filter. (4) POST /api/exercises creates custom exercise with is_builtin=false and owner_telegram_id=770001. All responses use UUID strings, no MongoDB _id fields leaked. Tested with telegram_id=770001."

  - task: "Phase 1 - Program templates (GET/POST /api/programs/templates)"
    implemented: true
    working: true
    file: "server.py, seed.py, models.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "GET /api/programs/templates lists built-in library (expect 3: Full Body new=4 weeks, Upper/Lower=4 weeks, Powerlifting Peaking=3 weeks). GET /api/programs/templates/{id} returns detail with full weeks->days->exercises. POST /api/programs/templates creates custom template (is_builtin=false). Idempotent seed verified via curl."
      - working: true
        agent: "testing"
        comment: "✅ TESTED: All program templates endpoints working perfectly. (1) GET /api/programs/templates returns exactly 3 built-in templates: 'Full Body для новичка' (4 weeks), 'Upper/Lower (гипертрофия)' (4 weeks), 'Powerlifting Peaking' (3 weeks). All have is_builtin=true and UUID ids. (2) GET /api/programs/templates/{id} returns full structure with weeks->days->exercises (verified Full Body has 4 weeks with non-empty days and exercises). (3) GET /api/programs/templates/{bad_id} returns 404 correctly. (4) POST /api/programs/templates creates custom template with is_builtin=false, weeks_count=1, owner_telegram_id=770001. No MongoDB _id leaks."

  - task: "Phase 1 - Plans (assign/snapshot, active, day, week-progress)"
    implemented: true
    working: true
    file: "server.py, models.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "POST /api/plans creates a Plan as a SNAPSHOT of template weeks (template_id) or from inline weeks; deactivates previous active plan for that athlete (single active plan). GET /api/plans/active/{telegram_id} returns active plan or null. GET /api/plans/{id} returns detail (404 if missing). GET /api/plans/{id}/day?week=&day= returns day exercises or rest-day object. GET /api/plans/{id}/week-progress?week= returns 7-day schedule (day_index 1..7 = Mon..Sun) with is_workout/planned_sets. Verified full flow via curl: Full Body template -> workout days Mon/Wed/Fri."
      - working: true
        agent: "testing"
        comment: "✅ TESTED: All plans endpoints working perfectly. (1) POST /api/plans with template_id creates plan with status='active', name from template, 4-week SNAPSHOT from Full Body template. (2) GET /api/plans/active/770001 returns the created plan. (3) Creating SECOND plan from Upper/Lower template correctly deactivates first plan (single active plan rule verified). (4) GET /api/plans/active/770001 now returns second plan. (5) GET /api/plans/{id} returns plan detail; GET /api/plans/{bad_id} returns 404. (6) GET /api/plans/{id}/day?week=1&day=1 returns workout day with 3 exercises (exercise_name, target_sets, target_reps). (7) GET /api/plans/{id}/day?week=1&day=2 returns rest day (is_rest=true, exercises empty). (8) GET /api/plans/{id}/week-progress?week=1 returns 7 days (day_index 1..7) with correct Full Body schedule: days 1,3,5 are workouts (planned_sets=9,7,9), days 2,4,6,7 are rest. (9) POST /api/plans without template_id and weeks returns 400. All UUIDs, no ObjectId leaks. Tested with telegram_id=770001."

  - task: "Phase 2 - Plan day enrichment + %1RM"
    implemented: true
    working: true
    file: "server.py, models.py, seed.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "Plan now stores one_rep_max (copied from template default_one_rep_max). GET /api/plans/{id}/day returns enriched exercises: sets_scheme (each set with computed percent_1rm = round(weight/1RM*100)), muscle_letter (Н/Г/С/П/Р/К from muscle_group), difficulty, tonnage, plus day-level group (e.g. Н+Г+С) and difficulty. Powerlifting template has a 7-exercise heavy day. Verified via curl: bench 127.5kg->91%, 115kg->82%; squat 160->94%, 142.5->84% (matches design). Seed now 29 exercises / 3 templates."
      - working: true
        agent: "testing"
        comment: "✅ TESTED: Plan day enrichment and %1RM calculations working perfectly. (1) Created plan from powerlifting-peaking template for athlete 880099 - one_rep_max correctly populated with bench-press:140, back-squat:170, deadlift:200. (2) GET /api/plans/{id}/day?week=1&day=1 returns exactly 7 exercises with day-level group='Н+Г+С+Р+К' and difficulty='Тяжело'. (3) All exercises have muscle_letter, difficulty, tonnage, and sets_scheme with computed percent_1rm. (4) Verified specific calculations: 'Жим лёжа (без ног)' 127.5kg->91% and 115kg->82%; 'Присед (с паузой)' 160kg->94% and 142.5kg->84% - all match expected values. (5) GET /api/plans/{id}/day?week=1&day=3 correctly returns rest day (is_rest=true). All UUIDs, no ObjectId leaks, ISO datetime strings."

  - task: "Phase 2 - Workout sessions lifecycle"
    implemented: true
    working: true
    file: "server.py, models.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "POST /api/sessions/start {plan_id,athlete_telegram_id,week,day} creates session snapshot (first exercise in_progress); idempotent (returns existing non-finished session); 400 if day is rest/no workout. GET /api/sessions/{id} and GET /api/sessions/active?plan_id=&week=&day=&athlete= return serialized session with stats {tonnage(done only), group, difficulty, duration_sec, done_count, skipped_count, total_count, progress_pct}. PATCH /api/sessions/{id}/exercise/{order}?action=done|skip|reset advances next pending to in_progress and auto-finishes when all resolved. PATCH /api/sessions/{id}/exercise/{order}/edit (body {exercise_name?, sets_scheme?}) recomputes tonnage/%. POST /api/sessions/{id}/finish, POST /api/sessions/{id}/pause?resume=bool. Verified full flow via curl (done/skip advance, auto-finish 6/7=86%, tonnage 12150)."
      - working: true
        agent: "testing"
        comment: "✅ TESTED: Workout sessions lifecycle working perfectly. (1) POST /api/sessions/start creates session with status='in_progress', exercise[0] in_progress, others pending, stats.total_count=7, tonnage=0, group present. (2) Idempotency verified - calling start again returns same session ID. (3) Starting session for rest day (day=3) correctly returns 400. (4) PATCH exercise/0?action=done: exercise 0 status='done', exercise 1 becomes 'in_progress', stats.done_count=1, tonnage=2220, progress_pct=14. (5) PATCH exercise/1?action=skip: exercise 1 status='skipped', exercise 2 becomes 'in_progress', stats.skipped_count=1. (6) PATCH exercise/1?action=reset: exercise 1 back to 'pending'. (7) Marking all remaining exercises done: session auto-finishes (status='finished', finished_at set), progress_pct=100. (8) GET /api/sessions/{id} returns session with stats. (9) GET /api/sessions/active returns same session. (10) POST /api/sessions/{id}/finish idempotent. (11) POST /api/sessions/{id}/pause?resume=false sets paused=true; resume=true sets paused=false. (12) PATCH /api/sessions/{id}/exercise/0/edit with sets_scheme updates tonnage to 900 and computes percent_1rm=88%. All UUIDs, ISO datetimes."

  - task: "Phase 2 - Stats/streak + week-progress from sessions"
    implemented: true
    working: true
    file: "server.py"
    stuck_count: 0
    priority: "medium"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "GET /api/stats/{telegram_id} returns {streak_days, total_workouts} from finished sessions' distinct dates (consecutive days ending today/yesterday). GET /api/plans/{id}/week-progress now reflects real sessions (progress_pct, is_done, has_session per day). Verified via curl: streak=1 after one finished session; day1 progress 86 / done True."
      - working: true
        agent: "testing"
        comment: "✅ TESTED: Stats and week-progress working perfectly. (1) GET /api/stats/880099 returns streak_days=1 and total_workouts=1 after finished session (streak correctly calculated from finished sessions). (2) GET /api/plans/{id}/week-progress?week=1 returns 7 days with correct structure. (3) Day 1 (workout day with finished session) shows progress_pct=100, is_done=true, has_session=true. (4) Day 3 (rest day) correctly shows is_workout=false. Week progress accurately reflects real session data."

  - task: "Edit exercise: add/delete sets + coach comment"
    implemented: true
    working: true
    file: "server.py, models.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "Enhanced PATCH /api/sessions/{id}/exercise/{order}/edit. (1) ADD/DELETE SETS: payload sets_scheme is a full replacement list - sending a list with MORE or FEWER items must add/remove sets; each set's percent_1rm and the exercise tonnage must recompute (sets>=1, reps>=0 clamped). (2) NEW COMMENT FIELD: payload may include 'comment' (athlete's note for the coach). Trimmed, max 500 chars; empty string or null clears it (sets comment=null). Comment is persisted on the SessionExercise and returned in session serialization (GET /api/sessions/{id} and /sessions/active) so it will be visible to the coach later. SessionExercise model now has comment field (default None); _view_exercise passes comment through. Backward compatible: old sessions without comment return null."
      - working: true
        agent: "testing"
        comment: "✅ TESTED: All 9 test scenarios passed for enhanced edit exercise endpoint. Created plan from powerlifting-peaking template for athlete 990011, started session week=1 day=1 (7 exercises, order=0 is squat-competition with 1RM=170). (1) ADD SETS: Successfully added 3 sets, percent_1rm calculated correctly (100kg->59%, 110kg->65%, 120kg->71%), tonnage=1450. (2) DELETE SETS: Reduced to 1 set, tonnage=500. (3) COMMENT ADD: Comment trimmed correctly ('  Болело плечо, снизил вес  ' -> 'Болело плечо, снизил вес'), sets_scheme unchanged. (4) COMMENT CLEAR: Comment cleared with both empty string and null. (5) COMMENT PERSISTENCE: Comment persisted in both GET /api/sessions/{id} and GET /api/sessions/active. (6) CLAMP: Sets and reps clamped correctly (sets=0->1, reps=-3->0, tonnage=0). (7) COMBINED: Both sets_scheme and comment updated on exercise order=1 (tonnage=1350, comment='норм'), exercise order=0 untouched. (8) NAME EDIT: Exercise name edit still works ('Тест присед'). (9) GENERAL ASSERTIONS: No MongoDB _id leaks, all IDs are UUID strings, datetimes are ISO strings, stats object present. All responses valid JSON."
      - working: true
        agent: "main"
        comment: "ADDED AFTER above test: SessionExercise now has 'edited' bool field (default false). The edit endpoint sets edited=true ONLY when exercise_name or sets_scheme actually changed (normalized weight/sets/reps compare); a comment-only edit does NOT set edited. _view_exercise passes edited through (default false). Manually verified via API: editing sets on order=0 -> edited=true; comment-only edit on order=1 -> edited=false. Frontend renders a pencil flag when edited=true and a notes flag when comment present (both next to the status)."

  - task: "Imported powerlifting template + plan scaling by maxes + day remapping + accessory exercises"
    implemented: true
    working: true
    file: "server.py, models.py, seed.py, seed_data/pl_autumn_3m.json"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "NEW built-in template '3 мес Подготовка на осень' (slug pl-autumn-3m) seeded from JSON (12 weeks, 3 training days each, 4 main exercises + accessory exercises per day). Template has requires_maxes=true and base_maxes={squat:200,bench:131,deadlift:230}. Each main exercise has lift_group (squat|bench|deadlift) and sets_scheme; accessory exercises have is_accessory=true and empty sets_scheme. GET /api/programs/templates now returns 4 templates (was 3); seed total exercises=29, templates=4 (idempotent). POST /api/plans now accepts optional 'maxes' {squat,bench,deadlift} and 'training_days' [1..7]. When creating a plan from a requires_maxes template: (1) all set weights scale by factor = athlete_max[lift_group]/base_max[lift_group], rounded to 2.5kg; (2) plan.one_rep_max[slug] = template ref × factor (so %1RM stays ~same); (3) the 3 template workout days get remapped to the chosen training_days (sorted). plan.maxes and plan.training_days are stored. GET /api/plans/{id}/day returns accessory exercises with is_accessory=true and empty sets_scheme (no fabricated set). Smoke-tested: maxes{180,120,210}+days[1,3,5] -> squat 160->145/167.5->150/135->122.5, one_rep_max squat-competition 200->180, week day_index [1,3,5], week-progress workout days [1,3,5], accessory present with empty sets."
      - working: true
        agent: "testing"
        comment: "✅ TESTED: All 7 test scenarios passed (45 assertions). (1) TEMPLATE LIST: GET /api/programs/templates returns exactly 4 templates (was 3). New template 'pl-autumn-3m' has name='3 мес Подготовка на осень', weeks_count=12, requires_maxes=true, base_maxes={squat:200,bench:131,deadlift:230}. (2) TEMPLATE DETAIL: GET /api/programs/templates/{id} returns full 12 weeks; week 1 has 3 days with day_index [2,4,6]; day 1 has 4 main exercises (with lift_group squat/bench/deadlift and non-empty sets_scheme) + 3 accessory exercises (is_accessory=true, empty sets_scheme). (3) PLAN WITH SCALING: POST /api/plans with maxes={squat:180,bench:120,deadlift:210} and training_days=[1,3,5] creates plan correctly. plan.maxes and plan.training_days stored. one_rep_max scaled: squat-competition=180.0 (200*0.9), bench-no-legs=108.0 (117.9*120/131), deadlift-classic=189.0 (207*210/230), squat-paused=157.5 (175*0.9). Week 1 days remapped to [1,3,5]. First squat exercise weights scaled correctly: [145.0, 150.0, 122.5] (original 160/167.5/135 * 0.9 rounded to 2.5kg). (4) PLAN DAY: GET /api/plans/{id}/day?week=1&day=1 returns is_rest=false, title='День 1 · Присед', group='Н+Г+С', difficulty='Тяжело'. 7 exercises: 4 main (with percent_1rm computed, non-empty sets_scheme) + 3 accessory (is_accessory=true, empty sets_scheme). Day 2 correctly returns is_rest=true. (5) WEEK-PROGRESS: GET /api/plans/{id}/week-progress?week=1 returns 7 days; is_workout=true for day_index [1,3,5], rest for [2,4,6,7]. (6) NO-MAXES PATH: POST /api/plans without maxes/training_days succeeds; one_rep_max=template default (squat-competition=200), week days=[2,4,6], first squat weight=160.0 (not scaled). (7) GENERAL: All IDs are UUID strings (36 chars), no MongoDB _id leaks, datetimes are ISO strings. Idempotent seed verified: template count stays at 4. Tested with athletes 661001 (with maxes) and 661002 (no maxes)."


  - task: "BUGFIX ROUND (Groups A+B): training-days remap + streak real work + robustness"
    implemented: true
    working: true
    file: "backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "BUGFIX ROUND (Groups A+B) ready for backend testing. (1) TRAINING-DAYS REMAP (main fix): PATCH /api/plans/{id}/training-days now calls _remap_week_days() which ACTUALLY MOVES the workout days in the plan snapshot to the selected training_days (not just stores the field). This ensures GET /api/plans/{id}/week-progress and GET /api/plans/{id}/day reflect the new schedule immediately. (2) STREAK ONLY COUNTS REAL WORK: GET /api/stats/{telegram_id} now checks if any exercise has status='done' (line 1748). If all exercises are skipped, the session is not counted toward streak/total_workouts. (3) ROBUSTNESS: GET /api/plans/{id}/day returns rest_response if week_obj not found or day_obj not found/is_rest (no 500). GET /api/plans/{id}/week-progress returns 7 days with is_workout=false for missing days (no 500). POST /api/sessions/start checks if day_obj is None or is_rest=true and returns 400. session.date is set as datetime.now(timezone.utc).date().isoformat() (YYYY-MM-DD format)."
      - working: true
        agent: "testing"
        comment: "✅ BUGFIX ROUND TESTS COMPLETE - ALL TESTS PASSED: Tested all 3 bugfix areas with comprehensive scenarios using fresh athletes (821001-821005). (1) TRAINING-DAYS REMAP: Created plan from full-body-beginner template (original workout days [1,3,5]). PATCH /api/plans/{id}/training-days {training_days:[2,4,6]} -> workouts ACTUALLY MOVED to days [2,4,6] in snapshot (verified via week-progress: is_workout=true only on [2,4,6]). Day 2 has real workout (is_rest=false, exercises present), day 1 is rest. Re-PATCH to [1,3,5,7] -> workouts moved again to [1,3,5] with NO duplicate day_index, same number of workouts (no workouts lost). Day 1 now has workout, day 2 is rest. Out-of-range [0,8] returns 400. (2) STREAK ONLY COUNTS REAL WORK: Athlete 821002 - started session, marked ALL exercises as skip -> session auto-finished with done_count=0, skipped_count=3. GET /api/stats/821002 -> streak_days=0, total_workouts=0 (all-skipped session NOT counted). Athlete 821003 - marked 1 exercise done, rest skipped -> GET /api/stats/821003 -> streak_days>=1, total_workouts>=1 (session with >=1 done exercise counted). (3) ROBUSTNESS: GET /api/plans/{id}/day?week=99&day=1 returns is_rest=true rest response (no 500). GET /api/plans/{id}/week-progress?week=99 returns 200 with 7 rest days (all is_workout=false, no 500). Explicit rest day (day 2) returns is_rest=true. POST /api/sessions/start on rest day returns 400. After starting session, session.date is non-null ISO date '2026-06-16' (YYYY-MM-DD format, 10 chars). (4) GENERAL: All responses use UUID strings (36 chars), no MongoDB _id leaks, ISO datetime strings. All 3 bugfix areas working correctly."

frontend:
  - task: "Program config modal (maxes + training days) + accessory folder + real forecast chart"
    implemented: true
    working: "NA"
    file: "pages/Programs.js, pages/Programs.css, components/WorkoutView.js, components/WorkoutView.css, components/DateSelector.js"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: "(1) PROGRAM CONFIG MODAL: In /programs, choosing a template with requires_maxes=true (the '3 мес Подготовка на осень' program) opens a modal asking 3 maxes (Присед/Жим/Тяга, data-testid max-squat/max-bench/max-deadlift) and training days (pick exactly days_per_week=3 weekday buttons data-testid day-1..day-7). Submit (data-testid config-submit) calls POST /api/plans with maxes + training_days. Other templates keep direct selection (no modal). (2) ACCESSORY FOLDER: In WorkoutView, exercises with is_accessory=true are grouped into a collapsible folder 'Подсобные упражнения' (data-testid accessory-folder, toggle accessory-toggle, list accessory-list) shown below the main exercises with a count badge. Accessory cards show NO tonnage/difficulty/forecast — only a recommendation 'Рекомендация: по 4 подхода'; their ✨ edit button is hidden. (3) REAL FORECAST CHART: the per-exercise mini-chart (expand a main exercise card) now plots that exercise's top-set weight across the plan's weeks (computed on frontend from plan.weeks by exercise_slug), with the current week highlighted; caption 'Вес по неделям'. Charts only render for exercises with >=2 weeks of weight data. To test: in /programs choose '3 мес Подготовка на осень' -> modal -> enter maxes (e.g. 200/140/230) and pick 3 days -> program becomes active -> Home shows the day with 4 main exercises + 'Подсобные упражнения' folder; expanding a main card shows the weight-by-weeks chart; expanding the accessory folder shows accessory cards with the '4 подхода' recommendation. NOTE: dev user (telegram_id 99000001) already has this plan active with days Mon/Wed/Fri."

  - task: "Edit exercise UI: add/delete sets, notes textarea, edited/comment flags"
    implemented: true
    working: "NA"
    file: "components/WorkoutView.js, components/WorkoutView.css, components/DateSelector.js"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: "EditExerciseModal ('Изменить упражнение') enhanced: per-row delete-set button (Trash2, disabled when only 1 set left), '+ Добавить подход' button, and a 'Заметки' textarea (500-char counter, hint 'Виден вашему тренеру') that maps to the backend comment field. Save sends {exercise_name, sets_scheme, comment}. ExerciseCard now shows: a pencil flag when ex.edited=true and a notes-icon flag when ex.comment is set (both in the status line), plus the comment text block when expanded. Also: workout control buttons (pause/stop/settings) restyled to 28x28px, border-radius 9px, icons strokeWidth 2.2 (Square=2.6) color #CACACA; forecast chart slightly enlarged (150x58 / mobile 112x50). Needs UI testing (start session -> edit exercise -> add/remove sets -> add note -> save -> verify flags + persistence)."

  - task: "Register user on Telegram WebApp init"
    implemented: true
    working: "NA"
    file: "App.js"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "Added registerUser function that calls POST /api/users on app init"
      - working: "NA"
        agent: "testing"
        comment: "Cannot test user registration without Telegram WebApp context. Function exists and will work when deployed in Telegram environment."

  - task: "Display user avatar in header"
    implemented: true
    working: true
    file: "App.js"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "testing"
        comment: "Testing avatar display functionality - should show either Telegram API avatar URL or UI Avatars fallback"
      - working: true
        agent: "testing"
        comment: "✅ TESTED: Avatar display working perfectly. Found avatar element with data-testid='profile-avatar' in header. Correctly shows UI Avatars fallback (https://ui-avatars.com/api/?name=Гость&background=FF6B00&color=fff&size=80&bold=true) with proper styling. Avatar visible and functional. External URL has routing issues but localhost works perfectly."

  - task: "Auth UI: mandatory gating + Login screen (Telegram/Google/Email)"
    implemented: true
    working: "NA"
    file: "App.js, context/AuthContext.js, pages/Login.js, api.js"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: "Mandatory auth (no guest). AppShell: loading->splash, !auth->Login, auth->UserProvider+routes. Login screen renders: Google button (always), Email+password form with login/register toggle, Telegram button shown ONLY in Telegram (isTelegramAvailable). Verified visually (renders correctly, gating works, TG button hidden on web). NOTE: main agent could NOT drive interactive submit/redirect via screenshot tool (tool does not execute multi-step playwright interactions here). Needs auto_frontend_testing_agent: register new email -> lands on Home (main-container, greeting shows name); login existing -> Home; wrong password -> inline error 'Неверный email или пароль'; toggle to register shows name field; logout from /profile -> back to Login. Token stored in localStorage 'twb_token', sent as Authorization: Bearer."

  - task: "Auth UI: Profile screen + logout + avatar link"
    implemented: true
    working: "NA"
    file: "pages/Profile.js, App.js"
    stuck_count: 0
    priority: "medium"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: "Header avatar is a Link to /profile (data-testid=profile-link). Profile shows avatar, name, email, auth_provider badges, platform, and Выйти (logout). Telegram BackButton wired via useBackButton. Needs testing: navigate avatar->/profile shows profile-page with correct name/email; logout-btn returns to Login and clears token."

  - task: "Auth UI: Google (Emergent) redirect + callback handling"
    implemented: true
    working: "NA"
    file: "context/AuthContext.js, pages/Login.js"
    stuck_count: 0
    priority: "medium"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: "Google button redirects to https://auth.emergentagent.com/?redirect=<origin+'/'>. On return, AuthProvider detects #session_id= in URL fragment FIRST, POSTs to /api/auth/google/session, stores token, cleans hash. Full happy path needs real Google account (cannot fully automate); verify the button redirects to auth.emergentagent.com."

  - task: "P3 Frontend: Profile coach mode (toggle), Подопечные avatars, coach link"
    implemented: true
    working: "NA"
    file: "pages/Profile.js, pages/Profile.css, context/AuthContext.js, api.js"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: "Profile now has: (1) Режим card with segmented Спортсмен/Тренер buttons (data-testid mode-athlete / mode-coach) — calls PATCH /api/users/{id}/mode via AuthContext.switchMode and refreshes authUser. (2) Подопечные section (data-testid profile-clients) visible when user is coach — shows horizontal avatar list (clients-avatars, each client-ava-<telegram_id>) with name + green ring if is_training_now; tapping an avatar -> /coach/:athleteId; header link open-coach-cabinet -> /coach; empty hint shows invite code. (3) Мой тренер section (profile-mycoach): coach-code-input + link-coach-btn calls POST /api/coach/link; if linked shows coach row + unlink-coach (POST /api/coach/unlink). Compiles cleanly, no runtime errors. Needs UI testing of the full flows."

  - task: "P3 Frontend: Coach dashboard (/coach) + client plan management (/coach/:athleteId)"
    implemented: true
    working: "NA"
    file: "pages/Coach.js, pages/CoachClient.js, pages/Coach.css, App.js, api.js"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: "New routes /coach (data-testid coach-page) and /coach/:athleteId (coach-client-page). Dashboard: invite code card (copy-code-btn/copy-link-btn), clients list (client-card-<id>) with live badge + plan visibility badge. Client page: if no plan -> assign-program-btn opens template list (assign-choose-<slug>), requires_maxes templates open AssignModal (assign-submit); coach-created plan becomes DRAFT. If plan exists -> visibility block (toggle-visibility-btn publishes/hides), training days (coach-day-<idx> auto-saves PATCH /training-days), weeks list (week-toggle-<n> publishes/hides each week), reassign-btn to change template. Compiles cleanly. Needs UI testing."

  - task: "P3 Frontend: Athlete sees 'plan preparing' for draft plan (DateSelector)"
    implemented: true
    working: "NA"
    file: "components/DateSelector.js"
    stuck_count: 0
    priority: "medium"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: "DateSelector now detects plan.visibility==='draft' (backend returns draft plan with weeks=[]) and shows a 'Ваш тренер готовит для вас программу' card (data-testid plan-preparing-card) instead of rest/workout/no-plan blocks. Once coach publishes, the real weeks/day UI returns. Needs UI testing with a coach-created draft plan."

  - task: "Plan editor Frontend (/coach/:athleteId/edit): weeks/days/exercises CRUD UI"
    implemented: true
    working: "NA"
    file: "pages/CoachPlanEditor.js, pages/CoachClient.js, pages/Coach.css, App.js, api.js"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: "New route /coach/:athleteId/edit (data-testid plan-editor-page), reachable from CoachClient via edit-plan-btn. Features: rename plan (plan-name -> plan-name-input/plan-name-save -> PATCH /plans/{id}); week pills (week-pill-N) + add-week-btn (POST /week) + delete-week-btn (DELETE /week); per-day cards (day-card-N) with edit-day-N/delete-day-N; add-day-btn opens DayModal (day-pick-N weekday picker, day-title, day-rest, day-save -> PUT /day); exercise rows (ex-row-D-i) with edit-ex/delete-ex; add-ex-D opens ExerciseModal (ex-name, ex-muscle, ex-diff, ex-accessory, set rows set-weight/sets/reps-i, add-set-row, ex-save -> PUT /exercise). Each op persists to backend and updates local plan from full Plan response. Compiles cleanly. Needs UI testing."




metadata:
  created_by: "main_agent"
  version: "1.0"
  test_sequence: 9
  run_ui: false

test_plan:
  current_focus:
    - "Frontend: week dots (prev/current/next) + 'План' button opens week picker"
  stuck_tasks: []
  test_all: false
  test_priority: "high_first"

agent_communication:
  - agent: "main"
    message: "Implemented user registration in MongoDB. Please test: 1) POST /api/users creates new user, 2) POST /api/users with same telegram_id updates user, 3) GET /api/users/{telegram_id} returns user, 4) GET /api/telegram/avatar/{user_id} works with valid telegram_id"
  - agent: "testing"
    message: "✅ ALL BACKEND TESTS PASSED: Created comprehensive backend_test.py and tested all 3 high-priority backend endpoints. 1) POST /api/users: User registration/update working perfectly with proper upsert logic. 2) GET /api/users/{telegram_id}: User retrieval working with correct 404 handling. 3) GET /api/telegram/avatar/{user_id}: Avatar endpoint working correctly with proper Telegram Bot API integration. All endpoints use correct production URL and handle responses properly. Backend is fully functional for the TrainWithBrain Telegram WebApp."
  - agent: "testing"
    message: "✅ AVATAR DISPLAY TESTED: Avatar functionality working perfectly on localhost. Found profile avatar in header with correct data-testid, displays UI Avatars fallback with proper styling (orange background #FF6B00). User registration cannot be tested without Telegram WebApp context but code is implemented correctly."
  - agent: "main"
    message: "PHASE 1 backend ready for testing (Programs & Plans). Please test ONLY the new Phase 1 endpoints (do not re-test old ones unless needed): (1) GET /api/exercises returns 24 built-in exercises; supports ?query=&muscle=&owner=. POST /api/exercises creates custom exercise. (2) GET /api/programs/templates returns 3 built-in templates; GET /api/programs/templates/{id} returns full structure; POST /api/programs/templates creates custom. (3) Plans flow: POST /api/plans with {athlete_telegram_id, template_id} must create a SNAPSHOT plan (status=active) and deactivate previous active plan for same athlete; GET /api/plans/active/{telegram_id} returns it (null if none); GET /api/plans/{id} (404 if missing); GET /api/plans/{id}/day?week=1&day=1 returns exercises; GET /api/plans/{id}/week-progress?week=1 returns 7 days with day_index 1..7 (Mon..Sun) and is_workout flags. Use a fresh test telegram_id (e.g., 770001). Verify idempotent seed (counts stay 24 exercises / 3 templates after restart). Verify UUIDs (no Mongo ObjectId leaks)."
  - agent: "testing"
    message: "✅ PHASE 1 BACKEND TESTS COMPLETE - ALL PASSED: Tested all Phase 1 endpoints with telegram_id=770001. (1) Exercises catalog: 24 built-in exercises returned, filters working (query, muscle), custom exercise creation working. (2) Program templates: 3 built-in templates returned with correct weeks_count, detail endpoint returns full structure, custom template creation working. (3) Plans: Plan creation from template creates SNAPSHOT with correct status, single active plan rule enforced (first plan deactivated when second created), active plan retrieval working, day endpoint returns workout/rest days correctly, week-progress returns 7-day schedule with correct Full Body schedule (Mon/Wed/Fri workouts). (4) Idempotency verified: counts stable at 24 exercises / 3 templates. All responses use UUID strings, no MongoDB ObjectId leaks, all datetime fields are ISO strings. ⚠️ NOTE: External URL (https://avatar-loader-1.preview.emergentagent.com/api/*) returns '404 page not found' for all endpoints - this is a Kubernetes ingress routing issue, NOT a backend code issue. Backend works perfectly on localhost:8001. Tests were run using localhost:8001."
  - agent: "main"
    message: "Note: the external URL 404 from previous run was a STALE .env (cloned repo pointed to avatar-loader-1). Fixed frontend/.env REACT_APP_BACKEND_URL to this container; external API now works. PHASE 2 backend ready for testing (seed is now 29 exercises / 3 templates). Please test ONLY Phase 2 (do not re-test Phase 1 unless needed). Use a fresh athlete telegram_id like 880099. (A) Day enrichment + %1RM: create a plan from the 'powerlifting-peaking' template -> plan.one_rep_max must be populated (e.g. bench-press:140, back-squat:170). GET /api/plans/{id}/day?week=1&day=1 -> 7 exercises; verify computed percent_1rm: 'Жим лёжа (без ног)' 127.5kg->91% & 115kg->82%; 'Присед (с паузой)' 160kg->94% & 142.5kg->84%; each exercise has muscle_letter, difficulty, tonnage; day-level group like 'Н+Г+С+Р+К' and difficulty 'Тяжело'. (B) Sessions: POST /api/sessions/start {plan_id,athlete_telegram_id,week:1,day:1} -> session in_progress, exercises[0].status='in_progress', stats.total_count=7, tonnage=0. Calling start again returns SAME session (idempotent). POST start for a REST day (e.g. day=3) -> 400. PATCH /api/sessions/{id}/exercise/0?action=done then exercise/1?action=skip -> statuses [done,skipped,in_progress,...], stats.done_count=1, progress_pct=14. Mark the rest done -> status auto 'finished', progress 100 or 86 depending. GET /api/sessions/{id} and GET /api/sessions/active?plan_id=&week=1&day=1&athlete= return same session with stats. POST /api/sessions/{id}/finish sets finished. POST /api/sessions/{id}/pause?resume=false sets paused true; resume=true sets false. PATCH /api/sessions/{id}/exercise/0/edit body {\"sets_scheme\":[{\"weight\":150,\"sets\":2,\"reps\":3}]} updates tonnage and percent_1rm. (C) Stats: GET /api/stats/{athlete} -> streak_days>=1 after a finished session. GET /api/plans/{id}/week-progress?week=1 -> day with finished session shows progress_pct>0 and is_done=true. Verify UUIDs only, ISO datetimes, no _id leaks."
  - agent: "testing"
    message: "✅ PHASE 2 BACKEND TESTS COMPLETE - ALL PASSED: Tested all Phase 2 endpoints with athlete telegram_id=880099 using powerlifting-peaking template. (A) Plan day enrichment + %1RM: Plan created with one_rep_max correctly populated (bench-press:140, back-squat:170, deadlift:200). GET /api/plans/{id}/day?week=1&day=1 returns exactly 7 exercises with day-level group='Н+Г+С+Р+К' and difficulty='Тяжело'. All exercises have muscle_letter, difficulty, tonnage, sets_scheme with computed percent_1rm. Verified specific calculations: 'Жим лёжа (без ног)' 127.5kg->91% & 115kg->82%; 'Присед (с паузой)' 160kg->94% & 142.5kg->84% - all match expected. Day 3 correctly returns rest day. (B) Workout sessions lifecycle: POST /api/sessions/start creates session (status='in_progress', ex[0] in_progress, stats.total_count=7, tonnage=0, group present). Idempotency verified (same session ID returned). REST day start returns 400. PATCH exercise/0?action=done: ex0='done', ex1='in_progress', stats.done_count=1, tonnage=2220, progress_pct=14. PATCH exercise/1?action=skip: ex1='skipped', ex2='in_progress', stats.skipped_count=1. PATCH exercise/1?action=reset: ex1='pending'. All remaining marked done: session auto-finishes (status='finished', progress_pct=100). GET /api/sessions/{id} and GET /api/sessions/active return session with stats. POST /api/sessions/{id}/finish idempotent. POST /api/sessions/{id}/pause works (paused=true/false). PATCH /api/sessions/{id}/exercise/0/edit updates tonnage to 900 and computes percent_1rm=88%. (C) Stats + week-progress: GET /api/stats/880099 returns streak_days=1, total_workouts=1. GET /api/plans/{id}/week-progress?week=1 returns 7 days; day 1 shows progress_pct=100, is_done=true, has_session=true; day 3 (rest) shows is_workout=false. All responses use UUID strings, ISO datetime strings, no MongoDB _id leaks. All 52 test assertions passed."
  - agent: "main"
    message: "NEW TASK ready for testing: 'Edit exercise: add/delete sets + coach comment'. Test ONLY the edit endpoint PATCH /api/sessions/{id}/exercise/{order}/edit (do not re-test other Phase 2 flows). Setup: create a plan from 'powerlifting-peaking' template for a fresh athlete telegram_id (e.g. 990011), start a session for week=1&day=1 (7 exercises). Then on exercise order=0: (1) ADD SETS: send body {\"sets_scheme\":[{\"weight\":100,\"sets\":2,\"reps\":5},{\"weight\":110,\"sets\":1,\"reps\":3},{\"weight\":120,\"sets\":1,\"reps\":1}]} -> exercise must now have 3 sets, each with recomputed percent_1rm (exercise at order=0 is slug 'squat-competition', plan 1RM=170: 100->59%, 110->65%, 120->71%), tonnage = 100*2*5 + 110*1*3 + 120*1*1 = 1000+330+120 = 1450. (2) DELETE SETS: send body {\"sets_scheme\":[{\"weight\":100,\"sets\":1,\"reps\":5}]} -> exactly 1 set remains, tonnage=500. (3) COMMENT ADD: send body {\"comment\":\"  Болело плечо, снизил вес  \"} -> exercise.comment == 'Болело плечо, снизил вес' (trimmed). (4) COMMENT CLEAR: send body {\"comment\":\"\"} -> exercise.comment == null; also {\"comment\":null} -> null. (5) COMMENT PERSISTENCE: GET /api/sessions/{id} must return the comment on that exercise; GET /api/sessions/active?plan_id=&week=1&day=1&athlete= too. (6) clamp: sending {\"sets_scheme\":[{\"weight\":80,\"sets\":0,\"reps\":-3}]} -> stored set has sets=1, reps=0. (7) combined: body with BOTH sets_scheme and comment updates both. Verify UUIDs only, ISO datetimes, no _id leaks, and that other exercises in the session are untouched."
  - agent: "testing"
    message: "✅ EDIT EXERCISE ENDPOINT TESTS COMPLETE - ALL PASSED: Tested enhanced PATCH /api/sessions/{id}/exercise/{order}/edit endpoint with athlete telegram_id=990011. Created plan from powerlifting-peaking template (one_rep_max: squat-competition:170, bench-press:140, deadlift:200), started session week=1 day=1 (7 exercises, order=0 is squat-competition). All 9 test scenarios passed: (1) ADD SETS: 3 sets added, percent_1rm calculated correctly (100kg->59%, 110kg->65%, 120kg->71%), tonnage=1450. (2) DELETE SETS: Reduced to 1 set, tonnage=500. (3) COMMENT ADD: Comment trimmed correctly ('  Болело плечо, снизил вес  ' -> 'Болело плечо, снизил вес'), sets_scheme unchanged. (4) COMMENT CLEAR: Comment cleared with both empty string and null. (5) COMMENT PERSISTENCE: Comment persisted in both GET /api/sessions/{id} and GET /api/sessions/active. (6) CLAMP: Sets and reps clamped correctly (sets=0->1, reps=-3->0, tonnage=0). (7) COMBINED: Both sets_scheme and comment updated on exercise order=1 (tonnage=1350, comment='норм'), exercise order=0 untouched. (8) NAME EDIT: Exercise name edit still works ('Тест присед'). (9) GENERAL ASSERTIONS: No MongoDB _id leaks, all IDs are UUID strings, datetimes are ISO strings, stats object present. All responses valid JSON. Backend API fully functional."
  - agent: "testing"
    message: "✅ IMPORTED POWERLIFTING TEMPLATE + PLAN SCALING TESTS COMPLETE - ALL PASSED: Tested new '3 мес Подготовка на осень' (pl-autumn-3m) template with maxes scaling, day remapping, and accessory exercises. All 45 assertions passed across 7 test scenarios. (1) TEMPLATE LIST: GET /api/programs/templates returns exactly 4 templates (was 3). New template has name='3 мес Подготовка на осень', weeks_count=12, requires_maxes=true, base_maxes={squat:200,bench:131,deadlift:230}. (2) TEMPLATE DETAIL: Full 12 weeks returned; week 1 has 3 days [2,4,6]; day 1 has 4 main exercises (lift_group squat/bench/deadlift, non-empty sets_scheme) + 3 accessory exercises (is_accessory=true, empty sets_scheme). (3) PLAN WITH SCALING: Created plan with maxes={squat:180,bench:120,deadlift:210} and training_days=[1,3,5]. plan.maxes and plan.training_days stored correctly. one_rep_max scaled: squat-competition=180.0, bench-no-legs=108.0, deadlift-classic=189.0, squat-paused=157.5. Week 1 days remapped to [1,3,5]. First squat exercise weights scaled: [145.0, 150.0, 122.5] (original 160/167.5/135 * 0.9 rounded to 2.5kg). (4) PLAN DAY: GET /api/plans/{id}/day?week=1&day=1 returns is_rest=false, title='День 1 · Присед', group='Н+Г+С', difficulty='Тяжело'. 7 exercises: 4 main (percent_1rm computed, non-empty sets_scheme) + 3 accessory (is_accessory=true, empty sets_scheme). Day 2 is rest. (5) WEEK-PROGRESS: GET /api/plans/{id}/week-progress?week=1 returns 7 days; is_workout=true for [1,3,5], rest for [2,4,6,7]. (6) NO-MAXES PATH: Plan created without maxes/training_days uses template defaults: one_rep_max squat-competition=200, days=[2,4,6], first squat weight=160.0 (not scaled). (7) GENERAL: All IDs are UUID strings (36 chars), no MongoDB _id leaks, datetimes are ISO strings. Idempotent seed verified: template count stays at 4. Tested with athletes 661001 (with maxes) and 661002 (no maxes). Backend API fully functional."
  - agent: "main"
    message: "NEW FEATURE ready for backend testing: AUTHENTICATION (3 methods, mandatory auth, no guest). Test ONLY the new /api/auth/* endpoints (do NOT re-test prior phases). Unified session model: collection user_sessions {session_token, telegram_id, auth_method, expires_at(ISO), created_at}; every account keyed by telegram_id (real for Telegram, synthetic 900000000000+ for email/google). Auth dependency get_current_user reads Authorization: Bearer <token> first, then session_token cookie. SCENARIOS: (A) EMAIL: POST /api/auth/register {email,password,name} -> 200 {token,user}; user has telegram_id, email, auth_provider=['email'], NO password_hash field; weak password (<6 chars) -> 400; invalid email (no @ / no domain dot) -> 400; duplicate email -> 400. POST /api/auth/login {email,password} -> 200 {token,user}; wrong password -> 401; unknown email -> 401. (B) SESSION: GET /api/auth/me with header 'Authorization: Bearer <token>' -> 200 user (no password_hash); without header -> 401; with bogus token -> 401. POST /api/auth/logout with token -> {ok:true}; afterwards GET /api/auth/me with that same token -> 401 (session deleted). (C) TELEGRAM: POST /api/auth/telegram {init_data:'hash=bad&user=...'} with an INVALID signature -> 401 (cannot forge without bot token). If you can construct a valid initData using the bot token in backend/.env (TELEGRAM_BOT_TOKEN) per Telegram HMAC scheme (secret=HMAC_SHA256(key='WebAppData', msg=token); hash=HMAC_SHA256(key=secret, msg=data_check_string)), then a valid payload with user={id,first_name} -> 200 {token,user} with that real telegram_id and auth_provider containing 'telegram'. (D) GOOGLE: POST /api/auth/google/session {session_id:'bogus'} -> 401 (Emergent exchange fails for invalid id). Full happy path needs a real browser session_id, skip if unavailable. GENERAL: responses are JSON, UUID 'id' on users, ISO datetimes, NO _id leaks, password_hash never present in any auth response. Use fresh emails like authtest+<rand>@example.com. test_credentials.md will be updated with any created accounts."
  - agent: "testing"
    message: "✅ AUTHENTICATION BACKEND TESTS COMPLETE - ALL 17 TESTS PASSED: Tested all 4 auth tasks (email, telegram, google, session management) with comprehensive scenarios. (A) EMAIL AUTH (7 tests): Register creates user with synthetic telegram_id=950454640997 (>=900000000000), returns {token,user} with UUID id, 'email' in auth_provider, NO password_hash. Weak password (<6 chars) rejected with 400. Invalid emails (no @ or no domain dot) rejected with 400. Duplicate email rejected with 400. Login with correct credentials returns {token,user}. Wrong password rejected with 401. Unknown email rejected with 401. (B) SESSION MANAGEMENT (5 tests): GET /api/auth/me with Bearer token returns user (200), NO password_hash, NO _id. Without token returns 401. With bogus token returns 401. POST /api/auth/logout returns {ok:true} (200). After logout, same token returns 401 (session deleted). (C) TELEGRAM AUTH (2 tests): Invalid HMAC signature rejected with 401. Valid HMAC signature (constructed per Telegram WebApp spec with bot token) accepted with 200, returns {token,user} with real telegram_id=123456789, 'telegram' in auth_provider. GET /api/auth/me with Telegram token works (200). (D) GOOGLE AUTH (1 test): Bogus session_id rejected with 401 (Emergent exchange fails correctly). (E) GENERAL ASSERTIONS (2 tests): All responses are valid JSON. UUIDs are 36 chars with 4 hyphens. ISO datetime strings. NO MongoDB _id leaks. password_hash NEVER present in any auth response. Test accounts created: email=authtest+1781538884@example.com / password=password123 / telegram_id=950454640997; telegram_id=123456789 (TestTG). Updated /app/memory/test_credentials.md with test accounts. Backend authentication fully functional."
  - agent: "main"
    message: "PHASE 3 (Coach mode) backend ready for testing. Test ONLY the new P3 endpoints (do NOT re-test prior phases). Conventions unchanged: UUIDs only, ISO datetimes, no _id leaks, explicit telegram_id in path/body (same pattern as /plans). SETUP: create two users via POST /api/users -> coach (e.g. telegram_id=701001, first_name='Coach') and athlete (e.g. 701002, first_name='Sam'). SCENARIOS: (1) MODE: PATCH /api/users/701001/mode {\"mode\":\"coach\"} -> 200, returns user with roles containing both 'athlete' and 'coach', active_mode='coach', invite_code present (8 chars). PATCH with mode='bad' -> 400. PATCH /api/users/999999/mode -> 404. PATCH back to {\"mode\":\"athlete\"} keeps coach role but active_mode='athlete'. (2) INVITE: POST /api/coach/invite {\"coach_telegram_id\":701001} -> 200 {invite_code, deep_link, bot_username}; calling again returns the SAME invite_code (stable). (3) LINK: POST /api/coach/link {\"code\":<invite_code>,\"athlete_telegram_id\":701002} -> 200 {status:'active', coach:{telegram_id:701001,...}}; user 701002 now has coach_telegram_id=701001. Unknown code -> 404. Self-link (code belongs to coach, athlete_telegram_id=701001) -> 400. (4) ATHLETE COACH: GET /api/athlete/701002/coach -> {coach:{telegram_id:701001,...}}; GET /api/athlete/701001/coach -> {coach:null}. (5) CLIENTS: GET /api/coach/701001/clients -> {clients:[{athlete:{telegram_id:701002}, plan:null, is_training_now:false, last_workout_at:null, linked_at}]}. (6) COACH CREATES DRAFT PLAN: get a template id from GET /api/programs/templates; POST /api/plans {\"athlete_telegram_id\":701002,\"template_id\":<id>,\"coach_telegram_id\":701001} -> plan.visibility='draft', prepared_by_coach=true, weeks non-empty. GET /api/plans/active/701002 -> visibility='draft' AND weeks=[] (content hidden). GET /api/coach/701001/clients/701002/plan -> full plan WITH weeks (coach sees draft). A coach who is NOT linked (e.g. 701003) calling that endpoint -> 403. (7) VISIBILITY: PATCH /api/plans/{plan_id}/visibility {\"visibility\":\"published\"} -> 200 visibility='published', published_at set. GET /api/plans/active/701002 now returns full weeks. Invalid visibility -> 400. (8) WEEK PUBLISH: PATCH /api/plans/{plan_id}/weeks/1/publish {\"published\":false} -> 200, weeks[0].published=false. Non-existent week (e.g. 99) -> 404. (9) TRAINING DAYS: PATCH /api/plans/{plan_id}/training-days {\"training_days\":[1,3,5]} -> 200 training_days=[1,3,5]; out-of-range like [0,8] -> 400. (10) SELF PLAN STILL PUBLISHED: POST /api/plans {\"athlete_telegram_id\":701002,\"template_id\":<id>} (no coach) -> visibility='published' (backward compatible). (11) CONFIRM SESSION (optional): start a session for the published plan via POST /api/sessions/start, then POST /api/sessions/{id}/confirm {\"coach_telegram_id\":701001} -> coach_confirmed=true, confirmed_by=701001; a non-linked coach -> 403; missing session -> 404. (12) UNLINK: POST /api/coach/unlink {\"athlete_telegram_id\":701002} -> {ok:true}; GET /api/athlete/701002/coach -> {coach:null}; GET /api/coach/701001/clients -> clients list no longer includes 701002. Verify all responses are JSON, UUIDs only, ISO datetimes, no _id leaks."

  - agent: "testing"
    message: "✅ PHASE 3 COACH MODE BACKEND TESTS COMPLETE - ALL 29 TESTS PASSED: Tested all 5 P3 tasks with comprehensive scenarios covering all 12 flows specified in review_request. Created test users: coach (701001), athlete (701002), unlinked coach (701003). (1) MODE SWITCH (4 tests): PATCH /api/users/{telegram_id}/mode switches to coach (roles include athlete+coach, active_mode=coach, invite_code generated 8 chars), invalid mode returns 400, unknown user returns 404, switch back to athlete keeps coach role. (2) INVITE+LINK+UNLINK (11 tests): POST /api/coach/invite generates stable invite_code+deep_link+bot_username. POST /api/coach/link links athlete to coach (status=active, coach brief returned), unknown code returns 404, self-link returns 400. GET /api/athlete/701002/coach returns coach 701001. GET /api/athlete/701001/coach returns null. GET /api/coach/701001/clients includes athlete 701002 with plan summary, is_training_now, last_workout_at, linked_at. POST /api/coach/unlink removes link, athlete coach becomes null, clients list no longer includes athlete. (3) PLAN VISIBILITY (7 tests): Coach creates plan with coach_telegram_id -> visibility=draft, prepared_by_coach=true. GET /api/plans/active/701002 returns draft with weeks=[] (hidden). GET /api/coach/701001/clients/701002/plan returns full weeks (coach sees draft). Unlinked coach 701003 returns 403. PATCH /api/plans/{id}/visibility {visibility:published} sets published_at, athlete now sees full weeks. Invalid visibility returns 400. Self-created plan (no coach) has visibility=published (backward compatible). (4) WEEK PUBLISH + TRAINING DAYS (4 tests): PATCH /api/plans/{id}/weeks/1/publish {published:false} sets week1.published=false. Non-existent week returns 404. PATCH /api/plans/{id}/training-days {training_days:[1,3,5]} stores sorted [1,3,5]. Out-of-range days return 400. (5) CONFIRM SESSION (3 tests): POST /api/sessions/{id}/confirm {coach_telegram_id:701001} sets coach_confirmed=true, confirmed_by=701001, confirmed_at timestamp. Non-linked coach returns 403. Missing session returns 404. All responses valid JSON, UUIDs only (36 chars, 4 hyphens), ISO datetime strings, NO MongoDB _id leaks. All conventions verified across multiple endpoints. Backend API fully functional for Phase 3 Coach mode."
  - agent: "testing"
    message: "✅ PHASE 3 COACH MODE BACKEND — ALL 29 TESTS PASSED across all 5 P3 tasks (mode switch, invite/link/unlink/clients/client-plan/athlete-coach, plan visibility draft/published, week publish + training-days, coach confirm session). Verified: coach-created plan -> draft + prepared_by_coach; athlete active plan hides weeks for draft; publish reveals; week.published toggles; training_days validated; unlinked coach -> 403; UUIDs/ISO/no _id leaks. Backend P3 fully functional."
  - agent: "main"
    message: "P3 FRONTEND implemented (coach mode UI). Per user request, added a 'Подопечные' section in Profile showing a horizontal list of client avatars. Full P3 frontend: (A) Profile.js — Режим toggle (mode-athlete/mode-coach), Подопечные avatars (clients-avatars, client-ava-<id>) + open-coach-cabinet link, Мой тренер (coach-code-input/link-coach-btn/unlink-coach). (B) New /coach dashboard (Coach.js) with invite code + clients list. (C) New /coach/:athleteId (CoachClient.js) — assign template (draft), toggle-visibility-btn, training days, per-week publish toggles. (D) DateSelector shows plan-preparing-card for draft plans. Frontend compiles cleanly, no runtime errors; backend all green. AWAITING USER PERMISSION to run auto_frontend_testing_agent. Suggested test (athlete-A registers email, becomes coach in /profile, copies invite code; athlete-B registers, enters code in Мой тренер; A sees B in Подопечные avatars + /coach; A opens B, assigns a non-maxes template -> draft; B sees 'план готовится'; A publishes -> B sees weeks; A sets training days + hides week 1)."

  - agent: "testing"
    message: "✅ PLAN EDITOR ENDPOINTS TESTS COMPLETE - ALL 18 TESTS PASSED: Tested all 7 plan editor CRUD endpoints for coach mode. Created plan from template (4 weeks) for athlete 734001. (1) PATCH /api/plans/{id}: Successfully updated name to 'Custom' and current_week to 2. (2) POST /api/plans/{id}/week: Added week, weeks count increased from 4 to 5, new week has week_index=5, published=true, days=[]. (3) PUT /api/plans/{id}/day: Added day (week=1, day=2, title='День тяги', is_rest=false). Repeated call updated title in place (no duplicate). Invalid day=8 returns 400. Nonexistent week=99 returns 404. (4) PUT /api/plans/{id}/exercise: Added exercise 'Становая' with sets_scheme [{weight:150, sets:3, reps:5}], target_sets=3, target_weight=150. Edited at order=0 with 2 sets [{160,1,3},{140,2,5}], target_sets=3 (1+2). GET /api/plans/{id}/day?week=1&day=2 returns exercises[0].tonnage=1880 (160*1*3+140*2*5), sets_scheme entries have percent_1rm key. Missing week/day returns 404. (5) DELETE /api/plans/{id}/exercise: Removed exercise at order=0. Out-of-range order returns 404. (6) DELETE /api/plans/{id}/day: Removed day (week=1, day=2). Missing day returns 404. (7) DELETE /api/plans/{id}/week: Deleted week 5, weeks count decreased from 5 to 4, remaining weeks reindexed contiguously 1..4. Nonexistent week returns 404. All responses valid JSON, UUIDs only, ISO datetimes, no _id leaks. Backend plan editor fully functional."

  - agent: "main"
    message: "NEW: PLAN EDITOR backend ready for testing. Test ONLY the new plan-editor endpoints (do NOT re-test prior phases). Setup: create plan via POST /api/plans {athlete_telegram_id:734001, template_id:<first template id from GET /api/programs/templates>} -> capture plan_id; it has 4 weeks. SCENARIOS: (1) PATCH /api/plans/{id} {\"name\":\"Custom\"} -> name updated; {\"current_week\":2} -> current_week=2. (2) POST /api/plans/{id}/week -> weeks length +1, last week_index is max+1 (e.g. 5), published=true, days=[]. (3) PUT /api/plans/{id}/day {\"week\":1,\"day\":2,\"title\":\"День тяги\",\"is_rest\":false} -> week1 gains day_index 2; repeat with title change -> updates same day (no duplicate). day=8 -> 400; week=99 -> 404. (4) PUT /api/plans/{id}/exercise {\"week\":1,\"day\":2,\"exercise_name\":\"Становая\",\"muscle_group\":\"back\",\"difficulty\":\"Тяжело\",\"sets_scheme\":[{\"weight\":150,\"sets\":3,\"reps\":5}],\"rest_seconds\":180} -> appends exercise; target_sets=3 (sum of sets), target_weight=150. Then with \"order\":0 and sets_scheme [{160,1,3},{140,2,5}] -> edits in place, 2 sets, target_sets=3. Verify GET /api/plans/{id}/day?week=1&day=2 -> exercises[0].tonnage=1880, sets_scheme have percent_1rm keys, group letter present. week/day missing -> 404. (5) DELETE /api/plans/{id}/exercise?week=1&day=2&order=0 -> exercise removed; out-of-range order -> 404. (6) DELETE /api/plans/{id}/day?week=1&day=2 -> day removed; missing -> 404. (7) DELETE /api/plans/{id}/week?week=5 -> week removed AND remaining week_index reindexed contiguous 1..N; deleting nonexistent week -> 404. Verify all responses are full Plan JSON, UUIDs only, ISO datetimes, no _id leaks. Use athlete telegram_id 734001 (clean up not required)."
  - agent: "main"
    message: "BUGFIX ROUND (Groups A+B) ready for backend testing. Test ONLY these changed areas (do NOT re-test unrelated prior phases). Conventions unchanged: UUIDs only, ISO datetimes, no _id leaks, telegram_id in path/body. SETUP: create athlete (e.g. 821001). Get a template id from GET /api/programs/templates (use a non-maxes one like 'full-body-beginner', OR 'pl-autumn-3m' with maxes). \n\n(1) TRAINING-DAYS REMAP (main fix): Create plan POST /api/plans {athlete_telegram_id:821001, template_id:<full-body-beginner>}. Note which day_index values are workouts in week 1 via GET /api/plans/{id}/week-progress?week=1 (is_workout=true days). Then PATCH /api/plans/{id}/training-days {\"training_days\":[2,4,6]} -> 200, plan.training_days=[2,4,6]. CRITICAL: now GET /api/plans/{id}/week-progress?week=1 MUST show is_workout=true ONLY on days [2,4,6] (the workouts were actually MOVED in the snapshot, not just stored as a field). Also GET /api/plans/{id}/day?week=1&day=2 returns a real workout (is_rest=false, exercises present) and day=1 returns rest. Then PATCH training-days {\"training_days\":[1,3,5,7]} -> week-progress shows workouts on [1,3,5] (or [1,3,5,7] if 4 workout days) with NO duplicate day_index. Out-of-range [0,8] -> 400. Number of workout days preserved (no workouts lost/duplicated).\n\n(2) STREAK ONLY COUNTS REAL WORK: For a fresh athlete (e.g. 821002) with a plan, start a session and mark ALL exercises as 'skip' (PATCH /api/sessions/{id}/exercise/{order}?action=skip for every order) so it auto-finishes with 0 done. GET /api/stats/821002 -> streak_days=0 AND total_workouts=0 (a fully-skipped session must NOT count). Then for another day (or athlete 821003) mark at least one exercise 'done' and finish -> GET /api/stats -> streak_days>=1, total_workouts>=1.\n\n(3) ROBUSTNESS: GET /api/plans/{id}/day?week=99&day=1 -> returns is_rest=true rest_response (no 500). GET /api/plans/{id}/week-progress?week=99 -> 200 with 7 rest days (no 500). A day explicitly marked is_rest=true (via plan editor PUT /api/plans/{id}/day {week,day,is_rest:true}) -> GET .../day returns is_rest=true. POST /api/sessions/start for a rest day -> 400. After POST /api/sessions/start, GET /api/sessions/{id} -> session.date is a non-null ISO date (YYYY-MM-DD). Verify no _id leaks, UUIDs, ISO datetimes throughout."
  - agent: "testing"
    message: "✅ BUGFIX ROUND (Groups A+B) BACKEND TESTS COMPLETE - ALL TESTS PASSED: Tested all 3 bugfix areas with comprehensive scenarios using fresh athletes (821001-821005). Created backend_test_bugfix.py with 4 test groups covering all specified scenarios. (1) TRAINING-DAYS REMAP (main fix): Created plan from full-body-beginner template (original workout days [1,3,5]). PATCH /api/plans/{id}/training-days {training_days:[2,4,6]} -> 200, workouts ACTUALLY MOVED to days [2,4,6] in snapshot (verified via GET /api/plans/{id}/week-progress?week=1: is_workout=true ONLY on [2,4,6]). GET /api/plans/{id}/day?week=1&day=2 returns real workout (is_rest=false, 3 exercises present), day=1 returns rest (is_rest=true, 0 exercises). Re-PATCH to [1,3,5,7] -> workouts moved again to [1,3,5] with NO duplicate day_index, same number of workouts (no workouts lost). Day 1 now has workout, day 2 is rest. Out-of-range [0,8] returns 400. (2) STREAK ONLY COUNTS REAL WORK: Athlete 821002 - started session on day 1 (3 exercises), marked ALL exercises as skip -> session auto-finished with status='finished', done_count=0, skipped_count=3. GET /api/stats/821002 -> streak_days=0, total_workouts=0 (all-skipped session NOT counted). Athlete 821003 - marked 1 exercise done, rest skipped -> session finished with done_count>=1. GET /api/stats/821003 -> streak_days>=1, total_workouts>=1 (session with >=1 done exercise counted). (3) ROBUSTNESS: GET /api/plans/{id}/day?week=99&day=1 returns is_rest=true rest response with title='День отдыха', 0 exercises (no 500). GET /api/plans/{id}/week-progress?week=99 returns 200 with 7 days, all is_workout=false (no 500). Explicit rest day (day 2 in week 1) returns is_rest=true from day endpoint. POST /api/sessions/start on rest day returns 400 ('No workout scheduled for this day'). After starting session on workout day, GET /api/sessions/{id} -> session.date is non-null ISO date '2026-06-16' (YYYY-MM-DD format, 10 chars, valid ISO date). (4) GENERAL ASSERTIONS: All responses use UUID strings (36 chars with hyphens), no MongoDB _id leaks, ISO datetime strings. All 3 bugfix areas working correctly. Backend API fully functional for bugfix round."



  - agent: "main"
    message: "FRONTEND UI change (per user request) in components/DateSelector.js + DateSelector.css. Reverted week navigation back to the vertical DOT indicators (data-testid week-dots, dots week-dot-(-1)/0/1 = prev/current/next week) AND added a small horizontal 'План' button (data-testid plan-week-btn, bg #333333, text #959595) placed under the day-cards list. Tapping 'План' opens a week-picker modal (data-testid week-picker-modal, grid week-picker-grid, cells week-pick-N for N=1..weeks_count) to jump to ANY plan week; the current plan week is outlined and the viewed week is highlighted with the orange gradient. Selecting a week also shifts the selected day so its card stays highlighted. The dots + 'План' button only render when an active, published plan with >1 week exists. Compiles cleanly. NEEDS UI TESTING (awaiting user go-ahead). Suggested flow: register email user -> /programs choose 'full-body-beginner' (4 weeks) -> back home -> verify 3 week-dots on the left of the cards and a 'План' button below; tap a dot to switch weeks; tap 'План' -> pick week 4 -> selector jumps to week 4."

