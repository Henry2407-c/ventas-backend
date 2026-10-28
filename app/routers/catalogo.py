from fastapi import APIRouter, Depends
from postgrest.exceptions import APIError

from app.deps import db, get_current_user, raise_db_error, require_roles
from app.schemas import CategoriaIn, MarcaIn

router = APIRouter(tags=["Catálogo"])
ESCRITURA = require_roles("admin", "almacenero")


@router.get("/empresa")
def empresa(_: dict = Depends(get_current_user)):
    return db.table("empresa").select("*").eq("id", 1).execute().data[0]


@router.get("/categorias")
def listar_categorias(_: dict = Depends(get_current_user)):
    return db.table("categorias").select("*").eq("activo", True).order("nombre").execute().data


@router.post("/categorias", status_code=201)
def crear_categoria(data: CategoriaIn, _: dict = Depends(ESCRITURA)):
    try:
        return db.table("categorias").insert(data.model_dump()).execute().data[0]
    except APIError as e:
        raise_db_error(e)


@router.get("/marcas")
def listar_marcas(_: dict = Depends(get_current_user)):
    return db.table("marcas").select("*").order("nombre").execute().data


@router.post("/marcas", status_code=201)
def crear_marca(data: MarcaIn, _: dict = Depends(ESCRITURA)):
    try:
        return db.table("marcas").insert(data.model_dump()).execute().data[0]
    except APIError as e:
        raise_db_error(e)