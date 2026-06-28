import os
import shutil
import duckdb
import pandas as pd
from pathlib import Path
from kaggle import KaggleApi

DATASET = "ulrikeherold/tech-layoffs-2020-2024"
DATA_DIR = Path("data")
DB_PATH = DATA_DIR / "layoffs.duckdb"
RAW_DIR = DATA_DIR / "raw"


def download_dataset():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {DATASET}...")
    api = KaggleApi()
    api.authenticate()
    api.dataset_download_files(DATASET, path=str(RAW_DIR), unzip=True)
    print("Download complete.")


def find_csv(directory: Path) -> Path:
    csvs = list(directory.glob("*.csv"))
    if not csvs:
        raise FileNotFoundError(f"No CSV found in {directory}")
    # prefer the largest file (main dataset, not metadata)
    return max(csvs, key=lambda p: p.stat().st_size)


def load_to_duckdb():
    csv_path = find_csv(RAW_DIR)
    print(f"Loading {csv_path.name} -> DuckDB...")

    df = pd.read_csv(csv_path, low_memory=False)
    print(f"Raw shape: {df.shape}")

    # normalize column names
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # common column aliases across dataset versions
    rename_map = {
        "laid_off": "total_laid_off",
        "percent_laid_off": "percentage_laid_off",
        "funds_raised": "funds_raised_millions",
    }
    df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns}, inplace=True)

    # parse date
    date_col = next((c for c in df.columns if "date" in c), None)
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df["year"] = df[date_col].dt.year
        df["month"] = df[date_col].dt.to_period("M").astype(str)

    # drop rows with no useful data
    df = df.dropna(subset=["company"])

    con = duckdb.connect(str(DB_PATH))
    con.execute("DROP TABLE IF EXISTS layoffs")
    con.execute("CREATE TABLE layoffs AS SELECT * FROM df")
    count = con.execute("SELECT COUNT(*) FROM layoffs").fetchone()[0]
    con.close()

    print(f"Loaded {count:,} rows into {DB_PATH}")


def main():
    DATA_DIR.mkdir(exist_ok=True)
    download_dataset()
    load_to_duckdb()
    # clean up raw files to keep repo light
    if RAW_DIR.exists():
        shutil.rmtree(RAW_DIR)
    print("Done.")


if __name__ == "__main__":
    main()
