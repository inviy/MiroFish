"""
Sports Domain - Seed Data Builder
스포츠 경기 예측을 위한 시드 텍스트 자동 생성.
무료 API: ESPN unofficial, The-Odds-API, SportsReference 등 활용.
"""

import json
import requests
from dataclasses import dataclass
from typing import Optional


@dataclass
class SportsSeed:
    question: str        # Polymarket 질문과 일치
    seed_text: str       # MiroFish에 입력할 문서
    domain: str = "sports"


class SportsSeedBuilder:
    """
    스포츠 시드 데이터 빌더.
    팀 통계, 최근 경기 결과, 부상 리포트, 여론/팬 반응을 합성해
    MiroFish 시뮬레이션용 시드 문서 생성.
    """

    def __init__(self, odds_api_key: Optional[str] = None):
        self.odds_api_key = odds_api_key
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "MiroFish/1.0"})

    def build_seed(
        self,
        team_a: str,
        team_b: str,
        event: str,
        sport: str = "basketball",
        question: str = "",
    ) -> SportsSeed:
        """
        두 팀 간의 시드 텍스트 생성.
        실제 데이터 API가 없을 경우 템플릿 기반 생성.
        """
        if not question:
            question = f"Will {team_a} beat {team_b} in {event}?"

        sections = []

        # 1. 이벤트 개요
        sections.append(f"""
=== SPORTS PREDICTION ANALYSIS: {event} ===

EVENT: {team_a} vs {team_b}
SPORT: {sport}
QUESTION: {question}
""")

        # 2. 최근 성적 (The Odds API에서 가져오거나 플레이스홀더)
        recent = self._fetch_recent_results(team_a, team_b, sport)
        sections.append(f"""
=== RECENT PERFORMANCE ===
{recent}
""")

        # 3. 팬 여론 & 베팅 라인
        odds = self._fetch_odds(team_a, team_b, sport)
        sections.append(f"""
=== BETTING ODDS & PUBLIC SENTIMENT ===
{odds}
""")

        # 4. 소셜 미디어 분위기 (MiroFish가 시뮬레이션할 핵심)
        sections.append(f"""
=== SOCIAL MEDIA & FAN DYNAMICS ===

Social media platforms like Reddit (r/{sport}) and Twitter/X are buzzing with
predictions for the {event} matchup between {team_a} and {team_b}.

Fan communities are analyzing:
- Historical head-to-head records
- Home/away performance differential
- Key player matchups and injury reports
- Coaching strategies and tactical adjustments

Public betting sentiment is split, with sharp money and casual bettors
often taking opposing positions, creating market inefficiencies.
""")

        seed_text = "\n".join(sections)
        return SportsSeed(question=question, seed_text=seed_text)

    def _fetch_recent_results(self, team_a: str, team_b: str, sport: str) -> str:
        """최근 경기 결과 - The Odds API 또는 ESPN 비공식 API 활용."""
        # ESPN 비공식 엔드포인트 시도
        sport_map = {
            "basketball": "nba",
            "football": "nfl",
            "soccer": "soccer",
            "baseball": "mlb",
        }
        espn_sport = sport_map.get(sport, "nba")
        try:
            url = f"https://site.api.espn.com/apis/site/v2/sports/{espn_sport}/scoreboard"
            resp = self.session.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                events = data.get("events", [])[:5]
                lines = []
                for ev in events:
                    name = ev.get("name", "")
                    status = ev.get("status", {}).get("type", {}).get("description", "")
                    lines.append(f"- {name}: {status}")
                if lines:
                    return f"Recent {espn_sport.upper()} games:\n" + "\n".join(lines)
        except Exception:
            pass

        return (
            f"{team_a}: Recent form shows consistent performance with strong defensive metrics.\n"
            f"{team_b}: Momentum building with key offensive weapons healthy and active.\n"
            f"Head-to-head: Historical matchups suggest competitive parity between both teams."
        )

    def _fetch_odds(self, team_a: str, team_b: str, sport: str) -> str:
        """배당률 데이터 - The Odds API 활용."""
        if not self.odds_api_key:
            return (
                f"Market odds are currently favoring {team_a} slightly, "
                f"reflecting public perception and recent performance trends. "
                f"Professional handicappers are divided, suggesting genuine uncertainty "
                f"in the outcome. Public money is flowing toward the favorite."
            )

        sport_key_map = {
            "basketball": "basketball_nba",
            "football":   "americanfootball_nfl",
            "soccer":     "soccer_usa_mls",
            "baseball":   "baseball_mlb",
        }
        sport_key = sport_key_map.get(sport, "basketball_nba")
        try:
            resp = self.session.get(
                "https://api.the-odds-api.com/v4/sports/{}/odds/".format(sport_key),
                params={"apiKey": self.odds_api_key, "regions": "us", "markets": "h2h"},
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json()
                for game in data:
                    teams = [t["name"] for t in game.get("bookmakers", [{}])[0]
                             .get("markets", [{}])[0].get("outcomes", [])]
                    if team_a in teams or team_b in teams:
                        outcomes = (game.get("bookmakers", [{}])[0]
                                    .get("markets", [{}])[0].get("outcomes", []))
                        lines = [f"{o['name']}: {o['price']}" for o in outcomes]
                        return "Betting odds:\n" + "\n".join(lines)
        except Exception:
            pass

        return f"Odds data unavailable. Market appears competitive for {team_a} vs {team_b}."
