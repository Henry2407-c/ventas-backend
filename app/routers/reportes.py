from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, Query

from app.deps import db, require_roles

router = APIRouter(prefix="/reportes", tags=["Reportes"])
VER = require_roles("admin", "contador")


def _rango(desde: date | None, hasta: date | None) -> tuple[str, str]:
    hasta = hasta or date.today()
    desde = desde or hasta.replace(day=1)
    return desde.isoformat(), hasta.isoformat()


@router.get("/stock-bajo")
def stock_bajo(_: dict = Depends(require_roles("admin", "almacenero"))):
    return db.table("v_stock_bajo").select("*").order("stock").execute().data


@router.get("/resumen-ventas")
def resumen_ventas(desde: date | None = None, hasta: date | None = None, _: dict = Depends(VER)):
    d, h = _rango(desde, hasta)
    rows = db.rpc("rpt_ventas_por_dia", {"p_desde": d, "p_hasta": h}).execute().data
    suma = lambda k: round(sum(float(r[k]) for r in rows), 2)
    return {"desde": d, "hasta": h, "cantidad_ventas": int(suma("cantidad_ventas")), "total": suma("total")}


@router.get("/ventas-por-dia")
def ventas_por_dia(desde: date | None = None, hasta: date | None = None, _: dict = Depends(VER)):
    d, h = _rango(desde, hasta)
    return db.rpc("rpt_ventas_por_dia", {"p_desde": d, "p_hasta": h}).execute().data


@router.get("/ventas-por-vendedor")
def ventas_por_vendedor(desde: date | None = None, hasta: date | None = None, _: dict = Depends(VER)):
    d, h = _rango(desde, hasta)
    return db.rpc("rpt_ventas_por_vendedor", {"p_desde": d, "p_hasta": h}).execute().data


@router.get("/top-productos")
def top_productos(desde: date | None = None, hasta: date | None = None,
                  limit: int = Query(10, ge=1, le=100), _: dict = Depends(VER)):
    d, h = _rango(desde, hasta)
    return db.rpc("rpt_top_productos", {"p_desde": d, "p_hasta": h, "p_limit": limit}).execute().data


@router.get("/ganancias")
def ganancias(desde: date | None = None, hasta: date | None = None, _: dict = Depends(VER)):
    d, h = _rango(desde, hasta)
    data = db.rpc("rpt_ganancias", {"p_desde": d, "p_hasta": h}).execute().data
    return {"desde": d, "hasta": h, **(data[0] if isinstance(data, list) and data else data)}


@router.get("/valor-inventario")
def valor_inventario(_: dict = Depends(VER)):
    data = db.rpc("rpt_valor_inventario", {}).execute().data
    return data[0] if isinstance(data, list) and data else data


LIMA = timezone(timedelta(hours=-5))


@router.get("/caja")
def caja(fecha: date | None = None, user: dict = Depends(require_roles("admin", "vendedor", "contador"))):
    """Cobros del día por método de pago. El vendedor solo ve los de sus ventas."""
    dia = fecha or datetime.now(LIMA).date()
    ini = datetime.combine(dia, time.min, tzinfo=LIMA)
    rows = (db.table("pagos")
            .select("id,metodo,monto,referencia,fecha,"
                    "ventas(id,serie,numero,estado,vendedor_id,clientes(nombre),"
                    "vendedor:profiles!vendedor_id(nombres,apellidos))")
            .gte("fecha", ini.isoformat())
            .lt("fecha", (ini + timedelta(days=1)).isoformat())
            .order("fecha").execute().data)

    detalle, por_metodo = [], {}
    for r in rows:
        v = r.get("ventas") or {}
        if v.get("estado") == "ANULADA":
            continue
        if user["rol"] == "vendedor" and v.get("vendedor_id") != user["id"]:
            continue
        monto = float(r["monto"])
        m = por_metodo.setdefault(r["metodo"], {"metodo": r["metodo"], "cantidad": 0, "total": 0.0})
        m["cantidad"] += 1
        m["total"] = round(m["total"] + monto, 2)
        vend = v.get("vendedor") or {}
        detalle.append({
            "hora": r["fecha"],
            "comprobante": f'{v.get("serie", "")}-{str(v.get("numero", "")).zfill(6)}',
            "cliente": (v.get("clientes") or {}).get("nombre") or "Cliente varios",
            "vendedor": f'{vend.get("nombres", "")} {vend.get("apellidos", "")}'.strip(),
            "metodo": r["metodo"],
            "referencia": r.get("referencia"),
            "monto": monto,
        })
    return {
        "fecha": dia.isoformat(),
        "total": round(sum(d["monto"] for d in detalle), 2),
        "cantidad": len(detalle),
        "por_metodo": sorted(por_metodo.values(), key=lambda x: -x["total"]),
        "detalle": detalle,
    }