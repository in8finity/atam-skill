"""ATAM domain models — dataclasses used by selection.py and controller.py.

These are runtime-only types, NOT hashharness records. The controller
reconstructs them from records via `controller.state()`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Canonical quality attributes (must match QualityAttribute records' title)
QA_NAMES = (
    "performance",
    "availability",
    "security",
    "modifiability",
    "usability",
    "testability",
    "deployability",
    "scalability",
    "interoperability",
    "observability",
    "cost",
)

PRIORITY_TIERS = ("critical", "discriminator", "standard", "exploratory")

RISK_LEVELS = ("benign", "sensitive", "high-stakes")


def risk_level_le(a: str, b: str) -> bool:
    return RISK_LEVELS.index(a) <= RISK_LEVELS.index(b)


# --------------------------------------------------------------------------- #
# Bank-side
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class BankProbe:
    record_sha256: str
    probe_id: str
    target_qa: str
    text: str
    intent: str
    priority_tier: str
    estimated_time_minutes: float
    expected_saturation_gain: float
    expected_findings: float
    risk_level: str
    discriminates_hypotheses: tuple[str, ...] = ()
    applies_when: tuple[dict, ...] = ()
    prerequisites: tuple[str, ...] = ()
    targets_components: tuple[str, ...] = ()
    finding_types_targeted: tuple[str, ...] = ()  # R | NR | SP | TP
    scope: str = "subsystem"  # "subsystem" | "endpoint" | "module"

    def expected_score_per_minute(self) -> float:
        if self.estimated_time_minutes <= 0:
            return 0.0
        return self.expected_saturation_gain / self.estimated_time_minutes


# --------------------------------------------------------------------------- #
# Case-side state
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ScenarioRef:
    record_sha256: str
    scenario_id: str  # text field
    title: str
    qa: str
    importance: str  # H/M/L
    difficulty: str  # H/M/L
    selected_for_analysis: bool
    category: str = "anticipated"  # anticipated | use | growth | exploratory


@dataclass(frozen=True)
class Coverage:
    scenario_id: str
    status: str  # untouched | in-progress | sufficient | saturated
    saturation: float
    gaps: tuple[str, ...] = ()
    findings_count: int = 0
    questions_asked: int = 0


@dataclass(frozen=True)
class Hypothesis:
    id: str  # = text field of the AtamHypothesis
    claim_text: str
    status: str  # open | confirmed | refuted | dropped
    discriminating_question: str | None = None
    discriminates_probe_ids: tuple[str, ...] = ()
    relevant_qas: tuple[str, ...] = ()
    scenario_id: str | None = None


# --------------------------------------------------------------------------- #
# Selection result
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ProbeRef:
    probe_id: str
    text_snapshot: str
    target_qa: str = ""
    intent: str = ""
    scenario_id: str | None = None


@dataclass(frozen=True)
class ProbeDecision:
    chosen_probe: ProbeRef | None
    source: str  # bank | generated | fallback-bank | closure
    reason: str
    alternatives: tuple[ProbeRef, ...] = ()
    bank_probe_sha: str | None = None  # only when source=bank|fallback-bank
    discriminates_hypothesis_id: str | None = None

    @classmethod
    def closure(cls) -> "ProbeDecision":
        return cls(
            chosen_probe=None,
            source="closure",
            reason="No uncovered scenarios and no open hypotheses.",
        )


@dataclass(frozen=True)
class ProbeCandidate:
    text: str
    intent: str
    target_qa: str
    scenario_id: str
    proposed_priority_tier: str = "standard"
    proposed_risk_level: str = "benign"
    estimated_time_minutes: float = 5.0
    expected_saturation_gain: float = 0.3
    generation_prompt_hash: str = ""


@dataclass(frozen=True)
class CritiqueBreakdown:
    info_value: float
    cost_eff: float
    specificity: float
    safety: float
    novelty: float
    qa_alignment: float


@dataclass(frozen=True)
class ProbeCritique:
    candidate: ProbeCandidate
    score: float
    breakdown: CritiqueBreakdown
    verdict: str  # select | revise | reject
    rationale_text: str


# --------------------------------------------------------------------------- #
# Top-level evaluation state
# --------------------------------------------------------------------------- #


@dataclass
class EvaluationGoal:
    primary: str = "find-tradeoffs-and-risks"
    secondary: tuple[str, ...] = ()
    scope_minutes: int = 240
    depth: str = "screening"  # screening | comprehensive
    target_qas: tuple[str, ...] = ()
    evaluation_scope: str = "subsystem"  # "subsystem" | "endpoint" | "module"


@dataclass
class EvaluationState:
    evaluation_workpackage: str
    evaluation_sha: str
    instrument_version_id: str
    goal: EvaluationGoal
    scenarios: dict[str, ScenarioRef]  # scenario_id -> ScenarioRef
    coverage: dict[str, Coverage]  # scenario_id -> latest Coverage
    hypotheses: list[Hypothesis]
    deployed_probe_ids: set[str] = field(default_factory=set)
    allowed_risk_level: str = "sensitive"
    current_phase: int = 6  # 6 or 8

    def uncovered_scenarios(self) -> list[ScenarioRef]:
        """Scenarios selected_for_analysis whose coverage is below sufficient."""
        out: list[ScenarioRef] = []
        for sid, s in self.scenarios.items():
            if not s.selected_for_analysis:
                continue
            cov = self.coverage.get(sid)
            if cov is None or cov.status in ("untouched", "in-progress"):
                out.append(s)
        return out

    def open_hypotheses(self) -> list[Hypothesis]:
        return [h for h in self.hypotheses if h.status == "open"]


@dataclass(frozen=True)
class QuestionSummary:
    """Lightweight view of a recently-deployed ProbingQuestion."""

    question_index: int
    probe_id: str
    text: str
    target_qa: str
    scenario_id: str | None
