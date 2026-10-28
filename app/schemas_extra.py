from datetime import date
from app.schemas import Rol
from pydantic import BaseModel, EmailStr, Field, field_validator


def _validar_ruc(v: str | None) -> str | None:
    if v is not None and not (v.isdigit() and len(v) == 11):
        raise ValueError("El RUC debe tener 11 dígitos")
    return v


class ProveedorIn(BaseModel):
    razon_social: str = Field(min_length=1)
    ruc: str | None = None
    contacto: str | None = None
    telefono: str | None = None
    email: EmailStr | None = None
    direccion: str | None = None

    _v = field_validator("ruc")(_validar_ruc)


class ProveedorUpdate(BaseModel):
    razon_social: str | None = None
    ruc: str | None = None
    contacto: str | None = None
    telefono: str | None = None
    email: EmailStr | None = None
    direccion: str | None = None
    activo: bool | None = None

    _v = field_validator("ruc")(_validar_ruc)


class CompraItemIn(BaseModel):
    producto_id: int
    cantidad: int = Field(gt=0)
    costo_unitario: float = Field(ge=0)  # sin IGV


class CompraIn(BaseModel):
    proveedor_id: int | None = None
    documento: str | None = None
    fecha: date | None = None
    items: list[CompraItemIn] = Field(min_length=1)
    observaciones: str | None = None


class DevolucionItemIn(BaseModel):
    venta_item_id: int
    cantidad: int = Field(gt=0)


class DevolucionIn(BaseModel):
    motivo: str = Field(min_length=3)
    items: list[DevolucionItemIn] = Field(min_length=1)


class UsuarioCrear(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    nombres: str = Field(min_length=1)
    apellidos: str = ""
    rol: Rol
    telefono: str | None = None
    meta_mensual: float | None = Field(None, ge=0)


class PasswordIn(BaseModel):
    password: str = Field(min_length=8)