"""Contrato mínimo consumido por la API y la interfaz, también para cachés antiguas."""
from pydantic import BaseModel, ConfigDict, Field


class Record(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True, allow_inf_nan=False)


class Quality(Record):
    valid_coverage: float = Field(ge=0, le=1)
    center_pixel_valid: bool
    center_pixel_flag_names: list[str]


class Wavelength(Record):
    central_um: float | None = Field(gt=0)
    width_um: float | None = Field(gt=0)


class Frame(Record):
    image: str
    aligned_fits: str
    mjd: float
    date_utc: str
    detector: str
    collection: str
    cutout_url: str
    quality: Quality
    wavelength_at_target: Wavelength


class Query(Record):
    rows: int | None = Field(default=None, ge=0)
    error: str | None = None


class Failure(Record):
    error: str


class Policy(Record):
    mask_bits: list[int]


class Manifest(Record):
    schema_version: int
    pipeline_version: str
    status: str
    created_at_utc: str
    parameters: dict
    collections: list[str]
    quality_policy: Policy
    frames: list[Frame]
    queries: dict[str, Query]
    caveats: list[str]
    failures: list[Failure]
    credit: str
    warnings: list[str] = Field(default_factory=list)
