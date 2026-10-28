from fastapi import APIRouter, Depends, HTTPException

from app.deps import db, get_current_user, require_roles
from app.schemas import UsuarioUpdate
from app.schemas_extra import PasswordIn, UsuarioCrear

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return user


@router.get("")
def listar(_: dict = Depends(require_roles("admin"))):
    perfiles = db.table("profiles").select("*").order("created_at", desc=True).execute().data
    try:  # agrega el correo desde auth
        emails = {u.id: u.email for u in db.auth.admin.list_users()}
        for p in perfiles:
            p["email"] = emails.get(p["id"])
    except Exception:
        pass
    return perfiles


@router.post("", status_code=201)
def crear(data: UsuarioCrear, _: dict = Depends(require_roles("admin"))):
    """Crea un empleado ya activo, con el rol y la contraseña inicial que define el admin."""
    try:
        res = db.auth.admin.create_user({
            "email": data.email,
            "password": data.password,
            "email_confirm": True,
            "user_metadata": {"nombres": data.nombres, "apellidos": data.apellidos},
        })
    except Exception as e:
        raise HTTPException(400, f"No se pudo crear el usuario: {e}")
    uid = res.user.id
    cambios = {"rol": data.rol, "activo": True, "telefono": data.telefono, "meta_mensual": data.meta_mensual}
    perfil = db.table("profiles").update(cambios).eq("id", uid).execute().data
    return perfil[0] if perfil else {"id": uid, **cambios}


@router.patch("/{user_id}")
def actualizar(user_id: str, data: UsuarioUpdate, admin: dict = Depends(require_roles("admin"))):
    cambios = data.model_dump(exclude_unset=True)
    if not cambios:
        raise HTTPException(400, "Nada que actualizar")
    if user_id == admin["id"] and (cambios.get("activo") is False or cambios.get("rol", "admin") != "admin"):
        raise HTTPException(400, "No puedes quitarte tu propio acceso de administrador")
    res = db.table("profiles").update(cambios).eq("id", user_id).execute()
    if not res.data:
        raise HTTPException(404, "Usuario no encontrado")
    return res.data[0]


@router.post("/{user_id}/password")
def cambiar_password(user_id: str, data: PasswordIn, _: dict = Depends(require_roles("admin"))):
    try:
        db.auth.admin.update_user_by_id(user_id, {"password": data.password})
    except Exception as e:
        raise HTTPException(400, f"No se pudo cambiar la contraseña: {e}")
    return {"mensaje": "Contraseña actualizada"}