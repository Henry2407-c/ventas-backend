from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from postgrest.exceptions import APIError
from supabase import Client, create_client

from app.config import settings

# Cliente con service_role: SOLO backend. Se salta el RLS, por eso los permisos
# se controlan aquí con require_roles().
db: Client = create_client(settings.supabase_url, settings.supabase_service_key)

bearer = HTTPBearer(auto_error=False)


def new_anon_client() -> Client:
    """Cliente nuevo por login para no compartir sesión entre usuarios."""
    return create_client(settings.supabase_url, settings.supabase_anon_key)


def get_current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if not creds:
        raise HTTPException(401, "Falta el token de autenticación")
    try:
        user = db.auth.get_user(creds.credentials).user
    except Exception:
        raise HTTPException(401, "Token inválido o expirado")
    if not user:
        raise HTTPException(401, "Token inválido o expirado")

    res = db.table("profiles").select("rol,activo,nombres,apellidos,meta_mensual").eq("id", user.id).execute()
    if not res.data:
        raise HTTPException(403, "Perfil no encontrado")
    p = res.data[0]
    if not p["activo"]:
        raise HTTPException(403, "Tu usuario está pendiente de activación por un administrador")

    return {
        "id": user.id,
        "email": user.email,
        "rol": p["rol"],
        "nombre": f'{p["nombres"]} {p["apellidos"]}'.strip(),
        "meta_mensual": p.get("meta_mensual"),
    }


def require_roles(*roles: str):
    def checker(user: dict = Depends(get_current_user)) -> dict:
        if user["rol"] not in roles:
            raise HTTPException(403, "No tienes permiso para esta acción")
        return user

    return checker


def raise_db_error(e: APIError):
    msg = getattr(e, "message", None) or str(e)
    if "productos_stock_check" in msg:
        detail = "Stock insuficiente para uno o más productos"
    elif "duplicate key" in msg or "unique constraint" in msg:
        detail = "Ya existe un registro con esos datos"
    elif "violates foreign key" in msg:
        detail = "Referencia inválida (el registro relacionado no existe o está en uso)"
    else:
        detail = msg
    raise HTTPException(400, detail)