"""Domain model for the Campus Service Request System."""
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Role(str, Enum):
    STUDENT = "student"
    STAFF = "staff"
    ADMIN = "admin"


class Status(str, Enum):
    OPEN = "Open"
    ASSIGNED = "Assigned"
    IN_PROGRESS = "In Progress"
    RESOLVED = "Resolved"


CATEGORIES = ["Electrical", "Plumbing", "IT / Network", "Furniture", "Cleaning", "Other"]
PRIORITIES = ["Low", "Medium", "High"]

# A request may only move forward one step at a time.
_TRANSITIONS = {
    Status.OPEN: {Status.ASSIGNED},
    Status.ASSIGNED: {Status.IN_PROGRESS},
    Status.IN_PROGRESS: {Status.RESOLVED},
    Status.RESOLVED: set(),
}


@dataclass
class User:
    id: int
    username: str
    full_name: str
    role: Role
    password_hash: str = ""


@dataclass
class ServiceRequest:
    id: int
    title: str
    category: str
    location: str
    description: str
    priority: str
    status: Status
    created_by: int
    assigned_to: Optional[int]
    created_at: str
    updated_at: str
    creator_name: str = ""
    assignee_name: str = ""

    def can_move_to(self, new_status: Status) -> bool:
        return new_status in _TRANSITIONS[self.status]
