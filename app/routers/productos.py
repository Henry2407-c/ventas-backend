import re

from fastapi import APIRouter, Depends, HTTPException, Query
from postgrest.exceptions import APIError

from app.deps import db, raise_db_error, require_roles
from app.schemas import AjusteStockIn, ProductoIn, ProductoUpdate

router = APIRouter(prefix="/productos", tags=["Productos"])
LECTURA = require_roles("admin", "vendedor", "almacenero")
ESCRITURA = require_roles("admin", "almacenero")


def _ocultar_costo(rows: list[dict], rol: str) -> list[dict]:
    """El vendedor no necesita ver el precio de compra."""
    if rol == "vendedor":
        for r in rows:
            r.pop("precio_compra", None)
    return rows


@router.get("")
def listar(
    q: str | None = None,
    categoria_id: int | None = None,
    marca_id: int | None = None,
    solo_activos: bool = True,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(LECTURA),
):
    query = db.table("productos").select("*, categorias(nombre), marcas(nombre)")
    if solo_activos:
        query = query.eq("activo", True)
    if categoria_id:
        query = query.eq("categoria_id", categoria_id)
    if marca_id:
        query = query.eq("marca_id", marca_id)
    if q:
        t = re.sub(r"[,()%*]", " ", q).strip()
        query = query.or_(f"nombre.ilike.%{t}%,sku.ilike.%{t}%,numero_parte.ilike.%{t}%")
    rows = query.order("nombre").range(offset, offset + limit - 1).execute().data
    return _ocultar_costo(rows, user["rol"])


@router.get("/{pid}")
def obtener(pid: int, user: dict = Depends(LECTURA)):
    res = db.table("productos").select("*, categorias(nombre), marcas(nombre)").eq("id", pid).execute()
    if not res.data:
        raise HTTPException(404, "Producto no encontrado")
    return _ocultar_costo(res.data, user["rol"])[0]


@router.post("", status_code=201)
def crear(data: ProductoIn, _: dict = Depends(ESCRITURA)):
    """El stock inicia en 0; usa /ajuste-stock (ENTRADA) para que quede en el kardex."""
    try:
        return db.table("productos").insert(data.model_dump()).execute().data[0]
    except APIError as e:
        raise_db_error(e)


@router.put("/{pid}")
def actualizar(pid: int, data: ProductoUpdate, _: dict = Depends(ESCRITURA)):
    cambios = data.model_dump(exclude_unset=True)
    if not cambios:
        raise HTTPException(400, "Nada que actualizar")
    try:
        res = db.table("productos").update(cambios).eq("id", pid).execute()
    except APIError as e:
        raise_db_error(e)
    if not res.data:
        raise HTTPException(404, "Producto no encontrado")
    return res.data[0]


@router.delete("/{pid}")
def desactivar(pid: int, _: dict = Depends(require_roles("admin"))):
    """Baja lógica: se conserva el historial de ventas."""
    res = db.table("productos").update({"activo": False}).eq("id", pid).execute()
    if not res.data:
        raise HTTPException(404, "Producto no encontrado")
    return {"mensaje": "Producto desactivado"}


@router.post("/{pid}/ajuste-stock", status_code=201)
def ajustar_stock(pid: int, data: AjusteStockIn, user: dict = Depends(ESCRITURA)):
    if not db.table("productos").select("id").eq("id", pid).execute().data:
        raise HTTPException(404, "Producto no encontrado")
    try:
        db.table("movimientos_inventario").insert({
            "producto_id": pid, "tipo": data.tipo, "cantidad": data.cantidad,
            "motivo": data.motivo, "usuario_id": user["id"],
        }).execute()
    except APIError as e:
        raise_db_error(e)
    return db.table("productos").select("id,sku,nombre,stock").eq("id", pid).execute().data[0]


@router.get("/{pid}/kardex")
def kardex(pid: int, limit: int = Query(100, ge=1, le=500),
           _: dict = Depends(require_roles("admin", "almacenero", "contador"))):
    return (db.table("movimientos_inventario").select("*").eq("producto_id", pid)
            .order("fecha", desc=True).limit(limit).execute().data)