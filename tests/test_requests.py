import time

from conftest import login
from models import Role, Status

VALID = {"title": "Broken ceiling light", "category": "Electrical", "location": "Block B, Room 204",
         "description": "The ceiling light flickers and then turns off completely.", "priority": "High"}


def submit_as_student(client, **overrides):
    login(client, "student1", "student123")
    return client.post("/requests/new", data={**VALID, **overrides})


# ---- positive cases -------------------------------------------------------
def test_tc01_student_submits_valid_request(app, client, record):
    resp = submit_as_student(client)
    req = app.repo.get_request(1)
    record("TC01", "Request is stored with status Open and the student is redirected to the list",
           f"HTTP {resp.status_code}; request #{req.id} stored with status {req.status.value}, "
           f"priority {req.priority}, submitted by {req.creator_name}")
    assert resp.status_code == 302
    assert req.status == Status.OPEN


def test_tc02_valid_login(client, record):
    resp = login(client, "student1", "student123")
    home = client.get("/")
    record("TC02", "Valid credentials log the user in and open the request list",
           f"HTTP {resp.status_code} redirect to {resp.headers['Location']}; list page returned HTTP {home.status_code}")
    assert resp.status_code == 302
    assert home.status_code == 200


def test_tc03_admin_assigns_open_request(app, client, record):
    submit_as_student(client)
    client.get("/logout")
    login(client, "admin", "admin123")
    staff = app.repo.get_user_by_username("staff1")
    client.post("/requests/1/assign", data={"staff_id": staff.id})
    req = app.repo.get_request(1)
    record("TC03", "Request becomes Assigned and shows the chosen staff member",
           f"Status {req.status.value}; assigned to {req.assignee_name}")
    assert req.status == Status.ASSIGNED
    assert req.assigned_to == staff.id


def test_tc04_staff_completes_workflow(app, client, record):
    submit_as_student(client)
    app.repo.assign_request(1, app.repo.get_user_by_username("staff1").id)
    client.get("/logout")
    login(client, "staff1", "staff123")
    client.post("/requests/1/status", data={"status": "In Progress"})
    mid = app.repo.get_request(1).status.value
    client.post("/requests/1/status", data={"status": "Resolved"})
    end = app.repo.get_request(1).status.value
    record("TC04", "Status moves Assigned, then In Progress, then Resolved",
           f"After first update: {mid}; after second update: {end}")
    assert (mid, end) == ("In Progress", "Resolved")


# ---- negative cases -------------------------------------------------------
def test_tc05_invalid_input_rejected(app, client, record):
    resp = submit_as_student(client, title="abc", description="short")
    stored = len(app.repo.list_requests())
    body = resp.get_data(as_text=True)
    shown = [m for m in ("Title must be between 5 and 100 characters.",
                         "Description must be at least 10 characters.") if m in body]
    record("TC05", "Form is rejected with validation messages and nothing is stored",
           f"HTTP {resp.status_code}; {len(shown)} validation messages shown; requests stored: {stored}")
    assert resp.status_code == 400
    assert stored == 0 and len(shown) == 2


def test_tc06_wrong_password_rejected(client, record):
    resp = login(client, "student1", "wrong-password")
    home = client.get("/")
    body = resp.get_data(as_text=True)
    record("TC06", "Login is refused with an error message and no session is created",
           f"HTTP {resp.status_code}; message 'Invalid username or password.' shown: "
           f"{'Invalid username or password.' in body}; list page redirects to {home.headers.get('Location')}")
    assert resp.status_code == 401
    assert home.status_code == 302


def test_tc07_student_cannot_view_others_request(app, client, record):
    submit_as_student(client)
    client.get("/logout")
    login(client, "student2", "student123")
    detail = client.get("/requests/1")
    listing = client.get("/").get_data(as_text=True)
    record("TC07", "Another student's request is refused and missing from the list",
           f"Detail page HTTP {detail.status_code}; request title in list: {VALID['title'] in listing}")
    assert detail.status_code == 403
    assert VALID["title"] not in listing


def test_tc08_invalid_status_transition_rejected(app, client, record):
    submit_as_student(client)
    app.repo.assign_request(1, app.repo.get_user_by_username("staff1").id)
    client.get("/logout")
    login(client, "staff1", "staff123")
    resp = client.post("/requests/1/status", data={"status": "Resolved"}, follow_redirects=True)
    status = app.repo.get_request(1).status.value
    ok = "Cannot change status from Assigned to Resolved." in resp.get_data(as_text=True)
    record("TC08", "Skipping a step is refused and the status stays Assigned",
           f"Error message shown: {ok}; status after attempt: {status}")
    assert ok and status == "Assigned"


def test_tc09_student_cannot_assign(app, client, record):
    submit_as_student(client)
    staff = app.repo.get_user_by_username("staff1")
    resp = client.post("/requests/1/assign", data={"staff_id": staff.id})
    req = app.repo.get_request(1)
    record("TC09", "A student is refused and the request stays Open and unassigned",
           f"HTTP {resp.status_code}; status {req.status.value}; assigned to: {req.assignee_name or 'nobody'}")
    assert resp.status_code in (302, 403)
    assert req.status == Status.OPEN and req.assigned_to is None


def test_tc10_unauthenticated_access_redirected(client, record):
    home = client.get("/")
    new = client.get("/requests/new")
    record("TC10", "Both pages redirect to the login page",
           f"List: HTTP {home.status_code} to {home.headers['Location']}; new request form: "
           f"HTTP {new.status_code} to {new.headers['Location']}")
    assert home.status_code == 302 and new.status_code == 302
    assert "/login" in home.headers["Location"] and "/login" in new.headers["Location"]


# ---- non-functional cases -------------------------------------------------
def test_tc11_passwords_are_hashed(app, record):
    user = app.repo.get_user_by_username("student1")
    record("TC11", "Stored password is a salted hash, not the plain text",
           f"Stored value starts with '{user.password_hash.split('$')[0]}'; equals plain text: "
           f"{user.password_hash == 'student123'}")
    assert user.password_hash != "student123"
    assert user.password_hash.startswith(("scrypt", "pbkdf2"))


def test_tc12_list_1000_requests_under_one_second(app, client, record):
    student = app.repo.get_user_by_username("student1")
    for i in range(1000):
        app.repo.add_request(f"Request number {i}", "Other", "Library", "Generated load test entry.", "Low", student.id)
    login(client, "admin", "admin123")
    start = time.perf_counter()
    resp = client.get("/")
    elapsed_ms = (time.perf_counter() - start) * 1000
    record("TC12", "Admin list page with 1000 requests responds in under 1000 ms",
           f"HTTP {resp.status_code}; response time {elapsed_ms:.0f} ms for 1000 requests")
    assert resp.status_code == 200
    assert elapsed_ms < 1000


def test_tc13_staff_cannot_update_unassigned_request(app, client, record):
    submit_as_student(client)
    app.repo.assign_request(1, app.repo.get_user_by_username("staff1").id)
    client.get("/logout")
    login(client, "staff2", "staff123")
    resp = client.post("/requests/1/status", data={"status": "In Progress"})
    status = app.repo.get_request(1).status.value
    record("TC13", "A staff member who is not assigned is refused and the status is unchanged",
           f"HTTP {resp.status_code}; status after attempt: {status}")
    assert resp.status_code == 403
    assert status == "Assigned"
