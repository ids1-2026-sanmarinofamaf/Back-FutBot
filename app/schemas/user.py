from pydantic import BaseModel, EmailStr

# schemas.py
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    club_name: str
    avatar: str

# Lo que devolvemos en GET/users/me
class UserOut(BaseModel):
    user_name: str
    user_email: str


class PasswordChange(BaseModel):
    old_password: str
    new_password: str
