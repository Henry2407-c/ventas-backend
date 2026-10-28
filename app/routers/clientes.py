import re

from fastapi import APIRouter, Depends, HTTPException, Query
from postgrest.exceptions import APIError

from app.deps import db, raise_db_error, require_roles
from app.schemas import ClienteIn, ClienteUpdate

router = APIRouter(prefix="/clientes", tags=["Clientes"])
LECTURA = require_roles("admin", "vendedor", "contador")
ESCRITURA = require_roles("admin", "vendedor")


@router.get("")
def listar(q: str | None = None, limit: int = Query(50, ge=1, le=200),
           offset: int = Query(0, ge=0), _: dict = Depends(LECTURA)):
    query = db.table("clientes").select("*")
    if q:
        t = re.sub(r"[,()%*]", " ", q).strip()
        query = query.or_(f"nombre.ilike.%{t}%,numero_doc.ilike.%{t}%")
    return query.order("nombre").range(offset, offset + limit - 1).execute().data


@router.get("/documento/{numero_doc}")
def por_documento(numero_doc: str, _: dict = Depends(LECTURA)):
    res = db.table("clientes").select("*").eq("numero_doc", numero_doc).execute()
    if not res.data:
        raise HTTPException(404, "Cliente no encontrado")
    return res.data[0]


@router.get("/{cid}")
def obtener(cid: int, _: dict = Depends(LECTURA)):
    res = db.table("clientes").select("*").eq("id", cid).execute()
    if not res.data:
        raise HTTPException(404, "Cliente no encontrado")
    return res.data[0]


@router.post("", status_code=201)
def crear(data: ClienteIn, user: dict = Depends(ESCRITURA)):
    try:
        return db.table("clientes").insert({**data.model_dump(), "created_by": user["id"]}).execute().data[0]
    except APIError as e:
        raise_db_error(e)


@router.put("/{cid}")
def actualizar(cid: int, data: ClienteUpdate, _: dict = Depends(ESCRITURA)):
    cambios = data.model_dump(exclude_unset=True)
    if not cambios:
        raise HTTPException(400, "Nada que actualizar")
    res = db.table("clientes").update(cambios).eq("id", cid).execute()
    if not res.data:
        raise HTTPException(404, "Cliente no encontrado")
    return res.data[0]