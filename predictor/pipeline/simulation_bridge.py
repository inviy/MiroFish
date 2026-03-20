"""
MiroFish Simulation Bridge
MiroFish 시뮬레이션 결과 → Polymarket 확률로 변환하는 핵심 파이프라인.

흐름:
  1. 도메인별 시드 데이터 수집 (뉴스, 통계, 여론)
  2. MiroFish 온톨로지 생성 & 그래프 빌드
  3. 에이전트 시뮬레이션 실행
  4. 결과 집계 → 확률 산출
  5. Polymarket 마켓 가격과 비교 → 엣지 탐색
"""

import json
import requests
from typing import Optional
from dataclasses import dataclass, field

BACKEND_URL = "http://localhost:5001"


@dataclass
class PredictionResult:
    question:     str
    domain:       str                     # sports / elections / finance / ...
    yes_prob:     float                   # 0~1
    confidence:   float                   # 0~1 (시뮬레이션 consensus 강도)
    reasoning:    str
    sim_id:       Optional[str] = None
    condition_id: Optional[str] = None   # Polymarket 마켓 ID (매핑 후)
    metadata:     dict = field(default_factory=dict)


class SimulationBridge:
    """MiroFish 백엔드 API를 호출해 예측 결과를 가져오는 브릿지."""

    def __init__(self, backend_url: str = BACKEND_URL):
        self.backend = backend_url
        self.session = requests.Session()

    # ── Step 1: 프로젝트 생성 & 파일 업로드 ───────────────────────────────────

    def create_project_from_text(self, text: str, name: str) -> str:
        """텍스트를 MiroFish 프로젝트에 업로드하고 project_id 반환."""
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt",
                                        delete=False, encoding="utf-8") as f:
            f.write(text)
            tmp_path = f.name
        try:
            with open(tmp_path, "rb") as fh:
                resp = self.session.post(
                    f"{self.backend}/api/graph/generate-ontology",
                    files={"files": (f"{name}.txt", fh, "text/plain")},
                    data={"project_name": name},
                    timeout=120,
                )
            resp.raise_for_status()
            data = resp.json()
            return data["project_id"]
        finally:
            os.unlink(tmp_path)

    # ── Step 2: 그래프 빌드 ──────────────────────────────────────────────────

    def build_graph(self, project_id: str) -> str:
        """그래프 빌드 태스크를 시작하고 task_id 반환."""
        resp = self.session.post(
            f"{self.backend}/api/graph/build",
            json={"project_id": project_id},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["task_id"]

    def wait_for_task(self, task_id: str, timeout_sec: int = 300) -> dict:
        """태스크 완료까지 폴링."""
        import time
        start = time.time()
        while time.time() - start < timeout_sec:
            resp = self.session.get(f"{self.backend}/api/task/{task_id}", timeout=10)
            data = resp.json()
            if data.get("status") in ("completed", "failed"):
                return data
            time.sleep(5)
        raise TimeoutError(f"Task {task_id} timed out after {timeout_sec}s")

    # ── Step 3: 시뮬레이션 실행 ──────────────────────────────────────────────

    def create_and_prepare_simulation(
        self, project_id: str, platform: str = "reddit", num_agents: int = 50
    ) -> str:
        """시뮬레이션 생성 & 준비 후 simulation_id 반환."""
        # 생성
        resp = self.session.post(
            f"{self.backend}/api/simulation/create",
            json={"project_id": project_id, "platform": platform,
                  "num_agents": num_agents},
            timeout=30,
        )
        resp.raise_for_status()
        sim_id = resp.json()["simulation_id"]

        # 준비
        resp = self.session.post(
            f"{self.backend}/api/simulation/prepare",
            json={"simulation_id": sim_id},
            timeout=300,
        )
        resp.raise_for_status()
        return sim_id

    # ── Step 4: 리포트 생성 & 확률 추출 ──────────────────────────────────────

    def generate_prediction_report(
        self, sim_id: str, question: str, domain: str
    ) -> PredictionResult:
        """
        시뮬레이션 완료 후 ReportAgent로 예측 확률 추출.
        프롬프트를 구조화해서 YES/NO 확률을 JSON으로 받음.
        """
        prompt = f"""
You are a prediction analyst. Based on the simulation results, answer:

QUESTION: {question}

Respond ONLY in this JSON format:
{{
  "yes_probability": <0.0 to 1.0>,
  "confidence": <0.0 to 1.0>,
  "reasoning": "<2-3 sentence explanation>",
  "key_factors": ["factor1", "factor2"]
}}
"""
        resp = self.session.post(
            f"{self.backend}/api/report/chat",
            json={"simulation_id": sim_id, "message": prompt},
            timeout=120,
        )
        resp.raise_for_status()
        raw = resp.json().get("response", "{}")

        # JSON 파싱 (LLM 응답에서 추출)
        try:
            start = raw.find("{")
            end   = raw.rfind("}") + 1
            parsed = json.loads(raw[start:end])
        except (json.JSONDecodeError, ValueError):
            parsed = {"yes_probability": 0.5, "confidence": 0.0,
                      "reasoning": raw, "key_factors": []}

        return PredictionResult(
            question   = question,
            domain     = domain,
            yes_prob   = float(parsed.get("yes_probability", 0.5)),
            confidence = float(parsed.get("confidence", 0.0)),
            reasoning  = parsed.get("reasoning", ""),
            sim_id     = sim_id,
            metadata   = {"key_factors": parsed.get("key_factors", [])},
        )

    # ── Full Pipeline ─────────────────────────────────────────────────────────

    def run_full_pipeline(
        self,
        seed_text: str,
        question: str,
        domain: str,
        project_name: str,
        platform: str = "reddit",
        num_agents: int = 50,
    ) -> PredictionResult:
        """
        시드 텍스트 → 예측 결과까지 전체 파이프라인 실행.

        Args:
            seed_text:    뉴스/보고서/통계 등 시드 문서 텍스트
            question:     예측 질문 (Polymarket 마켓 질문과 일치)
            domain:       sports / elections / finance / entertainment / ...
            project_name: 프로젝트 이름
            platform:     reddit (기본) / twitter
            num_agents:   에이전트 수 (많을수록 정확, 느림)
        """
        print(f"[Pipeline] Starting: {question}")

        print("[Pipeline] 1/4 Building graph...")
        project_id = self.create_project_from_text(seed_text, project_name)
        task_id    = self.build_graph(project_id)
        self.wait_for_task(task_id)

        print("[Pipeline] 2/4 Preparing simulation...")
        sim_id = self.create_and_prepare_simulation(project_id, platform, num_agents)

        print("[Pipeline] 3/4 Generating report & extracting prediction...")
        result = self.generate_prediction_report(sim_id, question, domain)

        print(f"[Pipeline] Done. YES={result.yes_prob:.2%}, Confidence={result.confidence:.2%}")
        return result
