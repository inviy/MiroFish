"""
Performance Tracker
예측 정확도 & 수익성 추적 대시보드.
실제 결과와 우리 예측을 비교해 모델 성능 검증.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


DATA_DIR = Path(__file__).parent.parent.parent / "data" / "predictions"


@dataclass
class PredictionRecord:
    id:            str
    question:      str
    domain:        str
    our_prob:      float          # 우리 예측 확률 (YES)
    mkt_price:     float          # 배팅 당시 시장 가격
    edge:          float          # our_prob - mkt_price
    side:          str            # YES / NO
    amount_usdc:   float          # 배팅 금액
    created_at:    str
    resolved_at:   Optional[str]  = None
    actual_result: Optional[bool] = None   # True=YES, False=NO
    pnl:           Optional[float] = None  # 수익 (USDC)
    condition_id:  Optional[str]  = None
    reasoning:     str            = ""


class PerformanceTracker:
    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.records_file = self.data_dir / "predictions.jsonl"

    # ── 기록 추가 ─────────────────────────────────────────────────────────────

    def record_prediction(self, record: PredictionRecord) -> None:
        with open(self.records_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")

    def resolve_prediction(
        self,
        prediction_id: str,
        actual_result: bool,
    ) -> Optional[PredictionRecord]:
        """실제 결과 업데이트 & PnL 계산."""
        records = self._load_all()
        updated = None
        for r in records:
            if r.id == prediction_id:
                r.actual_result = actual_result
                r.resolved_at   = datetime.utcnow().isoformat()

                # PnL 계산
                if r.side == "YES":
                    won = actual_result
                else:
                    won = not actual_result

                if won:
                    # 수익: 배팅금액 × (1/배팅가격 - 1)
                    price = r.mkt_price if r.side == "YES" else (1 - r.mkt_price)
                    r.pnl = r.amount_usdc * (1 / max(price, 0.01) - 1)
                else:
                    r.pnl = -r.amount_usdc

                updated = r
                break

        if updated:
            self._save_all(records)
        return updated

    # ── 분석 ─────────────────────────────────────────────────────────────────

    def summary(self) -> dict:
        records = self._load_all()
        resolved = [r for r in records if r.actual_result is not None]

        if not resolved:
            return {
                "total_predictions": len(records),
                "resolved": 0,
                "pending": len(records),
                "message": "No resolved predictions yet.",
            }

        wins = [r for r in resolved if r.pnl and r.pnl > 0]
        win_rate = len(wins) / len(resolved) if resolved else 0
        total_pnl = sum(r.pnl or 0 for r in resolved)
        total_staked = sum(r.amount_usdc for r in resolved)
        roi = total_pnl / total_staked if total_staked > 0 else 0

        # 브라이어 점수 (확률 보정 점수, 낮을수록 좋음)
        brier = sum(
            (r.our_prob - (1.0 if r.actual_result else 0.0)) ** 2
            for r in resolved
        ) / len(resolved)

        by_domain: dict[str, dict] = {}
        for r in resolved:
            d = by_domain.setdefault(r.domain, {"n": 0, "wins": 0, "pnl": 0.0})
            d["n"] += 1
            d["wins"] += 1 if (r.pnl or 0) > 0 else 0
            d["pnl"] += r.pnl or 0

        return {
            "total_predictions": len(records),
            "resolved":          len(resolved),
            "pending":           len(records) - len(resolved),
            "win_rate":          round(win_rate, 4),
            "total_pnl_usdc":    round(total_pnl, 2),
            "total_staked_usdc": round(total_staked, 2),
            "roi":               round(roi, 4),
            "brier_score":       round(brier, 4),
            "by_domain":         by_domain,
            "top_wins": sorted(
                [{"q": r.question, "pnl": r.pnl} for r in wins],
                key=lambda x: x["pnl"], reverse=True
            )[:5],
        }

    def print_dashboard(self) -> None:
        s = self.summary()
        print("\n" + "=" * 50)
        print("  MiroFish Prediction Performance Dashboard")
        print("=" * 50)
        print(f"  Total Predictions : {s['total_predictions']}")
        print(f"  Resolved          : {s['resolved']}")
        print(f"  Pending           : {s['pending']}")
        if s['resolved'] > 0:
            print(f"  Win Rate          : {s['win_rate']:.1%}")
            print(f"  Total PnL         : ${s['total_pnl_usdc']:,.2f}")
            print(f"  ROI               : {s['roi']:.2%}")
            print(f"  Brier Score       : {s['brier_score']:.4f}  (lower=better)")
            print("\n  By Domain:")
            for domain, data in s.get("by_domain", {}).items():
                wr = data["wins"] / data["n"] if data["n"] else 0
                print(f"    {domain:15} | {data['n']:3}bets | {wr:.0%} WR | ${data['pnl']:+.2f}")
        print("=" * 50 + "\n")

    # ── 내부 ─────────────────────────────────────────────────────────────────

    def _load_all(self) -> list[PredictionRecord]:
        if not self.records_file.exists():
            return []
        records = []
        with open(self.records_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(PredictionRecord(**json.loads(line)))
        return records

    def _save_all(self, records: list[PredictionRecord]) -> None:
        with open(self.records_file, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")
