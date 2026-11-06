"""Colecciones ordenadas por preferencia; cambios invalidan el índice de caché."""
import os
import re

DEFAULT_COLLECTIONS = ("spherex_qr3", "spherex_qr3_deep", "spherex_qr2", "spherex_qr2_deep")


def read_collections(value=None):
    values = tuple(part.strip() for part in (value or ",".join(DEFAULT_COLLECTIONS)).split(","))
    if not values or len(set(values)) != len(values) or any(
            not re.fullmatch(r"spherex_qr[0-9]+(?:_deep)?", part) for part in values):
        raise ValueError("ORBITLENS_COLLECTIONS debe contener colecciones SPHEREx únicas separadas por comas.")
    return values


COLLECTIONS = read_collections(os.environ.get("ORBITLENS_COLLECTIONS"))
