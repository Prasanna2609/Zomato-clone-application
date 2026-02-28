"""
Small test script to validate Phase 1 dataset ingestion.

Usage (from project root):
    python -m scripts.test_load_cleaned_data

This script assumes that the ingestion pipeline has already been run:
    python -m backend.data_ingestion.zomato_ingestion
"""

from __future__ import annotations

from phases.phase_1_data_ingestion.backend.data_ingestion.loader import load_cleaned_zomato


def main() -> None:
    df = load_cleaned_zomato()
    print("=== Cleaned Zomato Dataset Loaded ===")
    print(f"Shape: {df.shape}")
    print("\nColumns:")
    print(df.columns.tolist())
    print("\nSample rows:")
    print(df.head(5))


if __name__ == "__main__":
    main()

