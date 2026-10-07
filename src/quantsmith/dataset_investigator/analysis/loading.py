"""Load a dataset read-only and fingerprint it. Spec ``0099`` (REQ-001).

Supported: CSV/TSV, Parquet, a pandas DataFrame, and a Polars DataFrame (via
``to_pandas``; Polars is never imported here). The source is never written to.

Two fingerprints are recorded: the SHA-256 of the file's bytes (what
``reproduce`` checks before re-running anything) and a content hash of the
loaded table (what every tool execution is keyed on). Loading normalizes
types the same way for every format — ISO date strings become datetimes,
strings become ``object`` — so a CSV and a Parquet copy of one table give the
same content hash and the same profile.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Tuple, Union

import numpy as np
import pandas as pd

from .models import DatasetInfo
from .utils import sha256_text

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2}(\.\d+)?)?)?$")

Source = Union[str, Path, pd.DataFrame, Any]


class LoadError(ValueError):
    """The source cannot be read (unsupported format or missing reader)."""


def file_sha256(path: Union[str, Path]) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_file(path: Path) -> Tuple[pd.DataFrame, str]:
    suffix = path.suffix.lower()
    if suffix in (".csv", ".txt"):
        return pd.read_csv(path), "csv"
    if suffix == ".tsv":
        return pd.read_csv(path, sep="\t"), "tsv"
    if suffix in (".parquet", ".pq"):
        try:
            import pyarrow  # noqa: F401
        except ImportError as exc:  # pragma: no cover - the extra installs it
            raise LoadError("reading Parquet needs pyarrow: install quantsmith[investigator]") from exc
        return pd.read_parquet(path), "parquet"
    raise LoadError(f"unsupported file type {suffix!r}: use CSV, TSV, or Parquet (or pass a DataFrame)")


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Return a normalized copy: ISO date strings → ``datetime64[ns]``, strings → ``object``."""
    out = df.copy()
    out.columns = [str(c) for c in out.columns]
    for col in out.columns:
        s = out[col]
        if pd.api.types.is_datetime64_any_dtype(s):
            if getattr(s.dt, "tz", None) is not None:
                s = s.dt.tz_convert("UTC").dt.tz_localize(None)
            out[col] = s.astype("datetime64[ns]")
        elif pd.api.types.is_string_dtype(s) or s.dtype == object:
            values = s.dropna()
            head = values.iloc[:1000]
            if (len(values) and head.map(lambda v: isinstance(v, str)).all()
                    and head.str.match(_ISO_DATE).mean() >= 0.99
                    and values.map(lambda v: isinstance(v, str)).all()
                    and values.str.match(_ISO_DATE).mean() >= 0.99):
                out[col] = pd.to_datetime(s, errors="coerce", format="mixed").astype("datetime64[ns]")
                continue
            out[col] = s.astype(object).where(s.notna(), np.nan)
    return out


def content_sha256(df: pd.DataFrame) -> str:
    """A content hash of a normalized table: column names, dtypes, and every value in order."""
    h = hashlib.sha256()
    h.update("\x1f".join(f"{c}:{df[c].dtype}" for c in df.columns).encode("utf-8"))
    if len(df):
        h.update(pd.util.hash_pandas_object(df, index=False).to_numpy().tobytes())
    return h.hexdigest()


def load_dataset(source: Source) -> Tuple[pd.DataFrame, DatasetInfo]:
    """Load ``source`` and describe it (REQ-001). The source itself is never modified."""
    file_hash = None
    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.is_file():
            raise LoadError(f"no such file: {path}")
        raw, fmt = _read_file(path)
        file_hash = file_sha256(path)
        name = str(path)
    elif isinstance(source, pd.DataFrame):
        raw, fmt, name = source, "pandas", "<pandas.DataFrame>"
    elif type(source).__module__.split(".")[0] == "polars" and hasattr(source, "to_pandas"):
        raw, fmt, name = source.to_pandas(), "polars", "<polars.DataFrame>"
    else:
        raise LoadError(f"unsupported source type {type(source).__name__}: pass a path or a DataFrame")
    df = normalize(raw)
    content = content_sha256(df)
    info = DatasetInfo(
        source=name, format=fmt, file_sha256=file_hash, content_sha256=content,
        rows=int(len(df)), columns=int(df.shape[1]), column_names=list(df.columns),
    )
    return df, info


def fingerprint_short(info: DatasetInfo) -> str:
    return sha256_text(info.content_sha256)[:12]
