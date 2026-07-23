import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent

if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))


from src.collector.court_auction import CourtAuctionCollector
from src.collector.mapper import merge_items
from src.config import ensure_directories
from src.exporter.json_exporter import JsonExporter


COURT_CODE = "B000210"
DEPARTMENT_CODE = "1011"
AUCTION_DATE = "20260723"
SALE_TIME = "1000"
SALE_PLACE = "경매법정 4별관 211호"
PAGE_SIZE = 10


def main() -> None:
    ensure_directories()

    print("=" * 64)
    print("법원경매 물건목록 수집 테스트")
    print("=" * 64)

    collector = CourtAuctionCollector()

    try:
        result = collector.search_all_pages(
            court_code=COURT_CODE,
            department_code=DEPARTMENT_CODE,
            auction_date=AUCTION_DATE,
            sale_time=SALE_TIME,
            sale_place=SALE_PLACE,
            page_size=PAGE_SIZE,
        )

    except Exception as error:
        print("\n[실패] 물건 수집 중 오류가 발생했습니다.")
        print(f"[오류 종류] {type(error).__name__}")
        print(f"[오류 내용] {error}")
        return

    raw_items = result.get("items", [])

    print("\n[완료] 물건목록 수집이 끝났습니다.")
    print(f"[원본 행 수] {len(raw_items):,}개")
    print(
        f"[서버 전체 행 수] "
        f"{result.get('total_count', 0):,}개"
    )
    print(
        f"[화면상 사건 그룹 수] "
        f"{result.get('group_total_count', 0):,}개"
    )
    print(f"[RAW 저장] {result.get('raw_path', '')}")

    if not raw_items:
        print("\n[안내] 수집된 물건이 없습니다.")
        return

    first_item = raw_items[0]

    print("\n[첫 번째 원본 행]")
    print(f"- 사건번호: {first_item.get('srnSaNo', '')}")
    print(f"- 법원: {first_item.get('jiwonNm', '')}")
    print(f"- 담당계: {first_item.get('jpDeptNm', '')}")
    print(f"- 주소: {first_item.get('printSt', '').strip()}")
    print(f"- 용도: {first_item.get('dspslUsgNm', '')}")
    print(f"- 감정가: {first_item.get('gamevalAmt', '')}")
    print(f"- 최저가: {first_item.get('minmaePrice', '')}")

    try:
        properties = merge_items(raw_items)

        print("\n[병합 결과]")
        print(f"- 원본 행: {len(raw_items):,}개")
        print(f"- 경매 물건: {len(properties):,}개")

        filename = (
            f"auction_{COURT_CODE}_{AUCTION_DATE}"
        )

        json_path = JsonExporter.export(
            properties=properties,
            filename=filename,
            search_date=AUCTION_DATE,
        )

        latest_json_path = JsonExporter.export(
            properties=properties,
            filename="auction_latest",
            search_date=AUCTION_DATE,
        )

    except Exception as error:
        print("\n[실패] 데이터 병합 또는 JSON 저장 중 오류가 발생했습니다.")
        print(f"[오류 종류] {type(error).__name__}")
        print(f"[오류 내용] {error}")
        return

    print("\n[JSON 저장 완료]")
    print(f"- 날짜별 JSON: {json_path}")
    print(f"- 최신 UI용 JSON: {latest_json_path}")

    print("\n" + "=" * 64)
    print("전체 작업이 완료되었습니다.")
    print("=" * 64)


if __name__ == "__main__":
    main()