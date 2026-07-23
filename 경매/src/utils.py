import re
from datetime import date, datetime
from pathlib import Path
from typing import Optional


def safe_filename(value: str) -> str:
    """Windows에서 안전하게 사용할 수 있는 파일명을 만듭니다."""
    value = re.sub(r'[<>:"/\\|?*]', "_", value)
    value = re.sub(r"\s+", "_", value.strip())

    return value or "unknown"


def normalize_text(value: Optional[str]) -> str:
    """여러 공백과 줄바꿈을 하나의 공백으로 정리합니다."""
    if value is None:
        return ""

    return re.sub(r"\s+", " ", value).strip()


def parse_integer(value: Optional[str]) -> Optional[int]:
    """원, 쉼표 등이 포함된 문자열에서 정수를 추출합니다."""
    if not value:
        return None

    digits = re.sub(r"[^\d-]", "", value)

    if not digits or digits == "-":
        return None

    try:
        return int(digits)
    except ValueError:
        return None


def parse_float(value: Optional[str]) -> Optional[float]:
    """㎡ 등의 문자가 포함된 문자열에서 실수를 추출합니다."""
    if not value:
        return None

    match = re.search(r"-?\d+(?:\.\d+)?", value.replace(",", ""))

    if not match:
        return None

    try:
        return float(match.group())
    except ValueError:
        return None


def parse_date(value: Optional[str]) -> str:
    """여러 날짜 표기를 YYYY-MM-DD로 통일합니다."""
    if not value:
        return ""

    cleaned = value.strip()

    patterns = (
        "%Y.%m.%d",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y%m%d",
    )

    for pattern in patterns:
        try:
            return datetime.strptime(cleaned, pattern).strftime("%Y-%m-%d")
        except ValueError:
            continue

    match = re.search(
        r"(\d{4})[.\-/년\s]+(\d{1,2})[.\-/월\s]+(\d{1,2})",
        cleaned,
    )

    if not match:
        return cleaned

    year, month, day = map(int, match.groups())

    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return cleaned


def write_text(path: Path, content: str) -> Path:
    """텍스트를 UTF-8로 저장합니다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

    return path