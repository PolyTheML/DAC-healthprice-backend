import os
import datetime

import jwt
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-in-prod")
JWT_ALG = "HS256"
JWT_EXP_HOURS = 8

# Credentials read from environment variables.
# Set ADMIN_PASSWORD, UW_PASSWORD, ANALYST_PASSWORD on Render.
# Defaults are for local dev only — always override in production.
USERS = {
    "admin":       {"password": os.getenv("ADMIN_PASSWORD", "admin123"),     "role": "admin"},
    "underwriter": {"password": os.getenv("UW_PASSWORD", "uw123"),           "role": "underwriter"},
    "analyst":     {"password": os.getenv("ANALYST_PASSWORD", "analyst123"), "role": "analyst"},
}


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginRequest):
    user = USERS.get(body.username.strip().lower())
    if not user or user["password"] != body.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    payload = {
        "sub": body.username,
        "role": user["role"],
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=JWT_EXP_HOURS),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)
    return {"access_token": token, "role": user["role"], "username": body.username}
