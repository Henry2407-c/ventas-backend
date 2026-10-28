import re

from fastapi import APIRouter, Depends, HTTPException
from postgrest.exceptions import APIError

from app.deps import db, raise_db_error, require_roles
from app.schemas_extra import ProveedorIn, ProveedorUpdate

router = APIRouter(prefix="/proveedores", tags=["Proveedores"])
LECTURA = require_roles("admin", "almacenero", "contador")
ESCRITURA = require_roles("admin", "almacenero")


@router.get("")
def listar(q: str | None = None, solo_activos: bool = True, _: dict = Depends(LECTURA)):
    query = db.table("proveedores").select("*")
    if solo_activos:
        query = query.eq("activo", True)
    if q:
        t = re.sub(r"[,()%*]", " ", q).strip()
        query = query.or_(f"razon_social.ilike.%{t}%,ruc.ilike.%{t}%")
    return query.order("razon_social").execute().data


@router.get("/{pid}")
def obtener(pid: int, _: dict = Depends(LECTURA)):
    res = db.table("proveedores").select("*").eq("id", pid).execute()
    if not res.data:
        raise HTTPException(404, "Proveedor no encontrado")
    return res.data[0]


@router.post("", status_code=201)
def crear(data: ProveedorIn, _: dict = Depends(ESCRITURA)):
    try:
        return db.table("proveedores").insert(data.model_dump()).execute().data[0]
    except APIError as e:
        raise_db_error(e)


@router.put("/{pid}")
def actualizar(pid: int, data: ProveedorUpdate, _: dict = Depends(ESCRITURA)):
    cambios = data.model_dump(exclude_unset=True)
    if not cambios:
        raise HTTPException(400, "Nada que actualizar")
    try:
        res = db.table("proveedores").update(cambios).eq("id", pid).execute()
    except APIError as e:
        raise_db_error(e)
    if not res.data:
        raise HTTPException(404, "Proveedor no encontrado")
    return res.data[0]


@router.delete("/{pid}")
def desactivar(pid: int, _: dict = Depends(require_roles("admin"))):
    res = db.table("proveedores").update({"activo": False}).eq("id", pid).execute()
    if not res.data:
        raise HTTPException(404, "Proveedor no encontrado")
    return {"mensaje": "Proveedor desactivado"}