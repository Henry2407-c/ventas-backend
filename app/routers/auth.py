from fastapi import APIRouter, HTTPException, Request

from app.config import settings
from app.deps import db, new_anon_client
from app.ratelimit import verificar
from app.schemas import LoginIn, RegisterIn

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/login")
def login(data: LoginIn, request: Request):
    ip = request.client.host if request.client else "desconocido"
    verificar(f"login-ip:{ip}", 10, 300)
    verificar(f"login-mail:{data.email.lower()}", 10, 600)

    anon = new_anon_client()
    try:
        res = anon.auth.sign_in_with_password({"email": data.email, "password": data.password})
    except Exception:
        raise HTTPException(401, "Correo o contraseña incorrectos")

    perfil = db.table("profiles").select("rol,activo,nombres,apellidos").eq("id", res.user.id).execute().data
    if not perfil or not perfil[0]["activo"]:
        raise HTTPException(403, "Tu usuario está pendiente de activación por un administrador")
    p = perfil[0]
    return {
        "access_token": res.session.access_token,
        "refresh_token": res.session.refresh_token,
        "token_type": "bearer",
        "expires_in": res.session.expires_in,
        "user": {"id": res.user.id, "email": res.user.email, "rol": p["rol"],
                 "nombre": f'{p["nombres"]} {p["apellidos"]}'.strip()},
    }


@router.post("/register", status_code=201)
def register(data: RegisterIn, request: Request):
    """Deshabilitado por defecto: los empleados los crea el admin en Usuarios."""
    if not settings.registro_publico:
        raise HTTPException(403, "El registro público está deshabilitado. Pide a un administrador que cree tu cuenta.")
    verificar(f"registro-ip:{request.client.host if request.client else '?'}", 5, 3600)
    anon = new_anon_client()
    try:
        anon.auth.sign_up({
            "email": data.email,
            "password": data.password,
            "options": {"data": {"nombres": data.nombres, "apellidos": data.apellidos}},
        })
    except Exception as e:
        raise HTTPException(400, f"No se pudo registrar: {e}")
    return {"mensaje": "Registro exitoso. Un administrador debe activar tu cuenta."}


@router.post("/refresh")
def refresh(refresh_token: str):
    anon = new_anon_client()
    try:
        res = anon.auth.refresh_session(refresh_token)
    except Exception:
        raise HTTPException(401, "Refresh token inválido")
    return {"access_token": res.session.access_token, "refresh_token": res.session.refresh_token}