"""
Elections Domain - Seed Data Builder
선거 예측용 시드 데이터 생성.
MiroFish의 사회 시뮬레이션이 가장 강력하게 작동하는 도메인.
유권자 행동, 여론 형성, 미디어 영향력 모델링.
"""

import requests
from dataclasses import dataclass
from typing import Optional


@dataclass
class ElectionSeed:
    question: str
    seed_text: str
    domain: str = "elections"


class ElectionSeedBuilder:
    """
    선거 도메인 시드 빌더.
    여론조사 데이터, 인구통계, 미디어 프레이밍, 이슈 살리언스를
    MiroFish 에이전트 시뮬레이션용 텍스트로 합성.
    """

    def __init__(self):
        self.session = requests.Session()

    def build_seed(
        self,
        candidate_a: str,
        candidate_b: str,
        election_name: str,
        region: str = "USA",
        question: str = "",
        polling_data: Optional[dict] = None,
    ) -> ElectionSeed:
        """
        선거 시드 문서 생성.

        Args:
            polling_data: {"candidate_a": 48.2, "candidate_b": 44.1, "undecided": 7.7}
        """
        if not question:
            question = f"Will {candidate_a} win the {election_name}?"

        if polling_data is None:
            polling_data = {
                "candidate_a": 48.0,
                "candidate_b": 44.0,
                "undecided": 8.0,
            }

        seed = f"""
=== ELECTION PREDICTION ANALYSIS ===

ELECTION: {election_name}
REGION: {region}
CANDIDATES: {candidate_a} vs {candidate_b}
QUESTION: {question}

=== CURRENT POLLING DATA ===

Latest aggregate polling averages:
- {candidate_a}: {polling_data['candidate_a']:.1f}%
- {candidate_b}: {polling_data['candidate_b']:.1f}%
- Undecided: {polling_data.get('undecided', 8.0):.1f}%

Polling margin: {candidate_a} leads by {polling_data['candidate_a'] - polling_data['candidate_b']:.1f} points
Margin of error: ±3.0% (typical for national polls)

=== DEMOGRAPHIC BREAKDOWN ===

Voter coalition analysis shows distinct patterns:
- Urban voters tend to favor progressive candidates
- Rural and suburban districts show varying preferences
- Youth voters (18-29) are mobilizing around economic issues
- Senior voters prioritize healthcare and social security
- Independent voters remain the critical swing demographic

=== KEY CAMPAIGN ISSUES ===

Economy & Jobs: Top concern for 38% of voters
Healthcare: Critical for 24% of voters
Immigration: Mobilizing force for 18% of voters
Climate & Energy: Priority for 12% of voters
Other issues: 8% of voters

=== MEDIA COVERAGE ANALYSIS ===

Media framing is shaping voter perceptions:
- Mainstream outlets emphasizing polling momentum
- Social media driving alternative narratives and fact-checking
- Debate performance creating short-term opinion shifts
- Endorsements from influential figures influencing undecided voters

=== HISTORICAL CONTEXT ===

Historical election data for {region}:
- Incumbency advantage/disadvantage in current political climate
- Economic indicators correlation with election outcomes
- Voter turnout projections by demographics
- Early voting and mail-in ballot patterns

=== SOCIAL DYNAMICS & VOTER MOBILIZATION ===

Community organizing and grassroots mobilization:
- Volunteer networks and door-to-door canvassing
- Social media echo chambers reinforcing existing preferences
- Youth voter registration drives
- Minority community engagement strategies

The simulation should model how these social dynamics and information flows
evolve over time, particularly among undecided voters and low-propensity voters.
Key simulation parameters: media influence, peer effects, issue salience shifts.
"""
        return ElectionSeed(question=question, seed_text=seed)

    def build_from_wikipedia(self, election_url: str, question: str) -> ElectionSeed:
        """Wikipedia에서 선거 정보 크롤링해 시드 생성 (영어 위키 기준)."""
        try:
            # Wikipedia API로 텍스트 추출
            title = election_url.split("/wiki/")[-1]
            resp = self.session.get(
                "https://en.wikipedia.org/api/rest_v1/page/summary/" + title,
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                extract = data.get("extract", "")
                seed_text = f"""
=== ELECTION BACKGROUND (from Wikipedia) ===

{extract}

=== PREDICTION QUESTION ===
{question}

Based on the above background, analyze the social dynamics, voter behavior,
and likely outcome of this election event.
"""
                return ElectionSeed(question=question, seed_text=seed_text)
        except Exception:
            pass

        return ElectionSeed(
            question=question,
            seed_text=f"Election analysis for: {question}\n\nURL: {election_url}",
        )
