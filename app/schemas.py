from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator

Rol = Literal["admin", "vendedor", "almacenero", "contador"]
TipoDoc = Literal["DNI", "RUC", "CE", "PASAPORTE"]
Comprobante = Literal["BOLETA", "FACTURA", "NOTA_VENTA"]
Metodo = Literal["EFECTIVO", "TARJETA", "YAPE", "PLIN", "TRANSFERENCIA"]


# ---------- Auth / usuarios ----------
class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    nombres: str = Field(min_length=1)
    apellidos: str = ""


class UsuarioUpdate(BaseModel):
    rol: Rol | None = None
    activo: bool | None = None
    nombres: str | None = None
    apellidos: str | None = None
    telefono: str | None = None
    meta_mensual: float | None = Field(None, ge=0)


# ---------- Catálogo ----------
class CategoriaIn(BaseModel):
    nombre: str = Field(min_length=1)
    descripcion: str | None = None


class MarcaIn(BaseModel):
    nombre: str = Field(min_length=1)


class ProductoIn(BaseModel):
    sku: str = Field(min_length=1)
    nombre: str = Field(min_length=1)
    descripcion: str | None = None
    categoria_id: int | None = None
    marca_id: int | None = None
    proveedor_id: int | None = None
    numero_parte: str | None = None
    especificaciones: dict = {}
    datasheet_url: str | None = None
    imagen_url: str | None = None
    precio_compra: float = Field(0, ge=0)
    precio_venta: float = Field(ge=0)  # sin IGV
    stock_minimo: int = Field(5, ge=0)
    ubicacion: str | None = None


class ProductoUpdate(BaseModel):
    sku: str | None = None
    nombre: str | None = None
    descripcion: str | None = None
    categoria_id: int | None = None
    marca_id: int | None = None
    proveedor_id: int | None = None
    numero_parte: str | None = None
    especificaciones: dict | None = None
    datasheet_url: str | None = None
    imagen_url: str | None = None
    precio_compra: float | None = Field(None, ge=0)
    precio_venta: float | None = Field(None, ge=0)
    stock_minimo: int | None = Field(None, ge=0)
    ubicacion: str | None = None
    activo: bool | None = None


class AjusteStockIn(BaseModel):
    tipo: Literal["ENTRADA", "AJUSTE"]
    cantidad: int  # ENTRADA > 0 ; AJUSTE puede ser negativo
    motivo: str = Field(min_length=3)

    @model_validator(mode="after")
    def validar(self):
        if self.cantidad == 0:
            raise ValueError("La cantidad no puede ser 0")
        if self.tipo == "ENTRADA" and self.cantidad < 0:
            raise ValueError("Una ENTRADA debe ser positiva (use AJUSTE para restar)")
        return self


# ---------- Clientes ----------
class ClienteIn(BaseModel):
    tipo_doc: TipoDoc = "DNI"
    numero_doc: str = Field(min_length=1)
    nombre: str = Field(min_length=1)
    direccion: str | None = None
    telefono: str | None = None
    email: EmailStr | None = None

    @model_validator(mode="after")
    def validar_doc(self):
        if self.tipo_doc == "DNI" and not (self.numero_doc.isdigit() and len(self.numero_doc) == 8):
            raise ValueError("El DNI debe tener 8 dígitos")
        if self.tipo_doc == "RUC" and not (self.numero_doc.isdigit() and len(self.numero_doc) == 11):
            raise ValueError("El RUC debe tener 11 dígitos")
        return self


class ClienteUpdate(BaseModel):
    nombre: str | None = None
    direccion: str | None = None
    telefono: str | None = None
    email: EmailStr | None = None


# ---------- Ventas ----------
class ItemIn(BaseModel):
    producto_id: int
    cantidad: int = Field(gt=0)
    descuento: float = Field(0, ge=0)


class PagoIn(BaseModel):
    metodo: Metodo
    monto: float = Field(gt=0)
    referencia: str | None = None


class VentaIn(BaseModel):
    comprobante: Comprobante = "BOLETA"
    cliente_id: int | None = None
    items: list[ItemIn] = Field(min_length=1)
    pagos: list[PagoIn] = []
    observaciones: str | None = None


