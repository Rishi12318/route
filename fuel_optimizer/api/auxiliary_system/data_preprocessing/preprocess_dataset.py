"""
Dataset preprocessor for fuel_prices.csv.
Geocodes City+State → lat/lng using bundled offline lookup.
Saves cleaned_fuel_prices.csv to the Django project root.

Usage:
    python preprocess_dataset.py
    python preprocess_dataset.py --input path/to/fuel_prices.csv
"""
import os
import sys
import time
import json
import logging
import argparse
import pandas as pd
from typing import Optional

# Allow running from any directory
sys.path.insert(0, os.path.dirname(__file__))
from us_cities_geocode import lookup as city_lookup   # bundled offline geocoder

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Default paths
_HERE        = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.normpath(os.path.join(_HERE, "..", "..", ".."))  # fuel_optimizer/
DEFAULT_INPUT  = os.path.join(_PROJECT_ROOT, "fuel_prices.csv")
DEFAULT_OUTPUT = os.path.join(_PROJECT_ROOT, "cleaned_fuel_prices.csv")
DEFAULT_REPORT = os.path.join(_HERE, "preprocessing_report.json")


class FuelDatasetPreprocessor:
    """Load, geocode, clean and validate the raw fuel price CSV."""

    def __init__(self, input_path: str, output_path: str = DEFAULT_OUTPUT) -> None:
        self.input_path  = input_path
        self.output_path = output_path
        self._stats: dict = {}

    # ── Public entry point ────────────────────────────────────────────────
    def preprocess(self) -> pd.DataFrame:
        t0 = time.time()
        df = self.load_raw_data()
        self._stats["original_rows"] = len(df)

        df = self.geocode_stations(df)
        df = self.clean_data(df)
        df = self.validate_ranges(df)

        if len(df) < 100:
            raise ValueError(
                f"Insufficient data: only {len(df)} valid rows remain after cleaning."
            )

        df.to_csv(self.output_path, index=False)
        logger.info("Saved %d rows to %s", len(df), self.output_path)

        self._stats["final_rows"]   = len(df)
        self._stats["processing_time_seconds"] = round(time.time() - t0, 3)
        total_removed = sum(v for k, v in self._stats.get("rows_removed", {}).items())
        orig = self._stats.get("original_rows", 1)
        self._stats["data_quality_score"] = round(len(df) / orig, 4) if orig else 0

        self.generate_report(self._stats)
        return df

    # ── Step 1: Load ──────────────────────────────────────────────────────
    def load_raw_data(self) -> pd.DataFrame:
        if not os.path.isfile(self.input_path):
            raise FileNotFoundError(
                f"Input file not found: {self.input_path}"
            )
        for enc in ("utf-8", "latin-1"):
            try:
                df = pd.read_csv(self.input_path, encoding=enc)
                logger.info("Loaded %d rows with encoding=%s", len(df), enc)
                return df
            except UnicodeDecodeError:
                continue
        raise ValueError("Cannot decode CSV with UTF-8 or latin-1.")

    # ── Step 2: Geocode City+State → lat/lng ─────────────────────────────
    def geocode_stations(self, df: pd.DataFrame) -> pd.DataFrame:
        # Detect city / state columns (flexible naming)
        cols_lower = {c.lower(): c for c in df.columns}
        city_col  = next((cols_lower[k] for k in cols_lower if "city"  in k), None)
        state_col = next((cols_lower[k] for k in cols_lower if "state" in k), None)
        price_col = next(
            (cols_lower[k] for k in cols_lower
             if any(p in k for p in ("retail price", "price", "cost", "fuel_price"))),
            None,
        )

        if price_col is None:
            available = list(df.columns)
            raise KeyError(
                f"Cannot find a price column. Available columns: {available}"
            )

        logger.info("Using columns: city=%s, state=%s, price=%s", city_col, state_col, price_col)

        lats, lngs = [], []
        geocoded = skipped = 0
        for _, row in df.iterrows():
            city  = str(row[city_col]).strip()  if city_col  else ""
            state = str(row[state_col]).strip() if state_col else ""
            coords = city_lookup(city, state)
            if coords:
                lats.append(coords[0])
                lngs.append(coords[1])
                geocoded += 1
            else:
                lats.append(None)
                lngs.append(None)
                skipped += 1

        df = df.copy()
        df["lat"]   = lats
        df["lng"]   = lngs
        df["price"] = pd.to_numeric(df[price_col], errors="coerce")
        logger.info("Geocoded %d rows, %d skipped (unknown city/state)", geocoded, skipped)
        return df

    # ── Step 3: Clean ─────────────────────────────────────────────────────
    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        removed: dict = {}
        before = len(df)

        # Drop rows missing lat/lng/price
        df = df.dropna(subset=["lat", "lng", "price"])
        removed["missing_values"] = before - len(df);  before = len(df)

        # Drop exact duplicate rows
        df = df.drop_duplicates()
        removed["duplicates"] = before - len(df);  before = len(df)

        # Keep lowest price per coordinate pair
        df = (
            df.sort_values("price")
              .drop_duplicates(subset=["lat", "lng"], keep="first")
        )
        removed["coord_duplicates"] = before - len(df);  before = len(df)

        # Convert and round
        df["lat"]   = df["lat"].astype(float).round(6)
        df["lng"]   = df["lng"].astype(float).round(6)
        df["price"] = df["price"].astype(float).round(2)

        # Keep only canonical and useful columns
        cols_to_keep = ["OPIS Truckstop ID", "Truckstop Name", "Address", "City", "State", "Rack ID", "lat", "lng", "price"]
        available_cols = [c for c in cols_to_keep if c in df.columns]
        df = df[available_cols].reset_index(drop=True)

        self._stats["rows_removed"] = removed
        logger.info("After cleaning: %d rows (removed %s)", len(df), removed)
        return df

    # ── Step 4: Validate ranges ───────────────────────────────────────────
    def validate_ranges(self, df: pd.DataFrame) -> pd.DataFrame:
        before = len(df)
        invalid_lat   = df[(df["lat"] < -90)  | (df["lat"] > 90)]
        invalid_lng   = df[(df["lng"] < -180) | (df["lng"] > 180)]
        invalid_price = df[(df["price"] <= 0) | (df["price"] >= 20)]

        removed = self._stats.setdefault("rows_removed", {})
        removed["invalid_lat"]   = len(invalid_lat)
        removed["invalid_lng"]   = len(invalid_lng)
        removed["invalid_price"] = len(invalid_price)

        df = df[
            (df["lat"]   >= -90)  & (df["lat"]   <= 90)  &
            (df["lng"]   >= -180) & (df["lng"]   <= 180) &
            (df["price"] >  0)    & (df["price"] <  20)
        ]
        logger.info("After validation: %d rows (removed %d)", len(df), before - len(df))
        return df

    # ── Step 5: Report ────────────────────────────────────────────────────
    def generate_report(self, stats: dict) -> None:
        with open(DEFAULT_REPORT, "w", encoding="utf-8") as fh:
            json.dump(stats, fh, indent=2)
        logger.info("Preprocessing report saved to %s", DEFAULT_REPORT)


# ── CLI ───────────────────────────────────────────────────────────────────
def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Preprocess fuel_prices.csv")
    p.add_argument("--input",  default=DEFAULT_INPUT,  help="Path to raw CSV")
    p.add_argument("--output", default=DEFAULT_OUTPUT, help="Path to cleaned CSV")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    preprocessor = FuelDatasetPreprocessor(args.input, args.output)
    df = preprocessor.preprocess()
    print(f"\n[OK] Preprocessing complete - {len(df)} clean stations saved to:\n  {args.output}")
