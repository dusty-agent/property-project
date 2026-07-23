from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class AuctionProperty:
    # 고유 식별 정보
    court: str = ""
    court_code: str = ""
    case_number: str = ""
    item_number: str = ""
    department: str = ""

    # 물건 기본 정보
    title: str = ""
    property_type: str = ""
    address: str = ""
    road_address: str = ""
    building_name: str = ""

    # 가격 정보
    appraisal_price: Optional[int] = None
    minimum_price: Optional[int] = None
    minimum_price_rate: Optional[float] = None
    deposit_price: Optional[int] = None
    failed_auction_count: Optional[int] = None

    # 매각 일정
    auction_date: str = ""
    auction_time: str = ""
    status: str = ""

    # 토지·건물 정보
    land_area_m2: Optional[float] = None
    building_area_m2: Optional[float] = None
    land_share: str = ""
    sale_target: str = ""

    # 사건 세부 정보
    claim_amount: Optional[int] = None
    appraisal_date: str = ""
    remarks: str = ""

    # 첨부 및 이미지
    image_urls: list[str] = field(default_factory=list)
    document_links: dict[str, str] = field(default_factory=dict)

    # 원문 추적 정보
    source_url: str = ""
    source_text: str = ""
    source_data: dict[str, Any] = field(default_factory=dict)

    # 수집 정보
    collected_at: str = ""

    @property
    def id(self) -> str:
        """Finder와 데이터 저장에 사용할 고유 ID."""
        parts = [
            self.court or "unknown-court",
            self.case_number or "unknown-case",
            self.item_number or "0",
        ]
        return "-".join(parts)

    def calculate_minimum_price_rate(self) -> None:
        """감정가 대비 최저가 비율을 계산합니다."""
        if (
            self.appraisal_price is not None
            and self.appraisal_price > 0
            and self.minimum_price is not None
        ):
            self.minimum_price_rate = round(
                self.minimum_price / self.appraisal_price * 100,
                2,
            )

    def to_dict(self) -> dict:
        result = asdict(self)
        result["id"] = self.id
        return result