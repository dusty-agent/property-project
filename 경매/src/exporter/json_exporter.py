import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from src.config import JSON_DIR
from src.utils import safe_filename


class JsonExporter:

    @staticmethod
    def _to_dict(property_item: Any) -> dict:
        """
        AuctionProperty 객체와 dict를 모두 JSON 저장 가능한 dict로 변환합니다.
        """
        if isinstance(property_item, dict):
            return property_item

        if hasattr(property_item, "to_dict"):
            return property_item.to_dict()

        raise TypeError(
            "JSON으로 저장할 수 없는 데이터입니다. "
            f"현재 타입: {type(property_item).__name__}"
        )

    @staticmethod
    def export(
        properties: Iterable[Any],
        filename: str,
        search_date: str = "",
    ) -> Path:
        items = [
            JsonExporter._to_dict(property_item)
            for property_item in properties
        ]

        payload = {
            "source": "대한민국 법원경매정보",
            "searchDate": search_date,
            "totalCount": len(items),
            "collectedAt": datetime.now().isoformat(
                timespec="seconds"
            ),
            "items": items,
        }

        output_path = (
            JSON_DIR
            / f"{safe_filename(filename)}.json"
        )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with output_path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                payload,
                file,
                ensure_ascii=False,
                indent=2,
            )

        return output_path