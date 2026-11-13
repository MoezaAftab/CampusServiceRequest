# Campus Service Request System

A small web application where students report campus problems (electrical, plumbing, IT, furniture, cleaning),
administrators assign them to staff, and staff update the progress until they are resolved.

Course: SW315 Software Construction and Development, Lab 16 (Complex Engineering Problem)
Department of Software Engineering, Mehran University of Engineering and Technology, Jamshoro

## Roles

| Role | Can do |
|---|---|
| Student | Submit requests, see only their own requests and their status |
| Administrator | See all requests, assign an open request to a staff member |
| Staff | See requests assigned to them, move them Assigned -> In Progress -> Resolved |

## Run locally

```bash
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000 and log in with a demo account:

| Username | Password | Role |
|---|---|---|
| student1 | student123 | Student |
| student2 | student123 | Student |
| staff1 | staff123 | Staff |
| staff2 | staff123 | Staff |
| admin | admin123 | Administrator |

These accounts exist for demonstration only. Set `SECRET_KEY` and create real users before any real use.

## Run the tests

```bash
python -m pytest -v
```

13 test cases cover valid and invalid input, access control, the status workflow, password hashing and response time
for 1000 requests. The same command runs on every push through GitHub Actions (`.github/workflows/ci.yml`).

## Structure

| File | Purpose |
|---|---|
| `models.py` | Roles, statuses, `User` and `ServiceRequest`, allowed status transitions |
| `repository.py` | SQLite data access (all SQL) |
| `services.py` | Validation, permissions and workflow rules (`AuthService`, `RequestService`) |
| `app.py` | Flask routes and templates |
| `tests/` | pytest test cases |
