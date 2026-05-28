from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs"

PRODUCTS_FILE = DATA_DIR / "products.csv"
DEMAND_FILE = DATA_DIR / "demand_history.csv"
EVENTS_FILE = DATA_DIR / "events.csv"

DATE_FORMAT = "%Y-%m-%d"

INTERMITTENT_SELECTION_WEIGHTS = {
    "wape_rank": 0.35,
    "mae_rank": 0.25,
    "mase_rank": 0.25,
    "absolute_bias_rank": 0.15,
}
