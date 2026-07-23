from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent


BASE_DIR = Path(__file__).resolve().parent.parent

OUTPUT_DIR = BASE_DIR / "output"

RAW_DIR = OUTPUT_DIR / "raw"
JSON_DIR = OUTPUT_DIR / "json"
EXCEL_DIR = OUTPUT_DIR / "excel"
LOG_DIR = OUTPUT_DIR / "logs"

COURT_AUCTION_BASE_URL = "https://www.courtauction.go.kr"
COURT_AUCTION_MAIN_PATH = "/pgj/index.on"
COURT_AUCTION_MAIN_URL = (
    f"{COURT_AUCTION_BASE_URL}{COURT_AUCTION_MAIN_PATH}"
)

DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_PAGE_SIZE = 30


def ensure_directories() -> None:
    for directory in (
        RAW_DIR,
        JSON_DIR,
        EXCEL_DIR,
    ):
        directory.mkdir(
            parents=True,
            exist_ok=True,
        )