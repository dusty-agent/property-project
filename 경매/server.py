from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware


BASE_DIR = Path(__file__).resolve().parent
LATEST_JSON_PATH = (
    BASE_DIR
    / "output"
    / "json"
    / "auction_latest.json"
)

app = FastAPI(
    title="Property Deal Generator API",
    version="1.0.0",
)

# 로컬 Dustie와 향후 배포 주소에서 접근할 수 있도록 설정합니다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://dustie-web.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)


def read_latest_auction_data() -> dict[str, Any]:
    if not LATEST_JSON_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="auction_latest.json 파일이 없습니다.",
        )

    try:
        with LATEST_JSON_PATH.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"JSON 파일 형식이 올바르지 않습니다: {exc}",
        ) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"JSON 파일을 읽지 못했습니다: {exc}",
        ) from exc

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=500,
            detail="최신 경매 데이터가 객체 형식이 아닙니다.",
        )

    return data


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "Property Deal Generator API",
        "status": "running",
    }


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "auctionDataExists": LATEST_JSON_PATH.exists(),
    }


@app.get("/api/auction/latest")
def get_latest_auction() -> dict[str, Any]:
    return read_latest_auction_data()