from pydantic import BaseModel, EmailStr


class InviteUserRequest(BaseModel):
    email: EmailStr
    name: str
    role: str = "member"  # admin | member


class UpdateUserRequest(BaseModel):
    role: str | None = None
    is_active: bool | None = None
