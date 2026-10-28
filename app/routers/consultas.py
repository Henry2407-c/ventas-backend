from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from postgrest.exceptions import APIError
from pydantic import BaseModel

from app.deps import db, raise_db_error, require_roles
from app.services import lookup

router = APIRouter(prefix="/consultas", tags=["Consulta RUC / DNI"])
PUEDE = require_roles("admin", "vendedor")


def _validar(tipo: str, numero: str) -> None:
    largo = 11 if tipo == "RUC" else 8
    if not (numero.isdigit() and len(numero) == largo):
        raise HTTPException(400, f"El {tipo} debe tener {largo} dígitos")


@router.get("/ruc/{ruc}")
def consultar_ruc(ruc: str, _: dict = Depends(PUEDE)):
    _validar("RUC", ruc)
    return lookup.consultar_ruc(ruc)


@router.get("/dni/{dni}")
def consultar_dni(dni: str, _: dict = Depends(PUEDE)):
    _validar("DNI", dni)
    return lookup.consultar_dni(dni)


class ClienteDesdeDocumento(BaseModel):
    tipo_doc: Literal["DNI", "RUC"]
    numero_doc: str


@router.post("/crear-cliente")
def crear_cliente(data: ClienteDesdeDocumento, user: dict = Depends(PUEDE)):
    """Busca el cliente en tu base; si no existe, lo consulta y lo crea."""
    _validar(data.tipo_doc, data.numero_doc)
    existente = (db.table("clientes").select("*")
                 .eq("tipo_doc", data.tipo_doc).eq("numero_doc", data.numero_doc).execute().data)
    if existente:
        return {"origen": "base_de_datos", "cliente": existente[0]}

    info = (lookup.consultar_ruc(data.numero_doc) if data.tipo_doc == "RUC"
            else lookup.consultar_dni(data.numero_doc))
    if not info.get("nombre"):
        raise HTTPException(502, "El servicio no devolvió el nombre. Revisa la respuesta en /consultas/ruc o /consultas/dni")
    try:
        nuevo = db.table("clientes").insert({
            "tipo_doc": data.tipo_doc,
            "numero_doc": data.numero_doc,
            "nombre": info["nombre"],
            "direccion": info.get("direccion"),
            "created_by": user["id"],
        }).execute().data[0]
    except APIError as e:
        raise_db_error(e)
    return {"origen": "api_externa", "cliente": nuevo}