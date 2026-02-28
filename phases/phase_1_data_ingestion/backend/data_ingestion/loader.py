from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from shared.config.config import ZOMATO_CLEAN_PARQUET_PATH


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
    parquet_path = Path(path) if path is not None else ZOMATO_CLEAN_PARQUET_PATH
    if not parquet_path.exists():
        from phases.phase_1_data_ingestion.backend.data_ingestion.zomato_ingestion import run_full_ingestion
        print(f"Cleaned dataset not found at {parquet_path}. Triggering auto-ingestion...")
        run_full_ingestion()
        
        if not parquet_path.exists():
            raise FileNotFoundError(
                f"Auto-ingestion failed to produce dataset at {parquet_path}."
            )

    return pd.read_parquet(parquet_path)

