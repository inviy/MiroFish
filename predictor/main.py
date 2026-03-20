"""
MiroFish Predictor - Main Entry Point

사용법:
  python predictor/main.py scan              # 전체 도메인 마켓 스캔
  python predictor/main.py predict <domain>  # 특정 도메인 예측 실행
  python predictor/main.py dashboard         # 성과 대시보드 출력
  python predictor/main.py demo              # 데모 실행 (dry-run)
"""

import sys
import json
import uuid
from datetime import datetime

from predictor.polymarket.api_client import PolymarketClient
from predictor.pipeline.market_scanner import MarketScanner
from predictor.pipeline.simulation_bridge import SimulationBridge
from predictor.domains.sports.seed_builder import SportsSeedBuilder
from predictor.domains.elections.seed_builder import ElectionSeedBuilder
from predictor.domains.finance.seed_builder import FinanceSeedBuilder
from predictor.dashboard.performance_tracker import PerformanceTracker, PredictionRecord


def cmd_scan():
    """마켓 스캔 & 상위 기회 출력."""
    print("\n[MiroFish Predictor] Scanning Polymarket for opportunities...\n")
    scanner = MarketScanner()
    opportunities = scanner.top_opportunities(n=10)

    print(f"{'#':<3} {'Domain':<14} {'Score':<7} {'Liq($)':<10} {'Price':<7} {'Days':<6} Question")
    print("-" * 100)
    for i, opp in enumerate(opportunities, 1):
        m = opp.market
        question_short = m.question[:55] + "..." if len(m.question) > 55 else m.question
        print(
            f"{i:<3} {opp.domain:<14} {opp.priority_score:<7.3f} "
            f"${m.liquidity:<9,.0f} {m.yes_price:<7.2%} "
            f"{str(opp.days_to_close):<6} {question_short}"
        )

    print(f"\nTotal opportunities found: {len(opportunities)}")
    return opportunities


def cmd_predict_demo():
    """
    데모: 스포츠 예측 파이프라인 시뮬레이션 (MiroFish 백엔드 없이).
    실제 배팅 없이 전체 흐름 확인용.
    """
    print("\n[DEMO MODE] MiroFish Sports Prediction Pipeline\n")

    # 1. 시드 생성
    builder = SportsSeedBuilder()
    seed = builder.build_seed(
        team_a="Los Angeles Lakers",
        team_b="Boston Celtics",
        event="NBA Finals 2025",
        sport="basketball",
        question="Will the Los Angeles Lakers win the NBA Finals?",
    )
    print(f"Question: {seed.question}")
    print(f"Seed text preview ({len(seed.seed_text)} chars):\n{seed.seed_text[:300]}...")

    # 2. 마켓 스캔 (유사 마켓 찾기)
    print("\n[Step 2] Scanning for matching Polymarket market...")
    client = PolymarketClient()
    markets = client.search_markets(keyword="NBA Finals", min_liquidity=1000)
    if markets:
        m = markets[0]
        print(f"  Found: {m.question}")
        print(f"  YES price: {m.yes_price:.2%}, Liquidity: ${m.liquidity:,.0f}")
    else:
        print("  No active market found (demo: using placeholder)")
        from predictor.polymarket.api_client import Market
        m = Market(
            condition_id="demo_001", question=seed.question,
            end_date="2025-06-30", liquidity=50000, volume=200000,
            yes_price=0.42, no_price=0.58, active=True, tags=["Sports", "NBA"],
        )

    # 3. 예측 결과 (데모: MiroFish 시뮬레이션 결과 모킹)
    print("\n[Step 3] Running simulation... (demo: using mock result)")
    our_prob = 0.55  # 실제로는 SimulationBridge.run_full_pipeline() 결과
    edge = our_prob - m.yes_price
    print(f"  Our predicted YES prob: {our_prob:.2%}")
    print(f"  Market price:           {m.yes_price:.2%}")
    print(f"  Edge:                   {edge:+.2%}")

    # 4. 베팅 결정
    min_edge = 0.03
    bet_amount = 100  # USDC
    if abs(edge) >= min_edge:
        side = "YES" if edge > 0 else "NO"
        print(f"\n[Step 4] PLACE BET: {side} ${bet_amount} USDC (edge={abs(edge):.2%})")
        result = client.place_order(m.condition_id, side, bet_amount, dry_run=True)
        print(f"  Order result: {result['status']}")

        # 5. 기록
        tracker = PerformanceTracker()
        record = PredictionRecord(
            id=str(uuid.uuid4())[:8],
            question=seed.question,
            domain="sports",
            our_prob=our_prob,
            mkt_price=m.yes_price,
            edge=abs(edge),
            side=side,
            amount_usdc=bet_amount,
            created_at=datetime.utcnow().isoformat(),
            condition_id=m.condition_id,
            reasoning="Demo run - Lakers recent form and historical Finals performance",
        )
        tracker.record_prediction(record)
        print(f"  Prediction recorded: ID={record.id}")
    else:
        print(f"\n[Step 4] No bet: edge {abs(edge):.2%} < minimum {min_edge:.2%}")

    print("\n[DEMO COMPLETE]\n")


def cmd_dashboard():
    tracker = PerformanceTracker()
    tracker.print_dashboard()


def main():
    commands = {
        "scan":      cmd_scan,
        "demo":      cmd_predict_demo,
        "dashboard": cmd_dashboard,
    }

    cmd = sys.argv[1] if len(sys.argv) > 1 else "demo"

    if cmd in commands:
        commands[cmd]()
    else:
        print(__doc__)
        print(f"Available commands: {', '.join(commands)}")


if __name__ == "__main__":
    main()
