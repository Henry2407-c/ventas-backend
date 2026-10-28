import time
from collections import defaultdict, deque

from fastapi import HTTPException

_hits: dict[str, deque] = defaultdict(deque)


def verificar(clave: str, maximo: int, ventana: int) -> None:
    """Permite `maximo` intentos cada `ventana` segundos por clave (en memoria, una sola instancia)."""
    ahora = time.time()
    q = _hits[clave]
    while q and ahora - q[0] > ventana:
        q.popleft()
    if len(q) >= maximo:
        raise HTTPException(429, "Demasiados intentos. Espera unos minutos e inténtalo de nuevo.")
    q.append(ahora)
    if len(_hits) > 5000:  # limpieza básica para no crecer sin límite
        for k in [k for k, v in _hits.items() if not v or ahora - v[-1] > 3600]:
            _hits.pop(k, None)