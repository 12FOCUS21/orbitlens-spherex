"""Resolución SIMBAD con posición ICRS y movimiento propio desde J2000."""

import io
import math
import sys
from xml.etree import ElementTree

import astropy.units as u
import httpx
import numpy as np
from astropy.coordinates import SkyCoord
from astropy.io.votable import parse_single_table
from astropy.time import Time


PRESETS = {
    "barnard": "Barnard's Star",
    "epsilon-indi-b": "eps Ind B",
    "wise0855": "WISE J085510.83-071442.5",
    "rw-aur": "RW Aur",
    "r-dra": "R Dra",
}
SIMBAD_TAP = "https://simbad.cds.unistra.fr/simbad/sim-tap/sync"
SIMBAD_SERVERS = (SIMBAD_TAP, "https://simbad.harvard.edu/simbad/sim-tap/sync")


def query_simbad(client: httpx.Client, query: str):
    """Probar un mirror por vez; nunca degradar una búsqueda a coordenadas inventadas."""
    failures = []
    for endpoint in SIMBAD_SERVERS:
        try:
            print(f"Consultando SIMBAD: {endpoint}", flush=True)
            response = client.get(endpoint, params={"REQUEST": "doQuery", "LANG": "ADQL",
                                                   "FORMAT": "votable", "QUERY": query},
                                  timeout=httpx.Timeout(30.0, connect=10.0))
            response.raise_for_status()
        except (httpx.HTTPError, OSError) as exc:
            reason = f"{type(exc).__name__}: {exc}"
            failures.append({"server": endpoint, "error": reason})
            print(f"AVISO: SIMBAD no disponible en {endpoint}: {reason}", file=sys.stderr)
            continue
        try:
            root = ElementTree.fromstring(response.content)
        except ElementTree.ParseError:
            failures.append({"server": endpoint, "error": "Respuesta no XML"})
            print(f"AVISO: {endpoint} no devolvió XML; probando el siguiente mirror.", file=sys.stderr)
            continue
        for info in root.iter():
            if info.get("name") == "QUERY_STATUS" and info.get("value") == "ERROR":
                # Un error de consulta no se presenta como un problema de conectividad.
                raise ValueError(f"SIMBAD: {''.join(info.itertext()).strip()}")
        table = parse_single_table(io.BytesIO(response.content)).to_table(use_names_over_ids=True)
        return table, endpoint, failures
    details = "; ".join(f"{item['server']}: {item['error']}" for item in failures)
    raise ValueError("No se obtuvo una respuesta utilizable de SIMBAD en ninguno de los "
                     f"servidores. {details}. Para probar solo el pipeline de un campo, "
                     "usar --ra y --dec explícitas; esto no valida la identidad del objeto.")


def resolve_target(client: httpx.Client, name: str, epoch: float = 2026.5) -> dict:
    if not name.strip() or len(name) > 200 or not math.isfinite(epoch):
        raise ValueError("Nombre o época no válido.")
    # SIMBAD almacena algunos identificadores con prefijos NAME, * o V*.
    aliases = [name, f"NAME {name}", f"* {name}", f"V* {name}"]
    literals = ", ".join("'" + alias.replace("'", "''") + "'" for alias in aliases)
    query = ("SELECT DISTINCT TOP 2 b.main_id, b.ra, b.dec, b.pmra, b.pmdec "
             "FROM basic AS b JOIN ident AS i ON b.oid = i.oidref "
             f"WHERE i.id IN ({literals})")
    table, source, failures = query_simbad(client, query)
    if len(table) != 1:
        raise ValueError(f"SIMBAD: se esperaba un único objeto para {name!r}; encontrados {len(table)}.")
    row = table[0]
    ra, dec = float(row["ra"]), float(row["dec"])
    if not (math.isfinite(ra) and math.isfinite(dec)):
        raise ValueError("SIMBAD: coordenadas ausentes o no finitas.")
    pm_available = all(not np.ma.is_masked(row[key]) and math.isfinite(float(row[key]))
                       for key in ("pmra", "pmdec"))
    coord = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame="icrs")
    pmra = pmdec = None
    if pm_available:
        pmra, pmdec = float(row["pmra"]), float(row["pmdec"])
        reference = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, pm_ra_cosdec=pmra * u.mas / u.yr,
                             pm_dec=pmdec * u.mas / u.yr, obstime=Time("J2000"), frame="icrs")
        coord = reference.apply_space_motion(new_obstime=Time(epoch, format="jyear"))
    main_id = row["main_id"]
    if isinstance(main_id, bytes):
        main_id = main_id.decode("utf-8")
    return {"name": name, "main_id": str(main_id), "source": source,
            "server_failures": failures,
            "reference_epoch": "J2000", "reference_ra_deg": ra, "reference_dec_deg": dec,
            "pm_ra_cosdec_mas_yr": pmra, "pm_dec_mas_yr": pmdec,
            "proper_motion_applied": pm_available, "requested_epoch_jyear": epoch,
            "ra_deg": float(coord.ra.deg), "dec_deg": float(coord.dec.deg),
            "coordinate_epoch_jyear": epoch if pm_available else 2000.0,
            "caveat": "Movimiento propio lineal; sin paralaje anual ni velocidad radial."}
