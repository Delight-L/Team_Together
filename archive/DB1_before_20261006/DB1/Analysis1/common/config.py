from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Analysis1Config:
    """Approved Analysis 1 methodology. Change deliberately, not autonomously."""

    # 실제 입력 데이터의 행정동 식별자
    area_key: str = "adm_cd"
    area_name: str = "dong_name"

    expected_areas: int = 22
    random_state: int = 42

    # K-Means
    final_k: int = 3
    k_candidates: tuple[int, ...] = (2, 3, 4, 5, 6)

    # Perturbation stability
    perturbation_noise: tuple[float, ...] = (0.05, 0.10, 0.20)
    perturbation_repeats: int = 250
    ari_threshold: float = 0.80

    # 실제 입력 컬럼 → Analysis1 내부 표준 Feature
    input_feature_map: dict[str, str] = field(
        default_factory=lambda: {
            "flow_per_point": "activity_intensity",
        }
    )

    # 승인된 4개 Domain / 13 Features
    domains: dict[str, tuple[str, ...]] = field(
        default_factory=lambda: {
            "activity": (
                "activity_intensity",
            ),
            "life_activity": (
                "active_pop_pc1",
                "active_pop_pc2",
                "time_structure_pc1",
                "time_structure_pc2",
                "weekend_weekday_index",
            ),
            "population_household": (
                "resident_age_pc1",
                "resident_age_pc2",
                "foreigner_ratio",
                "household_structure_pc1",
                "household_structure_pc2",
            ),
            "structural_welfare": (
                "disability_ratio",
                "livelihood_recipient_ratio",
            ),
        }
    )

    output_dir: Path = Path("data/results/analysis1")


CONFIG = Analysis1Config()