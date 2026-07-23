from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

from src.collector.court_auction import CourtAuctionCollector
from src.config import RAW_DIR


@dataclass(frozen=True)
class CourtInfo:
    """법원 기본 정보."""

    court_code: str
    court_name: str


@dataclass(frozen=True)
class DepartmentInfo:
    """법원 경매 담당계 정보."""

    court_code: str
    court_name: str
    department_code: str
    department_name: str


@dataclass(frozen=True)
class AuctionSchedule:
    """법원별 경매 일정 정보."""

    court_code: str
    court_name: str
    department_code: str
    department_name: str
    auction_date: str
    sale_time: str
    sale_place: str


class CourtDirectoryCollector:
    """
    법원·경매계·매각기일 정보를 추출합니다.

    현재 확인된 법원경매 메인 정보 API 응답을 가져온 뒤,
    중첩된 JSON 내부에서 법원·담당계·기일 필드를 탐색합니다.

    실제 물건 검색은 CourtAuctionCollector가 담당하고,
    이 클래스는 검색 대상 목록만 제공합니다.
    """

    COURT_CODE_KEYS = (
    "boCd",
    "cortOfcCd",
    "courtCode",
    "court_code",
    "jiwonCd",
    "jiwonCode",
    )

    COURT_NAME_KEYS = (
    "jiwonNm",
    "cortOfcNm",
    "cortSptNm",
    "courtName",
    "court_name",
    "jiwonName",
    )

    DEPARTMENT_CODE_KEYS = (
    "jpDeptCd",
    "jdbnCd",
    "departmentCode",
    "department_code",
    "deptCd",
    )

    DEPARTMENT_NAME_KEYS = (
    "jpDeptNm",
    "cortAuctnJdbnNm",
    "jdbnNm",
    "departmentName",
    "department_name",
    "deptNm",
    )

    AUCTION_DATE_KEYS = (
    "maeGiil",
    "dspslDxdyYmd",
    "dxdyYmd",
    "auctionDate",
    "auction_date",
    "saleDate",
    )

    SALE_TIME_KEYS = (
    "maeHh1",
    "fstDspslHm",
    "scndDspslHm",
    "saleTime",
    "sale_time",
    "maeGiilHm",
    "dxdyHm",
    )

    SALE_PLACE_KEYS = (
    "maePlace",
    "dspslPlcNm",
    "salePlace",
    "sale_place",
    "maeGiilPlace",
    "dxdyPlcNm",
    )

    def __init__(
        self,
        auction_collector: CourtAuctionCollector | None = None,
    ) -> None:
        self.auction_collector = (
            auction_collector or CourtAuctionCollector()
        )
        self._cached_main_data: Any | None = None

    def fetch_directory_data(
        self,
        force_refresh: bool = False,
    ) -> Any:
        """
        법원경매 메인 정보 API 응답의 data 영역을 반환합니다.

        같은 실행 중 반복 요청을 줄이기 위해 결과를 캐시합니다.
        """
        if (
            self._cached_main_data is not None
            and not force_refresh
        ):
            return self._cached_main_data

        result = self.auction_collector.fetch_main_info()
        response_data = result.get("data")

        if response_data is None:
            raise RuntimeError(
                "법원경매 메인 정보 응답에 data가 없습니다."
            )

        self._cached_main_data = response_data

        return response_data

    def get_courts(
        self,
        force_refresh: bool = False,
    ) -> list[dict[str, str]]:
        """
        응답 전체에서 법원 코드와 법원명을 추출합니다.

        반환 예:
        [
            {
                "court_code": "B000210",
                "court_name": "서울중앙지방법원",
            }
        ]
        """
        data = self.fetch_directory_data(
            force_refresh=force_refresh,
        )

        courts: dict[str, CourtInfo] = {}

        for record in self._walk_dicts(data):
            court_code = self._first_value(
                record,
                self.COURT_CODE_KEYS,
            )
            court_name = self._first_value(
                record,
                self.COURT_NAME_KEYS,
            )

            if not court_code or not court_name:
                continue

            court_code = self._clean_text(court_code)
            court_name = self._clean_text(court_name)

            if not self._looks_like_court_code(court_code):
                continue
            
            # 부동산 경매 검색에 사용하는 B 계열 코드만 수집합니다.
            if not court_code.startswith("B"):
                continue

            courts[court_code] = CourtInfo(
                court_code=court_code,
                court_name=court_name,
            )

        result = [
            asdict(court)
            for court in sorted(
                courts.values(),
                key=lambda item: (
                    item.court_name,
                    item.court_code,
                ),
            )
        ]

        if not result:
            self._save_debug_response(
                data=data,
                prefix="court_directory_no_courts",
            )

            raise RuntimeError(
                "법원 목록을 추출하지 못했습니다. "
                "RAW 디렉터리에 디버그 응답을 저장했습니다."
            )

        return result

    def get_departments(
        self,
        court_code: str,
        force_refresh: bool = False,
    ) -> list[dict[str, str]]:
        """
        특정 법원의 경매 담당계를 추출합니다.

        반환 예:
        [
            {
                "court_code": "B000210",
                "court_name": "서울중앙지방법원",
                "department_code": "1011",
                "department_name": "경매11계",
            }
        ]
        """
        normalized_court_code = self._clean_text(court_code)

        if not normalized_court_code:
            raise ValueError("court_code가 비어 있습니다.")

        data = self.fetch_directory_data(
            force_refresh=force_refresh,
        )

        departments: dict[
            tuple[str, str],
            DepartmentInfo,
        ] = {}

        for record in self._walk_dicts(data):
            record_court_code = self._clean_text(
                self._first_value(
                    record,
                    self.COURT_CODE_KEYS,
                )
            )

            if record_court_code != normalized_court_code:
                continue

            court_name = self._clean_text(
                self._first_value(
                    record,
                    self.COURT_NAME_KEYS,
                )
            )
            department_code = self._clean_text(
                self._first_value(
                    record,
                    self.DEPARTMENT_CODE_KEYS,
                )
            )
            department_name = self._clean_text(
                self._first_value(
                    record,
                    self.DEPARTMENT_NAME_KEYS,
                )
            )

            if not department_code or not department_name:
                continue

            key = (
                normalized_court_code,
                department_code,
            )

            departments[key] = DepartmentInfo(
                court_code=normalized_court_code,
                court_name=court_name,
                department_code=department_code,
                department_name=department_name,
            )

        result = [
            asdict(department)
            for department in sorted(
                departments.values(),
                key=lambda item: (
                    item.department_name,
                    item.department_code,
                ),
            )
        ]

        return result

    def get_schedules(
        self,
        court_code: str,
        target_date: date | str | None = None,
        department_code: str | None = None,
        force_refresh: bool = False,
    ) -> list[dict[str, str]]:
        """
        특정 법원의 매각 일정을 추출합니다.

        target_date는 다음 형식을 모두 허용합니다.

        - datetime.date
        - "20260723"
        - "2026-07-23"

        department_code를 전달하면 해당 담당계만 필터링합니다.
        """
        normalized_court_code = self._clean_text(court_code)

        if not normalized_court_code:
            raise ValueError("court_code가 비어 있습니다.")

        normalized_department_code = self._clean_text(
            department_code
        )
        normalized_target_date = self._normalize_date(
            target_date
        )

        data = self.fetch_directory_data(
            force_refresh=force_refresh,
        )

        schedules: dict[
            tuple[str, str, str, str, str],
            AuctionSchedule,
        ] = {}

        for record in self._walk_dicts(data):
            record_court_code = self._clean_text(
                self._first_value(
                    record,
                    self.COURT_CODE_KEYS,
                )
            )

            if record_court_code != normalized_court_code:
                continue

            record_department_code = self._clean_text(
                self._first_value(
                    record,
                    self.DEPARTMENT_CODE_KEYS,
                )
            )

            if (
                normalized_department_code
                and record_department_code
                != normalized_department_code
            ):
                continue

            auction_date = self._normalize_date(
                self._first_value(
                    record,
                    self.AUCTION_DATE_KEYS,
                )
            )

            if not auction_date:
                continue

            if (
                normalized_target_date
                and auction_date != normalized_target_date
            ):
                continue

            court_name = self._clean_text(
                self._first_value(
                    record,
                    self.COURT_NAME_KEYS,
                )
            )
            department_name = self._clean_text(
                self._first_value(
                    record,
                    self.DEPARTMENT_NAME_KEYS,
                )
            )
            sale_time = self._normalize_time(
                self._first_value(
                    record,
                    self.SALE_TIME_KEYS,
                )
            )
            sale_place = self._clean_text(
                self._first_value(
                    record,
                    self.SALE_PLACE_KEYS,
                )
            )

            key = (
                normalized_court_code,
                record_department_code,
                auction_date,
                sale_time,
                sale_place,
            )

            schedules[key] = AuctionSchedule(
                court_code=normalized_court_code,
                court_name=court_name,
                department_code=record_department_code,
                department_name=department_name,
                auction_date=auction_date,
                sale_time=sale_time,
                sale_place=sale_place,
            )

        result = [
            asdict(schedule)
            for schedule in sorted(
                schedules.values(),
                key=lambda item: (
                    item.auction_date,
                    item.sale_time,
                    item.court_name,
                    item.department_name,
                ),
            )
        ]

        return result

    def inspect_structure(
        self,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """
        API 응답에 어떤 키가 존재하는지 확인합니다.

        실제 응답 필드명이 예상과 다를 때 실행하면
        법원·담당계·기일 관련 후보 키를 확인할 수 있습니다.
        """
        data = self.fetch_directory_data(
            force_refresh=force_refresh,
        )

        all_keys: set[str] = set()
        candidate_records: list[dict[str, Any]] = []

        keyword_fragments = (
            "cort",
            "court",
            "jiwon",
            "jdbn",
            "dept",
            "dxdy",
            "dspsl",
            "giil",
            "date",
            "place",
            "plc",
            "time",
            "hm",
        )

        for record in self._walk_dicts(data):
            all_keys.update(record.keys())

            matched_keys = [
                key
                for key in record.keys()
                if any(
                    fragment in key.lower()
                    for fragment in keyword_fragments
                )
            ]

            if matched_keys and len(candidate_records) < 100:
                candidate_records.append(
                    {
                        key: record.get(key)
                        for key in matched_keys
                    }
                )

        report = {
            "inspectedAt": datetime.now().isoformat(
                timespec="seconds"
            ),
            "allKeys": sorted(all_keys),
            "candidateRecords": candidate_records,
        }

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )
        output_path = (
            Path(RAW_DIR)
            / f"court_directory_structure_{timestamp}.json"
        )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        output_path.write_text(
            json.dumps(
                report,
                ensure_ascii=False,
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )

        report["savedPath"] = str(output_path)

        return report

    @classmethod
    def _walk_dicts(
        cls,
        value: Any,
    ) -> Iterable[dict[str, Any]]:
        """중첩된 JSON에서 모든 dict 객체를 순회합니다."""
        if isinstance(value, dict):
            yield value

            for child in value.values():
                yield from cls._walk_dicts(child)

        elif isinstance(value, list):
            for child in value:
                yield from cls._walk_dicts(child)

    @staticmethod
    def _first_value(
        record: dict[str, Any],
        keys: tuple[str, ...],
    ) -> Any:
        """후보 키 중 값이 존재하는 첫 번째 항목을 반환합니다."""
        for key in keys:
            value = record.get(key)

            if value is None:
                continue

            if isinstance(value, str) and not value.strip():
                continue

            return value

        return ""

    @staticmethod
    def _clean_text(value: Any) -> str:

        if value is None:
            return ""

        text = str(value).strip()

        text = " ".join(text.split())

        # 공백 제거 후 동일하게 비교
        if "경매법정" in text:
            text = text.replace(" ", "")

        return text

    @staticmethod
    def _looks_like_court_code(
        court_code: str,
    ) -> bool:
        """
        법원 코드 후보를 간단히 검증합니다.

        현재 확인된 형식은 B000210처럼 영문과 숫자가 섞인 형태입니다.
        """
        if len(court_code) < 4:
            return False

        return (
            any(character.isalpha() for character in court_code)
            and any(
                character.isdigit()
                for character in court_code
            )
        )

    @classmethod
    def _normalize_date(
        cls,
        value: date | str | Any | None,
    ) -> str:
        """날짜를 YYYYMMDD 형식으로 정규화합니다."""
        if value is None:
            return ""

        if isinstance(value, datetime):
            return value.strftime("%Y%m%d")

        if isinstance(value, date):
            return value.strftime("%Y%m%d")

        text = cls._clean_text(value)

        if not text:
            return ""

        digits = "".join(
            character
            for character in text
            if character.isdigit()
        )

        if len(digits) >= 8:
            return digits[:8]

        return ""

    @classmethod
    def _normalize_time(
        cls,
        value: Any,
    ) -> str:
        """시간을 HHMM 형식으로 정규화합니다."""
        text = cls._clean_text(value)

        if not text:
            return ""

        digits = "".join(
            character
            for character in text
            if character.isdigit()
        )

        if len(digits) >= 4:
            return digits[:4]

        if len(digits) == 3:
            return f"0{digits}"

        if len(digits) in (1, 2):
            return f"{int(digits):02d}00"

        return ""

    @staticmethod
    def _save_debug_response(
        data: Any,
        prefix: str,
    ) -> Path:
        """추출 실패 시 원본 API 응답을 저장합니다."""
        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )
        output_path = (
            Path(RAW_DIR)
            / f"{prefix}_{timestamp}.json"
        )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        output_path.write_text(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )

        return output_path