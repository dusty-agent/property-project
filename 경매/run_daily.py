from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil
import os
from zoneinfo import ZoneInfo

from src.collector.mapper import merge_items
from src.collector.nationwide import NationwideCollector
from src.exporter.json_exporter import JsonExporter


BASE_DIR = Path(__file__).resolve().parent

OUTPUT_JSON_DIR = (
    BASE_DIR
    / "output"
    / "json"
)

DUSTIE_DATA_DIR = Path(
    os.getenv(
        "DUSTIE_DATA_DIR",
        r"C:\Users\user\dev\dustie-web\public\data",
    )
)

COURT_CODE = "B000210"
COURT_NAME = "서울중앙지방법원"


def main() -> None:
    # 실제 운영 시 사용
    target_date = datetime.now(
        ZoneInfo("Asia/Seoul")
    ).strftime("%Y%m%d")

    # 2026-07-23 데이터 재테스트 시 아래처럼 잠깐 고정
    # target_date = "20260723"

    print("=" * 64)
    print("서울중앙지방법원 일일 경매 수집")
    print("=" * 64)
    print(f"- 수집 기준일: {target_date}")

    collector = NationwideCollector()

    try:
        result = collector.collect_by_date(
            target_date=target_date,
            court_codes=[COURT_CODE],
            stop_on_error=False,
        )

    except Exception as error:
        print("\n[실패] 경매 수집 중 오류가 발생했습니다.")
        print(f"[오류 종류] {type(error).__name__}")
        print(f"[오류 내용] {error}")
        raise

    raw_items = result.rows

    print()
    print("[수집 완료]")
    print(f"- 원본 행 수: {len(raw_items):,}개")
    print(
        f"- 성공 일정 수: "
        f"{result.successful_schedules:,}개"
    )
    print(
        f"- 실패 일정 수: "
        f"{result.failed_schedules:,}개"
    )

    if not raw_items:
        print()
        print("[안내] 수집된 경매 물건이 없습니다.")

        # 오늘 일정이 없는 경우에도 빈 JSON을 생성합니다.
        properties = []

    else:
        try:
            properties = merge_items(
                raw_items
            )

        except Exception as error:
            print()
            print(
                "[실패] 경매 원본 행 병합 중 "
                "오류가 발생했습니다."
            )
            print(
                f"[오류 종류] "
                f"{type(error).__name__}"
            )
            print(
                f"[오류 내용] "
                f"{error}"
            )
            raise

    print()
    print("[병합 결과]")
    print(
        f"- 원본 행: "
        f"{len(raw_items):,}개"
    )
    print(
        f"- 경매 물건: "
        f"{len(properties):,}개"
    )

    try:
        dated_filename = (
            f"auction_{COURT_CODE}_{target_date}"
        )

        dated_json_path = JsonExporter.export(
            properties=properties,
            filename=dated_filename,
            search_date=target_date,
        )

        latest_json_path = JsonExporter.export(
            properties=properties,
            filename="auction_latest",
            search_date=target_date,
        )

    except Exception as error:
        print()
        print(
            "[실패] JSON 저장 중 "
            "오류가 발생했습니다."
        )
        print(
            f"[오류 종류] "
            f"{type(error).__name__}"
        )
        print(
            f"[오류 내용] "
            f"{error}"
        )
        raise

    print()
    print("[JSON 저장 완료]")
    print(
        f"- 날짜별 JSON: "
        f"{dated_json_path}"
    )
    print(
        f"- 최신 JSON: "
        f"{latest_json_path}"
    )

    try:
        DUSTIE_DATA_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        dustie_latest_path = (
            DUSTIE_DATA_DIR
            / "auction_latest.json"
        )

        shutil.copy2(
            latest_json_path,
            dustie_latest_path,
        )

    except OSError as error:
        print()
        print(
            "[실패] Dustie UI로 JSON 복사 중 "
            "오류가 발생했습니다."
        )
        print(
            f"[오류 내용] "
            f"{error}"
        )
        raise

    print(
        f"- Dustie UI 복사: "
        f"{dustie_latest_path}"
    )

    if result.errors:
        print()
        print("[수집 오류 목록]")

        for error in result.errors:
            print(
                f"- {error.get('court_name', '')} "
                f"{error.get('department_name', '')}: "
                f"{error.get('message', '')}"
            )

    print()
    print("=" * 64)
    print("일일 수집 작업이 완료되었습니다.")
    print("=" * 64)


if __name__ == "__main__":
    main()