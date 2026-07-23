from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable

from src.collector.court_auction import CourtAuctionCollector
from src.collector.court_directory import CourtDirectoryCollector


@dataclass
class CollectionResult:
    """전국 경매 수집 결과."""

    target_date: str
    total_courts: int
    visited_courts: int
    total_schedules: int
    successful_schedules: int
    failed_schedules: int
    raw_row_count: int
    rows: list[dict[str, Any]]
    errors: list[dict[str, str]]

    def to_dict(self) -> dict[str, Any]:
        """수집 결과를 일반 dict 형태로 반환합니다."""
        return {
            "target_date": self.target_date,
            "total_courts": self.total_courts,
            "visited_courts": self.visited_courts,
            "total_schedules": self.total_schedules,
            "successful_schedules": self.successful_schedules,
            "failed_schedules": self.failed_schedules,
            "raw_row_count": self.raw_row_count,
            "rows": self.rows,
            "errors": self.errors,
        }


class NationwideCollector:
    """
    전국 법원경매 물건 수집을 총괄합니다.

    역할:
    1. 법원 목록 조회
    2. 대상 날짜의 매각 일정 조회
    3. 일정별 물건목록 수집
    4. 전체 원본 행 병합
    5. 중복 행 제거

    실제 API 통신은 CourtAuctionCollector가 담당합니다.
    법원·담당계·일정 탐색은 CourtDirectoryCollector가 담당합니다.
    """

    def __init__(
        self,
        auction_collector: CourtAuctionCollector | None = None,
        directory_collector: CourtDirectoryCollector | None = None,
    ) -> None:
        self.auction_collector = (
            auction_collector or CourtAuctionCollector()
        )

        self.directory_collector = (
            directory_collector
            or CourtDirectoryCollector(
                auction_collector=self.auction_collector,
            )
        )

    def collect_by_date(
        self,
        target_date: date | str,
        court_codes: list[str] | None = None,
        stop_on_error: bool = False,
    ) -> CollectionResult:
        """
        지정 날짜의 전국 경매 물건을 수집합니다.

        Args:
            target_date:
                datetime.date 또는 YYYYMMDD, YYYY-MM-DD 문자열

            court_codes:
                특정 법원 코드만 수집할 때 사용합니다.
                None이면 발견된 모든 B 계열 법원을 순회합니다.

            stop_on_error:
                True이면 한 일정에서 오류가 발생했을 때 즉시 중단합니다.
                False이면 오류를 기록하고 다음 일정으로 넘어갑니다.

        Returns:
            CollectionResult
        """
        normalized_date = self._normalize_date(target_date)

        courts = self.directory_collector.get_courts()

        if court_codes:
            allowed_codes = {
                str(code).strip()
                for code in court_codes
                if str(code).strip()
            }

            courts = [
                court
                for court in courts
                if court.get("court_code") in allowed_codes
            ]

        all_rows: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []

        visited_courts = 0
        total_schedules = 0
        successful_schedules = 0
        failed_schedules = 0

        print("=" * 64)
        print("전국 법원경매 수집")
        print("=" * 64)
        print(f"- 대상 날짜: {normalized_date}")
        print(f"- 대상 법원 수: {len(courts)}개")
        print("=" * 64)

        for court_index, court in enumerate(courts, start=1):
            court_code = str(
                court.get("court_code", "")
            ).strip()
            court_name = str(
                court.get("court_name", "")
            ).strip()

            if not court_code:
                continue

            print()
            print(
                f"[{court_index}/{len(courts)}] "
                f"{court_name} ({court_code})"
            )

            try:
                schedules = (
                    self.directory_collector.get_schedules(
                        court_code=court_code,
                        target_date=normalized_date,
                    )
                )
            except Exception as exc:
                error = {
                    "court_code": court_code,
                    "court_name": court_name,
                    "department_code": "",
                    "department_name": "",
                    "auction_date": normalized_date,
                    "message": str(exc),
                }
                errors.append(error)

                print(f"  [일정 조회 실패] {exc}")

                if stop_on_error:
                    raise

                continue

            if not schedules:
                print("  - 해당 날짜의 발견된 일정이 없습니다.")
                continue

            visited_courts += 1
            total_schedules += len(schedules)

            print(f"  - 발견 일정: {len(schedules)}개")

            for schedule_index, schedule in enumerate(
                schedules,
                start=1,
            ):
                department_code = str(
                    schedule.get("department_code", "")
                ).strip()
                department_name = str(
                    schedule.get("department_name", "")
                ).strip()
                auction_date = str(
                    schedule.get(
                        "auction_date",
                        normalized_date,
                    )
                ).strip()
                sale_time = str(
                    schedule.get("sale_time", "")
                ).strip()
                sale_place = str(
                    schedule.get("sale_place", "")
                ).strip()

                print(
                    f"  [{schedule_index}/{len(schedules)}] "
                    f"{department_name} / "
                    f"{sale_time or '시간 미상'} / "
                    f"{sale_place or '장소 미상'}"
                )

                if not department_code:
                    failed_schedules += 1

                    error = {
                        "court_code": court_code,
                        "court_name": court_name,
                        "department_code": "",
                        "department_name": department_name,
                        "auction_date": auction_date,
                        "message": "department_code가 없습니다.",
                    }
                    errors.append(error)

                    print("    [건너뜀] 담당계 코드가 없습니다.")
                    continue

                try:
                    search_result = (
                        self.auction_collector.search_all_pages(
                            court_code=court_code,
                            department_code=department_code,
                            auction_date=auction_date,
                            sale_time=sale_time,
                            sale_place=sale_place,
                        )
                    )

                    rows = self._extract_rows(search_result)
                    all_rows.extend(rows)

                    successful_schedules += 1

                    print(
                        f"    [완료] "
                        f"{len(rows)}개 원본 행 수집"
                    )

                except Exception as exc:
                    failed_schedules += 1

                    error = {
                        "court_code": court_code,
                        "court_name": court_name,
                        "department_code": department_code,
                        "department_name": department_name,
                        "auction_date": auction_date,
                        "message": str(exc),
                    }
                    errors.append(error)

                    print(f"    [수집 실패] {exc}")

                    if stop_on_error:
                        raise

        deduplicated_rows = self._deduplicate_rows(all_rows)

        print()
        print("=" * 64)
        print("전국 수집 결과")
        print("=" * 64)
        print(f"- 발견 법원 수: {len(courts)}개")
        print(f"- 일정이 있던 법원 수: {visited_courts}개")
        print(f"- 전체 일정 수: {total_schedules}개")
        print(f"- 성공 일정 수: {successful_schedules}개")
        print(f"- 실패 일정 수: {failed_schedules}개")
        print(f"- 수집 원본 행 수: {len(all_rows)}개")
        print(
            f"- 중복 제거 후 행 수: "
            f"{len(deduplicated_rows)}개"
        )
        print("=" * 64)

        return CollectionResult(
            target_date=normalized_date,
            total_courts=len(courts),
            visited_courts=visited_courts,
            total_schedules=total_schedules,
            successful_schedules=successful_schedules,
            failed_schedules=failed_schedules,
            raw_row_count=len(all_rows),
            rows=deduplicated_rows,
            errors=errors,
        )

    def collect_schedules(
        self,
        schedules: Iterable[dict[str, Any]],
        stop_on_error: bool = False,
    ) -> CollectionResult:
        """
        이미 준비된 일정 목록을 직접 전달하여 수집합니다.

        법원 일정 API가 아직 완성되지 않았을 때 테스트하거나,
        특정 일정만 골라서 수집할 때 사용할 수 있습니다.

        일정 형식:
        {
            "court_code": "B000210",
            "court_name": "서울중앙지방법원",
            "department_code": "1011",
            "department_name": "경매11계",
            "auction_date": "20260723",
            "sale_time": "1000",
            "sale_place": "경매법정4별관211호",
        }
        """
        schedule_list = list(schedules)

        all_rows: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []

        successful_schedules = 0
        failed_schedules = 0

        target_dates = {
            self._normalize_date(
                schedule.get("auction_date", "")
            )
            for schedule in schedule_list
            if schedule.get("auction_date")
        }

        target_date = (
            sorted(target_dates)[0]
            if len(target_dates) == 1
            else ""
        )

        visited_courts = {
            str(schedule.get("court_code", "")).strip()
            for schedule in schedule_list
            if schedule.get("court_code")
        }

        for index, schedule in enumerate(
            schedule_list,
            start=1,
        ):
            court_code = str(
                schedule.get("court_code", "")
            ).strip()
            court_name = str(
                schedule.get("court_name", "")
            ).strip()
            department_code = str(
                schedule.get("department_code", "")
            ).strip()
            department_name = str(
                schedule.get("department_name", "")
            ).strip()
            auction_date = self._normalize_date(
                schedule.get("auction_date", "")
            )
            sale_time = str(
                schedule.get("sale_time", "")
            ).strip()
            sale_place = str(
                schedule.get("sale_place", "")
            ).strip()

            print(
                f"[{index}/{len(schedule_list)}] "
                f"{court_name} {department_name} "
                f"{auction_date}"
            )

            try:
                search_result = (
                    self.auction_collector.search_all_pages(
                        court_code=court_code,
                        department_code=department_code,
                        auction_date=auction_date,
                        sale_time=sale_time,
                        sale_place=sale_place,
                    )
                )

                rows = self._extract_rows(search_result)
                all_rows.extend(rows)

                successful_schedules += 1

                print(f"  - {len(rows)}개 원본 행 수집")

            except Exception as exc:
                failed_schedules += 1

                errors.append(
                    {
                        "court_code": court_code,
                        "court_name": court_name,
                        "department_code": department_code,
                        "department_name": department_name,
                        "auction_date": auction_date,
                        "message": str(exc),
                    }
                )

                print(f"  [실패] {exc}")

                if stop_on_error:
                    raise

        deduplicated_rows = self._deduplicate_rows(all_rows)

        return CollectionResult(
            target_date=target_date,
            total_courts=len(visited_courts),
            visited_courts=len(visited_courts),
            total_schedules=len(schedule_list),
            successful_schedules=successful_schedules,
            failed_schedules=failed_schedules,
            raw_row_count=len(all_rows),
            rows=deduplicated_rows,
            errors=errors,
        )

    @classmethod
    def _extract_rows(
        cls,
        search_result: Any,
    ) -> list[dict[str, Any]]:
        """
        search_all_pages() 반환값에서 원본 행 목록을 꺼냅니다.

        기존 수집기의 반환 구조가 조금 달라도 사용할 수 있도록
        list, tuple, dict 구조를 모두 처리합니다.
        """
        if search_result is None:
            return []

        if isinstance(search_result, list):
            return [
                row
                for row in search_result
                if isinstance(row, dict)
            ]

        if isinstance(search_result, tuple):
            for value in search_result:
                rows = cls._extract_rows(value)

                if rows:
                    return rows

            return []

        if not isinstance(search_result, dict):
            raise TypeError(
                "search_all_pages() 반환값에서 "
                "행 목록을 찾을 수 없습니다. "
                f"반환 타입: {type(search_result).__name__}"
            )

        candidate_keys = (
            "rows",
            "raw_rows",
            "rawRows",
            "items",
            "results",
            "data",
            "dlt_srchResult",
        )

        for key in candidate_keys:
            value = search_result.get(key)

            if isinstance(value, list):
                rows = [
                    row
                    for row in value
                    if isinstance(row, dict)
                ]

                if rows:
                    return rows

            if isinstance(value, dict):
                rows = cls._extract_rows(value)

                if rows:
                    return rows

        rows = list(cls._find_row_lists(search_result))

        if rows:
            return rows

        raise RuntimeError(
            "search_all_pages() 반환값에서 원본 행 목록을 "
            "찾지 못했습니다. 반환 dict의 키를 확인해주세요: "
            f"{list(search_result.keys())}"
        )

    @classmethod
    def _find_row_lists(
        cls,
        value: Any,
    ) -> Iterable[dict[str, Any]]:
        """중첩 구조에서 경매 원본 행으로 보이는 dict를 찾습니다."""
        if isinstance(value, dict):
            if cls._looks_like_auction_row(value):
                yield value
                return

            for child in value.values():
                yield from cls._find_row_lists(child)

        elif isinstance(value, list):
            for child in value:
                yield from cls._find_row_lists(child)

    @staticmethod
    def _looks_like_auction_row(
        value: dict[str, Any],
    ) -> bool:
        """dict가 법원경매 원본 행인지 간단히 판단합니다."""
        identifying_keys = (
            "groupmaemulser",
            "bocdsano",
            "docid",
            "saNo",
            "srnSaNo",
        )

        return any(
            value.get(key)
            for key in identifying_keys
        )

    @classmethod
    def _deduplicate_rows(
        cls,
        rows: Iterable[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        원본 경매 행의 중복을 제거합니다.

        우선순위:
        1. docid
        2. 법원 코드 + 사건번호 + 물건번호 + 목적물번호
        3. groupmaemulser + mokmulSer
        """
        unique_rows: dict[str, dict[str, Any]] = {}

        for index, row in enumerate(rows):
            key = cls._make_row_key(
                row=row,
                fallback_index=index,
            )

            unique_rows[key] = row

        return list(unique_rows.values())

    @staticmethod
    def _make_row_key(
        row: dict[str, Any],
        fallback_index: int,
    ) -> str:
        """원본 행 중복 제거용 키를 만듭니다."""
        docid = str(row.get("docid", "")).strip()

        if docid:
            return f"docid:{docid}"

        court_code = str(
            row.get(
                "boCd",
                row.get("cortOfcCd", ""),
            )
        ).strip()
        case_number = str(
            row.get(
                "saNo",
                row.get("srnSaNo", ""),
            )
        ).strip()
        item_serial = str(
            row.get("maemulSer", "")
        ).strip()
        object_serial = str(
            row.get("mokmulSer", "")
        ).strip()

        if court_code and case_number:
            return (
                f"case:{court_code}:"
                f"{case_number}:"
                f"{item_serial}:"
                f"{object_serial}"
            )

        group_serial = str(
            row.get("groupmaemulser", "")
        ).strip()

        if group_serial:
            return (
                f"group:{group_serial}:"
                f"{object_serial}"
            )

        return f"fallback:{fallback_index}:{repr(row)}"

    @staticmethod
    def _normalize_date(
        value: date | datetime | str | Any,
    ) -> str:
        """날짜를 YYYYMMDD 형식으로 변환합니다."""
        if isinstance(value, datetime):
            return value.strftime("%Y%m%d")

        if isinstance(value, date):
            return value.strftime("%Y%m%d")

        text = str(value or "").strip()

        digits = "".join(
            character
            for character in text
            if character.isdigit()
        )

        if len(digits) < 8:
            raise ValueError(
                "target_date는 YYYYMMDD 또는 "
                "YYYY-MM-DD 형식이어야 합니다."
            )

        return digits[:8]