"""
Finance Domain - Seed Data Builder
금융/경제 예측용 시드 데이터 생성.
연준 금리 결정, 실적 발표, 암호화폐 이벤트, M&A 등.
"""

import requests
from dataclasses import dataclass
from typing import Optional


@dataclass
class FinanceSeed:
    question: str
    seed_text: str
    domain: str = "finance"


class FinanceSeedBuilder:
    def __init__(self, alpha_vantage_key: Optional[str] = None):
        self.av_key = alpha_vantage_key
        self.session = requests.Session()

    def build_macro_seed(
        self,
        event: str,
        question: str,
        context: str = "",
    ) -> FinanceSeed:
        """거시경제 이벤트 시드 (연준 결정, GDP, 인플레이션 등)."""
        seed = f"""
=== FINANCIAL/ECONOMIC EVENT ANALYSIS ===

EVENT: {event}
QUESTION: {question}

=== MACRO CONTEXT ===
{context if context else self._default_macro_context(event)}

=== MARKET PARTICIPANT DYNAMICS ===

Different market participants interpret economic signals differently:
- Institutional investors: Focus on long-term structural trends
- Retail investors: React to headlines and social media sentiment
- Hedge funds: Look for contrarian opportunities and market dislocations
- Central banks: Respond to dual mandate (employment + inflation)

=== ANALYST CONSENSUS ===

Wall Street analysts are divided on the outcome:
- Bull case: Favorable macro conditions support positive outcome
- Bear case: Structural headwinds and external risks create uncertainty
- Base case: Market consensus reflects current pricing in derivatives

=== SOCIAL & BEHAVIORAL FINANCE ===

Market psychology and behavioral patterns:
- Fear and greed index signaling current market sentiment
- Options market positioning indicating trader expectations
- Social media sentiment on financial platforms (Twitter/X, Reddit r/investing)
- Retail investor activity through commission-free brokers

The simulation models how different participant groups react to new information
and how their interactions shape the collective market outcome.
"""
        return FinanceSeed(question=question, seed_text=seed)

    def build_crypto_seed(self, token: str, event: str, question: str) -> FinanceSeed:
        """암호화폐 이벤트 시드 (ETF 승인, 하락/상승 예측 등)."""
        crypto_context = f"""
=== CRYPTOCURRENCY EVENT: {token} ===

EVENT: {event}

Cryptocurrency markets are uniquely driven by:
1. Regulatory developments and government stance
2. Institutional adoption and ETF inflows
3. On-chain metrics (wallet activity, DeFi TVL, exchange flows)
4. Social media influence (Twitter, Telegram, Discord communities)
5. Macro correlation with risk-on/risk-off sentiment

Community dynamics:
- Retail holders: Strong conviction, hodl mentality, social identity
- Traders: Technical analysis, momentum, short-term positioning
- Institutions: Regulatory clarity, custody solutions, ESG concerns
- Developers: Protocol upgrades, ecosystem growth, developer activity

The decentralized nature of crypto communities means social dynamics
play an outsized role compared to traditional markets.
"""
        return FinanceSeed(
            question=question,
            seed_text=f"{crypto_context}\n\nQUESTION: {question}",
        )

    def _default_macro_context(self, event: str) -> str:
        return (
            f"The {event} is a significant economic event that market participants "
            f"are closely monitoring. Current economic conditions show mixed signals "
            f"with inflation data, employment figures, and GDP growth all factoring "
            f"into analyst forecasts. The Federal Reserve's communication strategy "
            f"and forward guidance are key inputs for market pricing."
        )
