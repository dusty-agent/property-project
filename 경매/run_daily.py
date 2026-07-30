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
        r"C:\Users\user\dev\dustie.xyz\dustie-web\public\data",
    )
)


def main() -> None:
    target_date = datetime.now(
        ZoneInfo("Asia/Seoul")
    ).strftime("%Y%m%d")

    # 과거 날짜 재테스트 시 잠시 고정
    # target_date = "20260723"

    print("=" * 64)
    print("전국 법원경매 일일 수집")
    print("=" * 64)
    print(f"- 수집 기준일: {target_date}")
    print("- 수집 범위: 발견된 전체 법원")
    print()

    collector = NationwideCollector()

    try:
        result = collector.collect_by_date(
            target_date=target_date,

            # None이면 발견된 모든 B계열 법원을 순회합니다.
            court_codes=None,

            # 일부 법원 또는 일정에서 실패해도
            # 나머지 법원 수집을 계속합니다.
            stop_on_error=False,
        )

    except Exception as error:
        print()
        print(
            "[실패] 전국 경매 수집 중 "
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

    raw_items = result.rows

    print()
    print("[수집 완료]")
    print(
        f"- 발견 법원 수: "
        f"{result.total_courts:,}개"
    )
    print(
        f"- 일정이 있던 법원 수: "
        f"{result.visited_courts:,}개"
    )
    print(
        f"- 전체 일정 수: "
        f"{result.total_schedules:,}개"
    )
    print(
        f"- 성공 일정 수: "
        f"{result.successful_schedules:,}개"
    )
    print(
        f"- 실패 일정 수: "
        f"{result.failed_schedules:,}개"
    )
    print(
        f"- 원본 행 수: "
        f"{len(raw_items):,}개"
    )

    if not raw_items:
        print()
        print(
            "[안내] 수집된 경매 물건이 없습니다."
        )

        properties = []

    else:
        try:
            properties = merge_items(
                raw_items,
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
            f"auction_all_{target_date}"
        )

        dated_json_path = (
            JsonExporter.export(
                properties=properties,
                filename=dated_filename,
                search_date=target_date,
            )
        )

        latest_json_path = (
            JsonExporter.export(
                properties=properties,
                filename="auction_latest",
                search_date=target_date,
            )
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
                f"- "
                f"{error.get('court_name', '')} "
                f"{error.get('department_name', '')}: "
                f"{error.get('message', '')}"
            )

    print()
    print("=" * 64)
    print("전국 일일 수집 작업이 완료되었습니다.")
    print("=" * 64)


if __name__ == "__main__":
    main()