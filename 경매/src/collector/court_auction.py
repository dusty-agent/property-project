import json
import re
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin

import requests

from src.collector.base import BaseCollector
from src.config import (
    COURT_AUCTION_BASE_URL,
    COURT_AUCTION_MAIN_URL,
    DEFAULT_TIMEOUT_SECONDS,
    RAW_DIR,
)
from src.utils import safe_filename, write_text


class CourtAuctionCollector(BaseCollector):
    """대한민국 법원경매정보 수집기."""

    MAIN_UI_PATH = "/pgj/ui/pgj100/PGJ111M01.xml"

    SEARCH_API_PATH = "/pgj/pgjsearch/searchControllerMain.on"

    SEARCH_REFERER = (
        f"{COURT_AUCTION_BASE_URL}"
        "/pgj/index.on?"
        "w2xPath=/pgj/ui/pgj100/PGJ153F00.xml"
    )
    
    def __init__(self) -> None:
        self.session = requests.Session()

        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/150.0.0.0 Safari/537.36"
                ),
                "Accept-Language": (
                    "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
                ),
                "Connection": "keep-alive",
            }
        )

    def _get(
        self,
        url: str,
        referer: str | None = None,
        accept: str | None = None,
    ) -> requests.Response:
        """공통 GET 요청 함수입니다."""
        headers: dict[str, str] = {}

        if referer:
            headers["Referer"] = referer

        if accept:
            headers["Accept"] = accept

        response = self.session.get(
            url,
            headers=headers,
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

        # 법원경매 페이지와 XML은 UTF-8 기반입니다.
        response.encoding = "utf-8"

        return response

    def initialize_session(self) -> dict:
        """루트 및 메인 페이지에 접속해 WebSquare 세션을 생성합니다."""
        root_response = self._get(
            f"{COURT_AUCTION_BASE_URL}/",
            accept=(
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
        )

        main_response = self._get(
            COURT_AUCTION_MAIN_URL,
            referer=root_response.url,
            accept=(
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
        )

        return {
            "root_response": root_response,
            "main_response": main_response,
        }

    def discover(self) -> dict:
        """
        법원경매 WebSquare 메인 XML을 내려받고,
        내부 참조 경로와 서비스 후보를 추출합니다.
        """
        initialized = self.initialize_session()

        root_response = initialized["root_response"]
        main_response = initialized["main_response"]

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        root_path = RAW_DIR / f"root_{timestamp}.html"
        main_path = RAW_DIR / f"main_{timestamp}.html"

        write_text(root_path, root_response.text)
        write_text(main_path, main_response.text)

        ui_url = urljoin(
            COURT_AUCTION_BASE_URL,
            self.MAIN_UI_PATH,
        )

        ui_response = self._get(
            ui_url,
            referer=main_response.url,
            accept="application/xml,text/xml,*/*;q=0.8",
        )

        ui_path = RAW_DIR / f"PGJ111M01_{timestamp}.xml"
        write_text(ui_path, ui_response.text)

        references = self._extract_references(ui_response.text)
        keywords = self._extract_keyword_lines(ui_response.text)

        report = {
            "source": "대한민국 법원경매정보",
            "discoveredAt": datetime.now().isoformat(
                timespec="seconds"
            ),
            "root": {
                "url": root_response.url,
                "statusCode": root_response.status_code,
                "length": len(root_response.text),
                "savedPath": str(root_path),
            },
            "main": {
                "url": main_response.url,
                "statusCode": main_response.status_code,
                "length": len(main_response.text),
                "savedPath": str(main_path),
            },
            "mainUi": {
                "url": ui_response.url,
                "statusCode": ui_response.status_code,
                "contentType": ui_response.headers.get(
                    "Content-Type",
                    "",
                ),
                "length": len(ui_response.text),
                "savedPath": str(ui_path),
            },
            "cookies": self.session.cookies.get_dict(),
            "references": references,
            "keywordLines": keywords,
        }

        report_path = (
            RAW_DIR / f"discovery_report_{timestamp}.json"
        )

        report_path.write_text(
            json.dumps(
                report,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        report["reportPath"] = str(report_path)

        return report

    @staticmethod
    def _extract_references(xml_text: str) -> dict:
        """XML에서 화면·스크립트·서비스 경로 후보를 추출합니다."""
        path_pattern = re.compile(
            r"""(?:
                https?://[^\s"'<>]+
                |
                /pgj/[A-Za-z0-9_./?=&:%-]+
            )""",
            re.VERBOSE,
        )

        all_paths = sorted(
            {
                match.rstrip(");,")
                for match in path_pattern.findall(xml_text)
            }
        )

        xml_paths = [
            path
            for path in all_paths
            if ".xml" in path.lower()
        ]

        script_paths = [
            path
            for path in all_paths
            if any(
                extension in path.lower()
                for extension in (".js", ".wq")
            )
        ]

        service_paths = [
            path
            for path in all_paths
            if any(
                keyword in path.lower()
                for keyword in (
                    "service",
                    "select",
                    "search",
                    "query",
                    "retrieve",
                    "list",
                    ".on",
                )
            )
        ]

        return {
            "all": all_paths,
            "xml": xml_paths,
            "scripts": script_paths,
            "serviceCandidates": service_paths,
        }

    @staticmethod
    def _extract_keyword_lines(
        xml_text: str,
    ) -> dict[str, list[str]]:
        """조회 구조와 관계있는 줄을 키워드별로 수집합니다."""
        keyword_groups = {
            "경매": ["경매", "auction"],
            "사건": ["사건", "case"],
            "기일": ["기일", "date"],
            "검색": ["검색", "조회", "search", "select"],
            "서비스": [
                "submission",
                "service",
                "action",
                "ref=",
                "target=",
            ],
        }

        lines = xml_text.splitlines()
        result: dict[str, list[str]] = {}

        for group_name, keywords in keyword_groups.items():
            matched_lines: list[str] = []

            for line_number, line in enumerate(lines, start=1):
                lowered = line.lower()

                if any(
                    keyword.lower() in lowered
                    for keyword in keywords
                ):
                    cleaned = line.strip()

                    if cleaned:
                        matched_lines.append(
                            f"{line_number}: {cleaned}"
                        )

                if len(matched_lines) >= 100:
                    break

            result[group_name] = matched_lines

        return result

    @staticmethod
    def _build_search_payload(
        court_code: str,
        department_code: str,
        auction_date: str,
        sale_time: str,
        sale_place: str,
        page_no: int,
        page_size: int,
    ) -> dict:
        """법원경매 물건 상세검색 요청 Payload를 생성합니다."""
        return {
            "dma_pageInfo": {
                "pageNo": page_no,
                "pageSize": page_size,
                "bfPageNo": "",
                "startRowNo": "",
                "totalCnt": "",
                "totalYn": "Y",
                "groupTotalCount": "",
            },
            "dma_srchGdsDtlSrchInfo": {
                "rletDspslSpcCondCd": "",
                "bidDvsCd": "000331",
                "mvprpRletDvsCd": "",
                "cortAuctnSrchCondCd": "0004601",
                "rprsAdongSdCd": "",
                "rprsAdongSggCd": "",
                "rprsAdongEmdCd": "",
                "rdnmSdCd": "",
                "rdnmSggCd": "",
                "rdnmNo": "",
                "mvprpDspslPlcAdongSdCd": "",
                "mvprpDspslPlcAdongSggCd": "",
                "mvprpDspslPlcAdongEmdCd": "",
                "rdDspslPlcAdongSdCd": "",
                "rdDspslPlcAdongSggCd": "",
                "rdDspslPlcAdongEmdCd": "",
                "cortOfcCd": court_code,
                "jdbnCd": department_code,
                "execrOfcDvsCd": "",
                "lclDspslGdsLstUsgCd": "",
                "mclDspslGdsLstUsgCd": "",
                "sclDspslGdsLstUsgCd": "",
                "cortAuctnMbrsId": "",
                "aeeEvlAmtMin": "",
                "aeeEvlAmtMax": "",
                "lwsDspslPrcRateMin": "",
                "lwsDspslPrcRateMax": "",
                "flbdNcntMin": "",
                "flbdNcntMax": "",
                "objctArDtsMin": "",
                "objctArDtsMax": "",
                "mvprpArtclKndCd": "",
                "mvprpArtclNm": "",
                "mvprpAtchmPlcTypCd": "",
                "notifyLoc": "",
                "lafjOrderBy": "",
                "pgmId": "PGJ153M01",
                "csNo": "",
                "cortStDvs": "1",
                "statNum": "",
                "bidBgngYmd": "",
                "bidEndYmd": "",
                "dspslDxdyYmd": auction_date,
                "fstDspslHm": sale_time,
                "scndDspslHm": "",
                "thrdDspslHm": "",
                "fothDspslHm": "",
                "dspslPlcNm": sale_place,
                "lwsDspslPrcMin": "",
                "lwsDspslPrcMax": "",
                "grbxTypCd": "",
                "gdsVendNm": "",
                "fuelKndCd": "",
                "carMdyrMax": "",
                "carMdyrMin": "",
                "carMdlNm": "",
                "sideDvsCd": "2",
            },
        }

    def search_page(
        self,
        court_code: str,
        department_code: str,
        auction_date: str,
        sale_time: str = "1000",
        sale_place: str = "",
        page_no: int = 1,
        page_size: int = 10,
    ) -> dict:
        """특정 법원·경매계·기일의 물건목록 한 페이지를 조회합니다."""
        if page_no < 1:
            raise ValueError("page_no는 1 이상이어야 합니다.")

        if page_size < 1:
            raise ValueError("page_size는 1 이상이어야 합니다.")

        self.initialize_session()

        # 브라우저 요청과 동일하게 법원 코드 쿠키를 설정합니다.
        self.session.cookies.set(
            "cortOfcCd",
            court_code,
            domain="www.courtauction.go.kr",
            path="/",
        )

        url = urljoin(
            COURT_AUCTION_BASE_URL,
            self.SEARCH_API_PATH,
        )

        payload = self._build_search_payload(
            court_code=court_code,
            department_code=department_code,
            auction_date=auction_date,
            sale_time=sale_time,
            sale_place=sale_place,
            page_no=page_no,
            page_size=page_size,
        )

        response = self.session.post(
            url,
            json=payload,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json;charset=UTF-8",
                "Origin": COURT_AUCTION_BASE_URL,
                "Referer": self.SEARCH_REFERER,
                "SC-Userid": "SYSTEM",
                "submissionid": (
                    "mf_wfm_mainFrame_sbm_selectGdsDtlSrch"
                ),
            },
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )

        response.raise_for_status()
        response.encoding = "utf-8"

        try:
            response_data = response.json()
        except ValueError as error:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            error_path = (
                RAW_DIR
                / f"search_error_{auction_date}_{timestamp}.txt"
            )

            write_text(error_path, response.text)

            raise RuntimeError(
                "물건 검색 응답이 JSON 형식이 아닙니다. "
                f"원본 응답: {error_path}"
            ) from error

        if response_data.get("status") != 200:
            raise RuntimeError(
                "법원경매 물건 조회에 실패했습니다: "
                f"{response_data.get('message', '알 수 없는 오류')}"
            )

        data = response_data.get("data") or {}
        page_info = data.get("dma_pageInfo") or {}
        items = data.get("dlt_srchResult") or []

        return {
            "items": items,
            "page_info": page_info,
            "response": response_data,
            "request": {
                "url": url,
                "payload": payload,
            },
        }

    def search_all_pages(
        self,
        court_code: str,
        department_code: str,
        auction_date: str,
        sale_time: str = "1000",
        sale_place: str = "",
        page_size: int = 10,
    ) -> dict:
        """검색 결과의 모든 페이지를 순회하여 원본 행을 수집합니다."""
        all_items: list[dict] = []
        page_no = 1
        total_count: int | None = None
        group_total_count: int | None = None

        while total_count is None or len(all_items) < total_count:
            page_result = self.search_page(
                court_code=court_code,
                department_code=department_code,
                auction_date=auction_date,
                sale_time=sale_time,
                sale_place=sale_place,
                page_no=page_no,
                page_size=page_size,
            )

            page_items = page_result["items"]
            page_info = page_result["page_info"]

            if total_count is None:
                total_count = int(page_info.get("totalCnt") or 0)
                group_total_count = int(
                    page_info.get("groupTotalCount") or 0
                )

            if not page_items:
                break

            all_items.extend(page_items)

            print(
                f"- {page_no}페이지 수집: "
                f"{len(page_items)}개 "
                f"(누적 {len(all_items)}/{total_count})"
            )

            page_no += 1

        # 응답 중복이나 서버 페이지 오차에 대비합니다.
        if total_count is not None:
            all_items = all_items[:total_count]

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        raw_path = (
            RAW_DIR
            / f"search_{court_code}_{auction_date}_{timestamp}.json"
        )

        raw_result = {
            "source": "대한민국 법원경매정보",
            "collectedAt": datetime.now().isoformat(
                timespec="seconds"
            ),
            "courtCode": court_code,
            "departmentCode": department_code,
            "auctionDate": auction_date,
            "saleTime": sale_time,
            "salePlace": sale_place,
            "totalCount": total_count or len(all_items),
            "groupTotalCount": group_total_count or 0,
            "items": all_items,
        }

        raw_path.write_text(
            json.dumps(
                raw_result,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return {
            "items": all_items,
            "total_count": total_count or len(all_items),
            "group_total_count": group_total_count or 0,
            "raw_path": str(raw_path),
        }

    def collect_by_date(
        self,
        auction_date: date,
    ) -> list:
        """
        지정일 전체 수집은 탐색 완료 후 구현합니다.
        """
        raise NotImplementedError(
            "아직 기일별 목록 조회 요청을 탐색하는 단계입니다."
        )

    def collect_by_case_number(
        self,
        case_number: str,
    ) -> list:
        """
        사건번호 단건 수집은 탐색 완료 후 구현합니다.
        """
        case_number = safe_filename(case_number)

        raise NotImplementedError(
            f"아직 사건번호 조회 요청을 탐색하는 단계입니다: "
            f"{case_number}"
        )
        
    def fetch_main_info(self) -> dict:
        """메인 화면의 경매 일정 및 주요 물건 정보를 조회합니다."""
        self.initialize_session()

        url = (
            f"{COURT_AUCTION_BASE_URL}"
            "/pgj/pgj111/selectRletYrDspslStats.on"
        )

        response = self.session.post(
            url,
            json={"key1": ""},
            headers={
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json;charset=UTF-8",
                "Referer": COURT_AUCTION_MAIN_URL,
                "Origin": COURT_AUCTION_BASE_URL,
                "X-Requested-With": "XMLHttpRequest",
            },
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )

        response.raise_for_status()
        response.encoding = "utf-8"

        try:
            data = response.json()
        except ValueError as error:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            error_path = RAW_DIR / f"main_info_error_{timestamp}.txt"
            write_text(error_path, response.text)

            raise RuntimeError(
                "메인 정보 응답이 JSON이 아닙니다. "
                f"응답을 저장했습니다: {error_path}"
            ) from error

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = RAW_DIR / f"main_info_{timestamp}.json"

        output_path.write_text(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return {
            "data": data,
            "statusCode": response.status_code,
            "url": response.url,
            "savedPath": str(output_path),
        }