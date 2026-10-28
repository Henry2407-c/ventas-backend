from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_url: str
    supabase_anon_key: str
    supabase_service_key: str
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    apis_net_token: str = ""
    entorno: str = "desarrollo"      # en el servidor: produccion
    registro_publico: bool = False   # los empleados los crea el admin desde el panel

    @property
    def es_produccion(self) -> bool:
        return self.entorno.lower() in ("produccion", "producción", "production")


settings = Settings()