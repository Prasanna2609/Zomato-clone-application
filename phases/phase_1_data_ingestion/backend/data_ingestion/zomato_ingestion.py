from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import pandas as pd
from datasets import load_dataset

from shared.config.config import DATA_DIR, ZOMATO_DATASET_ID, ZOMATO_CLEAN_PARQUET_PATH


RAW_SPLIT_NAME = "train"


def fetch_raw_dataset() -> pd.DataFrame:
    """
    Download the raw Zomato dataset from Hugging Face and return it as a DataFrame.
    """
    ds = load_dataset(ZOMATO_DATASET_ID, split=RAW_SPLIT_NAME)
    df = ds.to_pandas()
    return df


def inspect_dataset(df: pd.DataFrame, num_rows: int = 5) -> None:
    """
    Print basic information about the dataset for manual inspection.
    """
    print("=== Zomato Raw Dataset Overview ===")
    print(f"Number of rows: {len(df)}")
    print(f"Number of columns: {len(df.columns)}")
    print("\nColumns:")
    for col in df.columns:
        print(f"  - {col}")

    print(f"\nSample {num_rows} rows:")
    print(df.head(num_rows))


def _parse_price(value: object) -> Optional[int]:
    """
    Normalize price strings like \"1,500\" into integer 1500.
    Returns None when parsing is not possible.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None

    # Remove common formatting artifacts such as commas
    text = text.replace(",", "")

    # Some rows may contain non-numeric placeholders
    if text.lower() in {"nan", "null", "none", "-"}:
        return None

    try:
        return int(float(text))
    except ValueError:
        return None


def _parse_rating(value: object) -> Optional[float]:
    """
    Normalize rating strings like \"4.1/5\" into float 4.1.
    Returns None when parsing is not possible (e.g., \"NEW\", \"-\").
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None

    # Common non-rating placeholders
    if text.upper() in {"NEW", "-", "NAN"}:
        return None

    # Typical pattern is \"4.1/5\"
    if "/" in text:
        text = text.split("/", 1)[0].strip()

    try:
        return float(text)
    except ValueError:
        return None


def _parse_cuisines(value: object) -> List[str]:
    """
    Normalize the cuisines column into a list of cuisine strings.
    The raw field is typically a comma-separated string such as
    \"North Indian, Mughlai, Chinese\".
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if not isinstance(value, str):
        return []

    parts = [part.strip() for part in value.split(",")]
    return [p for p in parts if p]


def clean_zomato_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply schema normalization and basic cleaning:
    - Normalize price, rating, and cuisines.
    - Remove duplicate restaurants (by `url`).
    - Add a stable `restaurant_id` column.
    """
    df_clean = df.copy()

    # Normalize price (approx_cost(for two people) -> price_for_two)
    price_col = "approx_cost(for two people)"
    if price_col in df_clean.columns:
        df_clean["price_for_two"] = df_clean[price_col].map(_parse_price)

    # Normalize rating (rate -> rating)
    rating_col = "rate"
    if rating_col in df_clean.columns:
        df_clean["rating"] = df_clean[rating_col].map(_parse_rating)

    # Normalize cuisines (string -> list[str])
    cuisines_col = "cuisines"
    if cuisines_col in df_clean.columns:
        df_clean["cuisines_normalized"] = df_clean[cuisines_col].map(_parse_cuisines)

    # Remove duplicate restaurants based on URL, which is a stable identifier in the dataset
    if "url" in df_clean.columns:
        df_clean = df_clean.drop_duplicates(subset="url").reset_index(drop=True)

    # Generate a simple integer restaurant_id for internal use
    df_clean.insert(0, "restaurant_id", range(1, len(df_clean) + 1))

    return df_clean


def save_cleaned_dataset(df_clean: pd.DataFrame, path: Path = ZOMATO_CLEAN_PARQUET_PATH) -> Path:
    """
    Persist the cleaned dataset to disk in Parquet format.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df_clean.to_parquet(path, index=False)
    return path


def run_full_ingestion() -> Path:
    """
    Execute the full Phase 1 ingestion pipeline:
    - Fetch raw dataset from Hugging Face.
    - Inspect and print basic information.
    - Clean and normalize key fields.
    - Deduplicate restaurants.
    - Save cleaned dataset to disk.
    """
    print("Fetching raw Zomato dataset from Hugging Face...")
    raw_df = fetch_raw_dataset()

    inspect_dataset(raw_df, num_rows=5)

    print("\nCleaning and normalizing dataset...")
    clean_df = clean_zomato_dataframe(raw_df)

    print(f"Rows after cleaning and de-duplication: {len(clean_df)}")

    print(f"\nSaving cleaned dataset to: {ZOMATO_CLEAN_PARQUET_PATH}")
    output_path = save_cleaned_dataset(clean_df, ZOMATO_CLEAN_PARQUET_PATH)

    print("Done.")
    return output_path


if __name__ == "__main__":
    run_full_ingestion()

