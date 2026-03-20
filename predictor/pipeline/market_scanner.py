"""
Market Scanner
Polymarket 마켓을 도메인별로 스캔하고 시뮬레이션 대상 선별.
우선순위: 유동성 높고, 마감일 임박하지 않고, 엣지 발굴 가능성 높은 마켓.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from predictor.polymarket.api_client import PolymarketClient, Market


# 도메인별 검색 키워드 & 태그
DOMAIN_CONFIG = {
    "sports": {
        "tags":     ["Sports", "NBA", "NFL", "Soccer", "MLB", "NHL", "Tennis", "MMA"],
        "keywords": ["champion", "win", "cup", "title", "playoffs", "super bowl",
                     "world series", "stanley cup", "finals"],
        "min_liquidity": 5_000,
    },
    "elections": {
        "tags":     ["Politics", "Elections", "Government"],
        "keywords": ["election", "president", "senate", "congress", "vote",
                     "mayor", "governor", "referendum", "poll"],
        "min_liquidity": 10_000,
    },
    "finance": {
        "tags":     ["Economics", "Finance", "Crypto", "Business"],
        "keywords": ["fed rate", "gdp", "inflation", "bitcoin", "etf",
                     "stock", "earnings", "ipo", "merger", "bankruptcy"],
        "min_liquidity": 5_000,
    },
    "entertainment": {
        "tags":     ["Entertainment", "Awards", "TV", "Movies", "Music"],
        "keywords": ["oscar", "grammy", "emmy", "golden globe", "academy award",
                     "season", "renewed", "cancelled", "box office"],
        "min_liquidity": 2_000,
    },
    "geopolitics": {
        "tags":     ["World", "International", "Geopolitics"],
        "keywords": ["war", "ceasefire", "treaty", "sanction", "nato",
                     "un resolution", "conflict", "diplomatic"],
        "min_liquidity": 5_000,
    },
}


@dataclass
class ScoredMarket:
    market:        Market
    domain:        str
    priority_score: float   # 높을수록 먼저 분석
    days_to_close: Optional[int]


class MarketScanner:
    def __init__(self, client: Optional[PolymarketClient] = None):
        self.client = client or PolymarketClient()

    def scan_domain(self, domain: str, limit: int = 30) -> list[ScoredMarket]:
        """특정 도메인의 마켓 스캔 & 우선순위 계산."""
        config = DOMAIN_CONFIG.get(domain)
        if not config:
            raise ValueError(f"Unknown domain: {domain}. Available: {list(DOMAIN_CONFIG)}")

        markets: list[Market] = []

        # 태그 기반 검색
        for tag in config["tags"]:
            found = self.client.search_markets(
                tag=tag,
                limit=limit,
                min_liquidity=config["min_liquidity"],
            )
            markets.extend(found)

        # 키워드 기반 검색 (중복 제거)
        seen_ids = {m.condition_id for m in markets}
        for kw in config["keywords"][:5]:  # 상위 5개만 (API 부하 제한)
            found = self.client.search_markets(
                keyword=kw,
                limit=20,
                min_liquidity=config["min_liquidity"],
            )
            for m in found:
                if m.condition_id not in seen_ids:
                    markets.append(m)
                    seen_ids.add(m.condition_id)

        # 우선순위 점수화
        scored = []
        now = datetime.now(timezone.utc)
        for m in markets:
            days = self._days_to_close(m.end_date, now)
            score = self._priority_score(m, days)
            scored.append(ScoredMarket(
                market=m, domain=domain,
                priority_score=score, days_to_close=days,
            ))

        return sorted(scored, key=lambda x: x.priority_score, reverse=True)

    def scan_all_domains(self, limit_per_domain: int = 20) -> list[ScoredMarket]:
        """모든 도메인 스캔."""
        all_markets = []
        for domain in DOMAIN_CONFIG:
            try:
                results = self.scan_domain(domain, limit=limit_per_domain)
                all_markets.extend(results)
                print(f"  [{domain}] {len(results)} markets found")
            except Exception as e:
                print(f"  [{domain}] Error: {e}")
        return sorted(all_markets, key=lambda x: x.priority_score, reverse=True)

    def _days_to_close(self, end_date: str, now: datetime) -> Optional[int]:
        if not end_date:
            return None
        try:
            close = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            return max(0, (close - now).days)
        except ValueError:
            return None

    def _priority_score(self, m: Market, days: Optional[int]) -> float:
        """
        우선순위 공식:
          - 유동성 많을수록 ↑ (신뢰도, 실제 배팅 가능)
          - 가격이 50%에 가까울수록 ↑ (불확실성 높음 = 엣지 가능성 높음)
          - 마감 7~30일 이내 ↑ (너무 멀면 비효율)
          - 마감 3일 이내 ↓ (정보 우위 불가)
        """
        liq_score  = min(m.liquidity / 100_000, 1.0)  # 10만 달러 기준 정규화
        uncertainty = 1.0 - abs(m.yes_price - 0.5) * 2  # 0.5 근처 = 1.0
        vol_score  = min(m.volume / 50_000, 1.0)

        timing = 0.5
        if days is not None:
            if 7 <= days <= 30:
                timing = 1.0
            elif 3 <= days < 7:
                timing = 0.8
            elif days < 3:
                timing = 0.2
            elif days > 60:
                timing = 0.3

        return (liq_score * 0.3 + uncertainty * 0.3 + vol_score * 0.2 + timing * 0.2)

    def top_opportunities(self, n: int = 10) -> list[ScoredMarket]:
        """전체 도메인에서 상위 N개 기회 반환."""
        all_markets = self.scan_all_domains()
        return all_markets[:n]
