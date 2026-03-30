# -*- coding: utf-8 -*-
"""네이버 멤버십 관점 주간 뉴스브리핑 수집·섹션 분류 (네이버 뉴스 검색 API)."""
import os
import re
import json
from pathlib import Path
from datetime import datetime, timedelta

from src.config import get_naver_search_credentials
from src.news_collector import (
    fetch_naver_news,
    _strip_html,
    _parse_pubdate,
    _normalize_url,
    _normalize_title,
)

BRIEFING_CACHE_FILE = "membership_briefing_recent.json"

BRIEFING_SEARCH_QUERIES = [
    "아마존 이커머스",
    "월마트 온라인몰",
    "타겟 배송",
    "라쿠텐 쇼핑",
    "알리익스프레스",
    "국내 이커머스",
    "온라인 쇼핑 거래액",
    "쿠팡 와우",
    "유니버스 클럽 신세계",
    "컬리 멤버스",
    "쿠팡 SSG 마켓플레이스",
    "지마켓 11번가",
    "올리브영 온라인매출",
    "무신사 커머스",
    "29cm 패션",
    "당근마켓",
    "지그재그 패션",
    "다이소 매출",
    "제휴 멤버십 할인",
    "넷플릭스 요금제",
    "쿠팡플레이 티빙",
    "현대카드 제휴",
    "카카오페이 혜택",
    "배민 멤버십",
    "롯데시네마 제휴",
    "CU GS25 편의점 행사",
    "펫 반려동물 할인",
    "네이버 멤버십 혜택",
    "스포티파이 구독",
    "쏘카 우버 모빌리티",
]

SECTION_DEFS = [
    (
        "global_ecommerce",
        "글로벌 이커머스 소식",
        (
            "아마존", "amazon", "월마트", "walmart", "타겟", "target",
            "라쿠텐", "rakuten", "알리", "알리익스", "이베이", "ebay",
        ),
    ),
    (
        "domestic_ecommerce",
        "국내 이커머스 소식",
        (
            "국내 이커머스", "이커머스 시장", "온라인 쇼핑", "오픈마켓",
            "거래액", "이커머스 동향",
        ),
    ),
    (
        "ecommerce_membership",
        "이커머스 멤버십",
        (
            "와우", "유니버스 클럽", "멤버스", "컬리 멤버", "쿠팡 플레이", "멤버십 구독",
        ),
    ),
    (
        "marketplace",
        "이커머스 > 마켓플레이스 뉴스",
        (
            "쿠팡", "SSG", "지마켓", "11번가", "옥션", "마켓플레이스", "G마켓",
        ),
    ),
    (
        "vertical",
        "이커머스 > 버티컬 뉴스",
        (
            "올리브영", "무신사", "29cm", "당근", "지그재그", "버티컬", "뷰티 커머스",
        ),
    ),
    (
        "commerce",
        "커머스",
        ("다이소", "오프라인", "대형마트", "편의점", "소매"),
    ),
    (
        "partnership_benefit",
        "제휴 혜택 관련 뉴스",
        (
            "제휴", "멤버십 혜택", "할인", "구독", "프로모션", "바우처",
            "네이버 멤버십", "네이버멤버십",
        ),
    ),
    (
        "digital_content",
        "디지털 콘텐츠",
        (
            "넷플릭스", "쿠팡플레이", "티빙", "웨이브", "wavve",
            "스포티파이", "spotify", "디즈니", "OTT", "스트리밍",
        ),
    ),
    (
        "card",
        "카드사",
        (
            "현대카드", "신한카드", "삼성카드", "카카오페이", "토스", "카드사", "신용카드",
        ),
    ),
    (
        "other",
        "기타",
        (
            "배민", "우아한형제들", "쿠팡이츠", "롯데시네마", "CGV", "메가박스",
            "CU", "GS25", "펫", "반려동물", "우버", "쏘카", "티맵", "모빌리티",
        ),
    ),
]

MEMBERSHIP_BOOST = (
    "네이버 멤버십", "네이버멤버십", "네이버 플러스", "스포티파이", "펫", "베이비",
    "바우처", "우버", "쏘카", "롯데마트", "제타", "배민",
)

_EMPTY_MSG = (
    "브리핑 후보 뉴스가 최근 기간 내에 없거나, 네이버 검색 API 설정이 필요합니다."
)


def _briefing_should_exclude(title_plain: str, body_plain: str) -> bool:
    t = title_plain or ""
    full = (title_plain or "") + " " + (body_plain or "")
    if re.search(r"\[[^\]]*칼럼[^\]]*\]", t):
        return True
    if "사설" in t:
        return True
    if "위클립" in t or "[위클립]" in t:
        return True
    if len(full.strip()) < 8:
        return True
    return False


def _score_sections(title_plain: str, body_plain: str) -> dict:
    text = ((title_plain or "") + " " + (body_plain or "")).lower()
    scores = {}
    for sid, _title, keywords in SECTION_DEFS:
        s = 0
        for kw in keywords:
            if kw.lower() in text:
                s += 2 if len(kw) >= 3 else 1
        scores[sid] = s
    boost = sum(2 for k in MEMBERSHIP_BOOST if k.lower() in text)
    if boost:
        scores["partnership_benefit"] = scores.get("partnership_benefit", 0) + min(boost, 6)
        scores["other"] = scores.get("other", 0) + min(boost, 4)
    best_id = max(scores, key=lambda k: scores[k])
    if scores[best_id] == 0:
        return {"other": 1}
    return scores


def _pick_section_id(title_plain: str, body_plain: str) -> str:
    sc = _score_sections(title_plain, body_plain)
    return max(sc, key=lambda k: sc[k])


def collect_membership_briefing_recent(config: dict, cache_dir: Path, days: int = 14):
    cid, csec = get_naver_search_credentials(config)
    cache_dir = Path(cache_dir)
    if os.environ.get("VERCEL"):
        cache_dir = Path("/tmp/news_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / BRIEFING_CACHE_FILE

    if not cid or not csec:
        return {
            "collected_at": datetime.now().isoformat(),
            "sections": [],
            "message": "네이버 뉴스 검색 API: NAVER_CLIENT_ID/SECRET(환경변수) 또는 config의 naver_search를 설정하면 뉴스브리핑이 표시됩니다.",
        }

    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            collected = datetime.fromisoformat(data.get("collected_at", "2000-01-01"))
            if (datetime.now() - collected).total_seconds() < 3600:
                return data
        except Exception:
            pass

    raw_items = []
    try:
        for q in BRIEFING_SEARCH_QUERIES:
            raw_items.extend(fetch_naver_news(q, cid, csec, display=15, sort="date"))
    except Exception as e:
        return {
            "collected_at": datetime.now().isoformat(),
            "sections": [],
            "message": "뉴스 API 오류: " + str(e),
        }

    cutoff = (datetime.now() - timedelta(days=days)).date()
    seen_url = set()
    seen_title = set()
    unique = []
    for x in raw_items:
        raw_link = (x.get("link") or "").strip()
        raw_title = (x.get("title") or "").strip()
        title = _strip_html(raw_title)
        desc = _strip_html((x.get("description") or "").strip())
        link = _strip_html(raw_link) or raw_link
        url_key = _normalize_url(link)
        title_key = _normalize_title(title) if title else ""
        pub = _parse_pubdate(x.get("pubDate"))
        if pub is not None:
            pub_date = pub.date() if hasattr(pub, "date") else pub
            if hasattr(pub_date, "year") and pub_date < cutoff:
                continue
        if _briefing_should_exclude(title, title + " " + desc):
            continue
        if not title and not link:
            continue
        if url_key and url_key in seen_url:
            continue
        if title_key and title_key in seen_title:
            continue
        if url_key:
            seen_url.add(url_key)
        if title_key:
            seen_title.add(title_key)
        sid = _pick_section_id(title, desc)
        date_str = pub.strftime("%Y-%m-%d") if pub else ""
        unique.append({
            "title": title,
            "link": link or x.get("link"),
            "date": date_str,
            "section_id": sid,
        })

    by_section = {sid: [] for sid, _, __ in SECTION_DEFS}
    for item in unique:
        sid = item["section_id"]
        if sid not in by_section:
            sid = "other"
        row = {k: v for k, v in item.items() if k != "section_id"}
        by_section[sid].append(row)

    order = [s[0] for s in SECTION_DEFS]
    sections = []
    for sid in order:
        meta = next((s for s in SECTION_DEFS if s[0] == sid), None)
        if not meta:
            continue
        items = by_section.get(sid, [])[:25]
        if not items:
            continue
        sections.append({"id": sid, "title": meta[1], "items": items})

    out = {
        "collected_at": datetime.now().isoformat(),
        "sections": sections,
    }
    if not sections:
        out["message"] = _EMPTY_MSG
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return out
