"""Entrada ICRS: números en grados; RA sexagesimal en horas salvo unidad explícita."""

import math
import re

import astropy.units as u
from astropy.coordinates import Angle


def parse_coordinates(ra: str | float, dec: str | float) -> tuple[float, float]:
    def parse(value, right_ascension):
        text = str(value).strip()
        if not text or len(text) > 100:
            raise ValueError("Introduce RA y Dec en grados o formato sexagesimal.")
        try:
            degrees = float(text)
        except ValueError:
            # 08:55:10 o 08h55m10s son horas; 133d45m tiene unidad angular explícita.
            unit = u.hourangle if right_ascension and not re.search(r"[d°]", text.lower()) else u.deg
            degrees = float(Angle(text, unit=unit).degree)
        if not math.isfinite(degrees):
            raise ValueError("Las coordenadas deben ser finitas.")
        if right_ascension and not 0 <= degrees < 360:
            raise ValueError("RA debe estar en [0, 360) grados o [0, 24) horas.")
        if not right_ascension and not -90 <= degrees <= 90:
            raise ValueError("Dec debe estar entre −90 y +90 grados.")
        return degrees

    return parse(ra, True), parse(dec, False)
