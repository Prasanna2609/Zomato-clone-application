from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from shared.config.config import ZOMATO_CLEAN_PARQUET_PATH


_cached_df: Optional[pd.DataFrame] = None

def load_cleaned_zomato(path: Optional[str | Path] = None) -> pd.DataFrame:
    """
    Load the cleaned Zomato dataset produced by Phase 1.

    Parameters
    ----------
    path:
        Optional override for the Parquet file path. When omitted, the default
        location defined in `backend.config.ZOMATO_CLEAN_PARQUET_PATH` is used.

    Returns
    -------
    pandas.DataFrame
        The cleaned restaurant records, including normalized price, rating,
        cuisines, and a stable `restaurant_id`.
    """
    global _cached_df
    if _cached_df is not None and path is None:
        return _cached_df

    parquet_path = Path(path) if path is not None else ZOMATO_CLEAN_PARQUET_PATH
    if not parquet_path.exists():
        raise FileNotFoundError(
            f"Dataset not found at {parquet_path}. "
            "Run ingestion locally before deployment."
        )

    df = pd.read_parquet(parquet_path)
    if path is None:
        _cached_df = df
    return df

