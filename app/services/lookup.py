import httpx
from fastapi import HTTPException

from app.config import settings

BASE = "https://api.apis.net.pe/v2"


def _get(path: str, numero: str) -> dict:
    if not settings.apis_net_token:
        raise HTTPException(503, "Consulta RUC/DNI no configurada (falta APIS_NET_TOKEN en el .env)")
    try:
        r = httpx.get(
            f"{BASE}{path}",
            params={"numero": numero},
            headers={"Accept": "application/json", "Authorization": f"Bearer {settings.apis_net_token}"},
            timeout=15,
        )
    except httpx.HTTPError:
        raise HTTPException(502, "No se pudo conectar con el servicio de consulta")
    if r.status_code in (404, 422):
        raise HTTPException(404, "Documento no encontrado")
    if r.status_code in (401, 403):
        raise HTTPException(502, "Token de consulta inválido o sin permisos")
    if r.status_code == 429:
        raise HTTPException(429, "Se alcanzó el límite de consultas del proveedor")
    if r.status_code != 200:
        raise HTTPException(502, f"Error del servicio de consulta ({r.status_code})")
    return r.json()


def consultar_ruc(ruc: str) -> dict:
    data = _get("/sunat/ruc", ruc)
    return {
        "tipo_doc": "RUC",
        "numero_doc": ruc,
        "nombre": data.get("razonSocial") or data.get("nombre"),
        "direccion": data.get("direccion"),
        "estado": data.get("estado"),
        "condicion": data.get("condicion"),
        "raw": data,
    }


def consultar_dni(dni: str) -> dict:
    data = _get("/reniec/dni", dni)
    nombre = data.get("nombreCompleto") or " ".join(
        x for x in (data.get("nombres"), data.get("apellidoPaterno"), data.get("apellidoMaterno")) if x
    )
    return {"tipo_doc": "DNI", "numero_doc": dni, "nombre": nombre or None, "direccion": None, "raw": data}