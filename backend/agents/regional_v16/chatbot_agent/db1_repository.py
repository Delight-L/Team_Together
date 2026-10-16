"""DB1 근거 저장소의 계약. 챗봇 로직(query_service·consumption_trends·orchestrator)은 이 계약만 압니다.

구현
- pg_repository.PostgresDb1Repository : PostgreSQL에 게시된 활성 run을 읽기 전용으로 조회 (유일한 구현)
  (조회 로직은 repository.SqlDb1Repository가 공통으로 가짐)

계약을 지키면 챗봇 로직은 저장소가 바뀌어도 바뀌지 않습니다. SQL은 구현 안에만 둡니다.
탐지·근거 조회는 pandas DataFrame, 소비·배경 조회는 dict 목록을 돌려줍니다(기존 동작 유지).
"""
from __future__ import annotations

from typing import Any, Protocol

import pandas as pd


class Db1Repository(Protocol):
    # ── 상태 ────────────────────────────────────────────────────
    def has_data(self) -> bool:
        """근거 자료가 이 서버에 있는지. 없으면 지역 분석 에이전트가 동·그룹 분석으로 대신 답합니다."""

    def pipeline_status(self) -> dict:
        """처리 상태: history_end, history_rows, detection_rows, age_detection_rows, waiting_for …"""

    # ── 범위 ────────────────────────────────────────────────────
    def districts(self) -> set[str]:
        """조회 가능한 행정동 이름(별칭 정규화 후)."""

    def available_period(self) -> tuple[str, str]:
        """탐지 결과가 있는 (시작월, 끝월) 'YYYY-MM'."""

    def consumption_period(self) -> tuple[str, str]:
        """소비 자료가 다루는 (시작월, 끝월) 'YYYY-MM'."""

    def district_codes(self) -> dict[str, str]:
        """행정동 이름(별칭 정규화) → 행정동 코드."""

    def cluster_types(self) -> list[str]:
        """지역 배경에 저장된 클러스터(지역 유형) 이름."""

    def cluster_districts(self, cluster: str) -> list[str]:
        """그 클러스터에 속한 행정동 이름(가나다순)."""

    # ── 탐지·근거 (DataFrame) ───────────────────────────────────
    def activity(self, dong: str | None, start: str | None = None, end: str | None = None,
                 age_band: str | None = None) -> pd.DataFrame:
        """동(없으면 전체)·기간·연령대의 월별 탐지 결과."""

    def signals(self, start: str | None = None, end: str | None = None, dong: str | None = None,
                signal: str = 'any', age_band: str | None = None) -> pd.DataFrame:
        """신호가 잡힌 행. signal: any | communication | mobility | combined."""

    def anomalies(self, start: str | None = None, end: str | None = None, metric: str | None = None,
                  age_band: str | None = None, dongs: tuple = ()) -> tuple[pd.DataFrame, str]:
        """지표 Robust Z가 낮은 순 상위 10행과 사용한 컬럼 이름."""

    def evidence(self, dong: str, start: str | None = None, end: str | None = None,
                 age_band: str | None = None) -> pd.DataFrame:
        """신호 근거 카드."""

    def context(self, dong: str, as_of: str | None = None) -> pd.DataFrame:
        """as_of 시점에 유효한 지역 유형·구조 지표(0행 또는 1행)."""

    # ── 보조 맥락 (dict) ────────────────────────────────────────
    def supplements(self, names: list, dates: list, age_band: str | None = None) -> dict[str, Any]:
        """관측기간에 맞춘 상권·날씨·지역 배경·서베이 보조 자료."""

    def consumption_evidence(self, names: tuple, start: str, end: str, age: str | None) -> tuple[list, dict]:
        """요청한 달력 기간의 (동 상권 자료 행 목록, 강남구 공통 소비 자료 dict)."""

    def consumption_payloads(self, table: str, *, periods: list | None = None, adm_cds: list | None = None,
                             ages: list | None = None, districts: list | None = None) -> list[dict]:
        """소비 증감 계산용 원자료. table: a3a_feature | a3a_comparison | a3b_feature.

        목록 조건은 해당 값의 행만 읽도록 저장소에 내려 보냅니다(None=조건 없음, 빈 목록=해당 행 없음).
        조건에 맞는 행이 결과에 그대로 들어가야 하므로, 구현은 조건을 파이썬 쪽에서 다시 걸 필요가 없게 해야 합니다."""
