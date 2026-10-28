from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from postgrest.exceptions import APIError
from pydantic import BaseModel, Field

from app.deps import db, raise_db_error, require_roles
from app.schemas import Metodo

router = APIRouter(prefix="/pedidos", tags=["Pedidos web"])
PUEDE = require_roles("admin", "vendedor")
SERIES = {"BOLETA": "B001", "FACTURA": "F001", "NOTA_VENTA": "N001"}
SELECT = "*, pedido_items(*, productos(sku,nombre)), atendido:profiles!atendido_por(nombres,apellidos)"


class EstadoIn(BaseModel):
    estado: Literal["NUEVO", "CONFIRMADO", "CANCELADO"]
    motivo: str | None = Field(None, max_length=300)


class ConvertirIn(BaseModel):
    comprobante: Literal["BOLETA", "FACTURA", "NOTA_VENTA"] = "BOLETA"
    cliente_id: int | None = None
    metodo_pago: Metodo | None = None  # si viene, se registra el pago completo


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pedido(pid: int) -> dict:
    res = db.table("pedidos").select(SELECT).eq("id", pid).execute()
    if not res.data:
        raise HTTPException(404, "Pedido no encontrado")
    return res.data[0]


def _cliente_desde_pedido(p: dict, user: dict) -> int | None:
    if not (p.get("tipo_doc") and p.get("numero_doc")):
        return None
    ex = (db.table("clientes").select("id")
          .eq("tipo_doc", p["tipo_doc"]).eq("numero_doc", p["numero_doc"]).execute().data)
    if ex:
        return ex[0]["id"]
    return db.table("clientes").insert({
        "tipo_doc": p["tipo_doc"], "numero_doc": p["numero_doc"], "nombre": p["nombre"],
        "direccion": p.get("direccion"), "telefono": p["telefono"], "email": p.get("email"),
        "created_by": user["id"],
    }).execute().data[0]["id"]


@router.get("")
def listar(
    estado: str | None = Query(None, pattern="^(NUEVO|CONFIRMADO|CONVERTIDO|CANCELADO)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: dict = Depends(PUEDE),
):
    q = db.table("pedidos").select(SELECT)
    if estado:
        q = q.eq("estado", estado)
    return q.order("created_at", desc=True).range(offset, offset + limit - 1).execute().data


@router.get("/{pid}")
def obtener(pid: int, _: dict = Depends(PUEDE)):
    return _pedido(pid)


def _cancelar_convertido(p: dict, data: EstadoIn, user: dict) -> dict:
    """Cancela un pedido que ya era venta: anula la venta (el trigger devuelve el stock) y registra la cancelación."""
    if user["rol"] != "admin":
        raise HTTPException(403, "Solo un administrador puede cancelar un pedido ya convertido en venta")
    if not (data.motivo and len(data.motivo.strip()) >= 3):
        raise HTTPException(400, "Indica el motivo de la cancelación")
    venta_id = p.get("venta_id")
    if venta_id:
        v = db.table("ventas").select("estado").eq("id", venta_id).execute().data
        if v and v[0]["estado"] != "ANULADA":
            try:
                db.table("ventas").update({"estado": "ANULADA"}).eq("id", venta_id).execute()
            except APIError as e:
                raise_db_error(e)
    db.table("pedidos").update({
        "estado": "CANCELADO",
        "motivo_cancelacion": data.motivo.strip(),
        "atendido_por": user["id"],
        "atendido_en": _ahora(),
    }).eq("id", p["id"]).execute()
    return _pedido(p["id"])


@router.patch("/{pid}/estado")
def cambiar_estado(pid: int, data: EstadoIn, user: dict = Depends(PUEDE)):
    p = _pedido(pid)
    if data.estado == "NUEVO":  # reabrir un pedido cancelado
        if p["estado"] != "CANCELADO":
            raise HTTPException(400, "Solo se puede reabrir un pedido cancelado")
        cambios = {"estado": "NUEVO", "motivo_cancelacion": None, "atendido_por": None,
                   "atendido_en": None, "venta_id": None}
    else:
        if data.estado == "CANCELADO" and p["estado"] == "CONVERTIDO":
            return _cancelar_convertido(p, data, user)
        if p["estado"] not in ("NUEVO", "CONFIRMADO"):
            raise HTTPException(400, f"El pedido ya está {p['estado'].lower()}")
        if data.estado == "CANCELADO" and not (data.motivo and len(data.motivo.strip()) >= 3):
            raise HTTPException(400, "Indica el motivo de la cancelación")
        cambios = {
            "estado": data.estado,
            "atendido_por": user["id"],
            "atendido_en": _ahora(),
            "motivo_cancelacion": data.motivo.strip() if data.estado == "CANCELADO" else None,
        }
    db.table("pedidos").update(cambios).eq("id", pid).execute()
    return _pedido(pid)


@router.post("/{pid}/convertir")
def convertir(pid: int, data: ConvertirIn, user: dict = Depends(PUEDE)):
    """Convierte el pedido en una venta (descuenta stock y calcula IGV con los precios actuales)."""
    p = _pedido(pid)
    if p["estado"] not in ("NUEVO", "CONFIRMADO"):
        raise HTTPException(400, f"El pedido ya está {p['estado'].lower()}")
    try:
        cliente_id = data.cliente_id or _cliente_desde_pedido(p, user)
        res = db.rpc("crear_venta", {
            "p_vendedor_id": user["id"],
            "p_comprobante": data.comprobante,
            "p_serie": SERIES[data.comprobante],
            "p_cliente_id": cliente_id,
            "p_items": [{"producto_id": i["producto_id"], "cantidad": i["cantidad"]} for i in p["pedido_items"]],
            "p_pagos": [],
            "p_observaciones": f"Pedido web #{pid} - {p['nombre']} ({p['telefono']})",
        }).execute()
        venta_id = res.data
        if data.metodo_pago:
            total = db.table("ventas").select("total").eq("id", venta_id).execute().data[0]["total"]
            db.table("pagos").insert({"venta_id": venta_id, "metodo": data.metodo_pago,
                                      "monto": total, "referencia": f"Pedido web #{pid}"}).execute()
    except APIError as e:
        raise_db_error(e)
    db.table("pedidos").update({
        "estado": "CONVERTIDO", "venta_id": venta_id, "atendido_por": user["id"], "atendido_en": _ahora(),
    }).eq("id", pid).execute()
    return {"pedido": _pedido(pid), "venta_id": venta_id}