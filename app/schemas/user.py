from pydantic import BaseModel, EmailStr, Field, field_validator

import base64, binascii

# schemas.py
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=30, pattern=r"^[A-Za-z0-9]+$")
    club_name: str = Field(min_length=3, max_length=30, pattern=r"^[^0-9]+$")
    avatar: str = Field(description="Imagen PNG o JPG codificada en Base64")

    @field_validator("avatar") # Permite escribir tu propia regla de validación para un campo
    @classmethod
    def validar_avatar(cls, v: str) -> str:
        try:
            data = base64.b64decode(v, validate=True)
        except binascii.Error:
            raise ValueError("El avatar no es Base64 válido")
        if not (data.startswith(b"\x89PNG") or data.startswith(b"\xff\xd8\xff")):
            raise ValueError("El avatar debe ser PNG o JPG")
        return v
    
# Lo que devolvemos en GET/users/me
class UserOut(BaseModel):
    user_name: str
    user_email: str


class PasswordChange(BaseModel):
    old_password: str
    new_password: str
