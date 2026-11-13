import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402

RESULTS = {}


@pytest.fixture
def app(tmp_path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.db"), "SECRET_KEY": "test"})


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, username, password):
    return client.post("/login", data={"username": username, "password": password})


@pytest.fixture
def record():
    """Store the expected and the actually observed result of a test case."""
    def _record(tc_id, expected, actual):
        RESULTS.setdefault(tc_id, {}).update(expected=expected, actual=actual)
    return _record


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" and item.name.startswith("test_tc"):
        tc_id = item.name.split("_")[1].upper()
        RESULTS.setdefault(tc_id, {})["status"] = "Pass" if report.passed else "Fail"
        RESULTS[tc_id]["test"] = item.name


def pytest_sessionfinish(session, exitstatus):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.json")
    with open(path, "w") as fh:
        json.dump(dict(sorted(RESULTS.items())), fh, indent=2)
