"""Business rules: validation, permissions and the request workflow."""
from typing import List, Optional

from werkzeug.security import check_password_hash, generate_password_hash

from models import CATEGORIES, PRIORITIES, Role, ServiceRequest, Status, User
from repository import Repository


class ValidationError(Exception):
    def __init__(self, errors: List[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


class PermissionDenied(Exception):
    pass


class NotFound(Exception):
    pass


class AuthService:
    def __init__(self, repo: Repository):
        self.repo = repo

    def create_user(self, username: str, password: str, full_name: str, role: Role) -> User:
        return self.repo.add_user(username, full_name, role, generate_password_hash(password))

    def authenticate(self, username: str, password: str) -> Optional[User]:
        user = self.repo.get_user_by_username((username or "").strip())
        if user and check_password_hash(user.password_hash, password or ""):
            return user
        return None


class RequestService:
    def __init__(self, repo: Repository):
        self.repo = repo

    def submit(self, user: User, title: str, category: str, location: str,
               description: str, priority: str) -> ServiceRequest:
        if user.role != Role.STUDENT:
            raise PermissionDenied("Only students can submit service requests.")
        title, location, description = (title or "").strip(), (location or "").strip(), (description or "").strip()
        errors = []
        if not 5 <= len(title) <= 100:
            errors.append("Title must be between 5 and 100 characters.")
        if category not in CATEGORIES:
            errors.append("Please choose a valid category.")
        if not location:
            errors.append("Location is required.")
        if len(description) < 10:
            errors.append("Description must be at least 10 characters.")
        if priority not in PRIORITIES:
            errors.append("Please choose a valid priority.")
        if errors:
            raise ValidationError(errors)
        rid = self.repo.add_request(title, category, location, description, priority, user.id)
        return self.repo.get_request(rid)

    def visible_requests(self, user: User, status: Optional[str] = None) -> List[ServiceRequest]:
        if user.role == Role.ADMIN:
            return self.repo.list_requests(status=status)
        if user.role == Role.STAFF:
            return self.repo.list_requests(assigned_to=user.id, status=status)
        return self.repo.list_requests(created_by=user.id, status=status)

    def get_request(self, user: User, request_id: int) -> ServiceRequest:
        req = self.repo.get_request(request_id)
        if req is None:
            raise NotFound("Request not found.")
        allowed = (user.role == Role.ADMIN
                   or (user.role == Role.STUDENT and req.created_by == user.id)
                   or (user.role == Role.STAFF and req.assigned_to == user.id))
        if not allowed:
            raise PermissionDenied("You do not have access to this request.")
        return req

    def assign(self, user: User, request_id: int, staff_id: int) -> ServiceRequest:
        if user.role != Role.ADMIN:
            raise PermissionDenied("Only administrators can assign requests.")
        req = self.get_request(user, request_id)
        staff = self.repo.get_user(staff_id)
        if staff is None or staff.role != Role.STAFF:
            raise ValidationError(["Please choose a valid staff member."])
        if req.status != Status.OPEN:
            raise ValidationError(["Only open requests can be assigned."])
        self.repo.assign_request(request_id, staff_id)
        return self.repo.get_request(request_id)

    def update_status(self, user: User, request_id: int, new_status: str) -> ServiceRequest:
        req = self.get_request(user, request_id)
        if user.role != Role.STAFF:
            raise PermissionDenied("Only the assigned staff member can update the status.")
        try:
            target = Status(new_status)
        except ValueError:
            raise ValidationError(["Unknown status."])
        if not req.can_move_to(target):
            raise ValidationError([f"Cannot change status from {req.status.value} to {target.value}."])
        self.repo.set_status(request_id, target)
        return self.repo.get_request(request_id)
