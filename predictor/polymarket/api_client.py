"""
Polymarket API Client
- CLOB API: market data, orderbook, trade history
- Gamma API: market search, metadata
- Supports USDC betting via crypto wallet
"""

import os
import time
import json
import hmac
import hashlib
import requests
from typing import Optional
from dataclasses import dataclass


GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API  = "https://clob.polymarket.com"


@dataclass
class Market:
    condition_id: str
    question: str
    end_date: str
    liquidity: float
    volume: float
    yes_price: float   # 0~1 (= implied probability)
    no_price: float
    active: bool
    tags: list[str]

    @property
    def spread(self) -> float:
        return 1.0 - self.yes_price - self.no_price


class PolymarketClient:
    def __init__(self, api_key: Optional[str] = None, private_key: Optional[str] = None):
        self.api_key     = api_key     or os.getenv("POLYMARKET_API_KEY")
        self.private_key = private_key or os.getenv("POLYMARKET_PRIVATE_KEY")
        self.session     = requests.Session()
        self.session.headers.update({"User-Agent": "MiroFish-Predictor/1.0"})

    # ── Market Discovery ──────────────────────────────────────────────────────

    def search_markets(
        self,
        keyword: str = "",
        tag: str = "",
        limit: int = 50,
        min_liquidity: float = 1000,
    ) -> list[Market]:
        """키워드/태그로 활성 마켓 검색."""
        params = {
            "active": "true",
            "closed": "false",
            "limit": limit,
            "offset": 0,
        }
        if keyword:
            params["search"] = keyword
        if tag:
            params["tag"] = tag

        resp = self.session.get(f"{GAMMA_API}/markets", params=params, timeout=10)
        resp.raise_for_status()
        raw = resp.json()

        markets = []
        for m in raw:
            try:
                tokens = m.get("tokens", [])
                yes_tok = next((t for t in tokens if t.get("outcome") == "Yes"), {})
                no_tok  = next((t for t in tokens if t.get("outcome") == "No"),  {})
                liquidity = float(m.get("liquidity", 0))
                if liquidity < min_liquidity:
                    continue
                markets.append(Market(
                    condition_id = m["conditionId"],
                    question     = m["question"],
                    end_date     = m.get("endDate", ""),
                    liquidity    = liquidity,
                    volume       = float(m.get("volume", 0)),
                    yes_price    = float(yes_tok.get("price", 0.5)),
                    no_price     = float(no_tok.get("price",  0.5)),
                    active       = m.get("active", True),
                    tags         = [t.get("label", "") for t in m.get("tags", [])],
                ))
            except (KeyError, ValueError, StopIteration):
                continue
        return markets

    def get_market(self, condition_id: str) -> Optional[Market]:
        resp = self.session.get(f"{GAMMA_API}/markets/{condition_id}", timeout=10)
        if resp.status_code != 200:
            return None
        m = resp.json()
        tokens   = m.get("tokens", [])
        yes_tok  = next((t for t in tokens if t.get("outcome") == "Yes"), {})
        no_tok   = next((t for t in tokens if t.get("outcome") == "No"),  {})
        return Market(
            condition_id = m["conditionId"],
            question     = m["question"],
            end_date     = m.get("endDate", ""),
            liquidity    = float(m.get("liquidity", 0)),
            volume       = float(m.get("volume", 0)),
            yes_price    = float(yes_tok.get("price", 0.5)),
            no_price     = float(no_tok.get("price",  0.5)),
            active       = m.get("active", True),
            tags         = [t.get("label", "") for t in m.get("tags", [])],
        )

    def get_orderbook(self, token_id: str) -> dict:
        resp = self.session.get(f"{CLOB_API}/book", params={"token_id": token_id}, timeout=10)
        resp.raise_for_status()
        return resp.json()

    # ── Edge Detection ────────────────────────────────────────────────────────

    def find_value_bets(
        self,
        markets: list[Market],
        our_probs: dict[str, float],   # condition_id → our YES probability
        min_edge: float = 0.03,        # 최소 3% 엣지
    ) -> list[dict]:
        """
        우리 예측 확률 vs 시장 가격 비교 → 엣지 있는 마켓 반환.
        edge = our_prob - market_yes_price  (양수면 YES 유리)
        """
        bets = []
        for market in markets:
            cid = market.condition_id
            if cid not in our_probs:
                continue
            our_p    = our_probs[cid]
            mkt_p    = market.yes_price
            edge     = our_p - mkt_p
            side     = "YES" if edge > 0 else "NO"
            abs_edge = abs(edge)
            if abs_edge < min_edge:
                continue
            bets.append({
                "condition_id": cid,
                "question":     market.question,
                "side":         side,
                "our_prob":     round(our_p, 4),
                "mkt_price":    round(mkt_p, 4),
                "edge":         round(abs_edge, 4),
                "liquidity":    market.liquidity,
                "expected_roi": round(abs_edge / (1 - our_p + 1e-9), 4),
            })
        return sorted(bets, key=lambda x: x["edge"], reverse=True)

    # ── Order Execution (requires wallet setup) ───────────────────────────────

    def place_order(
        self,
        condition_id: str,
        side: str,           # "YES" or "NO"
        amount_usdc: float,
        dry_run: bool = True,
    ) -> dict:
        """
        USDC 베팅 주문.
        dry_run=True 이면 실제 주문 없이 시뮬레이션만.
        실제 주문은 py-clob-client 라이브러리 필요.
        """
        order = {
            "condition_id":  condition_id,
            "side":          side,
            "amount_usdc":   amount_usdc,
            "timestamp":     int(time.time()),
            "dry_run":       dry_run,
        }
        if dry_run:
            print(f"[DRY RUN] Would place: {side} ${amount_usdc:.2f} on {condition_id}")
            return {"status": "dry_run", "order": order}

        # TODO: 실제 CLOB 주문 구현 (py-clob-client 연동)
        raise NotImplementedError("Live trading requires py-clob-client setup and funded wallet")

    # ── Portfolio Tracking ────────────────────────────────────────────────────

    def get_portfolio(self, wallet_address: str) -> dict:
        resp = self.session.get(
            f"{GAMMA_API}/positions",
            params={"user": wallet_address},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
