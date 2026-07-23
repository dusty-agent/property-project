from collections import OrderedDict
from datetime import datetime


def to_int(value):
    if value in ("", None):
        return None

    try:
        return int(str(value).replace(",", ""))
    except Exception:
        return None


def format_date(value):
    if not value:
        return None

    try:
        return datetime.strptime(value, "%Y%m%d").strftime("%Y-%m-%d")
    except Exception:
        return value


def format_time(value):
    if not value:
        return None

    value = str(value).zfill(4)

    return f"{value[:2]}:{value[2:]}"


def build_property(row):
    """
    토지 / 건물 목록 하나 생성
    """

    description = row.get("convAddr")

    if not description:
        description = row.get("pjbBuldList")

    if not description:
        description = row.get("areaList")

    return {
        "list_number": int(row["mokmulSer"]),
        "type": row.get("mokGbncd"),
        "description": description,
        "area": row.get("areaList"),
        "building": row.get("pjbBuldList"),
        "land": row.get("jimokList"),
    }


def merge_items(rows):
    """
    groupmaemulser 기준 병합
    """

    merged = OrderedDict()

    for row in rows:

        key = row["groupmaemulser"]

        if key not in merged:

            merged[key] = {

                "detail_id": row["docid"],

                "group_id": key,

                "case_number": row["srnSaNo"],

                "court": row["jiwonNm"],

                "department": row["jpDeptNm"],

                "phone": row["tel"],

                "address": row["printSt"].strip(),

                "road_address": row.get("bgPlaceRdAllAddr"),

                "property_type": row["dspslUsgNm"],

                "remarks": row["mulBigo"],

                "failed_count": to_int(row["yuchalCnt"]),

                "auction_count": to_int(row["maeGiilCnt"]),

                "appraisal_price": to_int(row["gamevalAmt"]),

                "minimum_price": to_int(row["minmaePrice"]),

                "minimum_rate": to_int(
                    row["notifyMinmaePriceRate1"]
                ),

                "auction_date": format_date(
                    row["maeGiil"]
                ),

                "auction_time": format_time(
                    row["maeHh1"]
                ),

                "sale_place": row["maePlace"],

                "telephone": row["tel"],

                "latitude": row.get("wgs84Ycordi"),

                "longitude": row.get("wgs84Xcordi"),

                "properties": [],

                "raw": [],
            }

        merged[key]["properties"].append(
            build_property(row)
        )

        merged[key]["raw"].append(row)

    return list(merged.values())