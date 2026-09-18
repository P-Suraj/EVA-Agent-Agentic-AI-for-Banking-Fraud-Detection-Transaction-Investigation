"""
Dataset Adapter Interface and Concrete Adapters.

Transforms external or synthetic dataset representations into the canonical
EvaluationCase schema. Adapters are strictly deterministic, with zero LLM inference.
"""

from abc import ABC, abstractmethod
import json
from pathlib import Path
from typing import Any

from banking_eval.schema import CaseCategory, EvaluationCase, PolicyOutcome, RiskOutcome


class DatasetAdapter(ABC):
    """Abstract base class for dataset adapters."""

    @abstractmethod
    def adapt_record(self, raw_record: dict[str, Any]) -> EvaluationCase:
        """Convert a single raw dataset record into a canonical EvaluationCase."""
        pass

    def adapt(self, raw_data: list[dict[str, Any]]) -> list[EvaluationCase]:
        """Convert a collection of raw dataset records into canonical EvaluationCases."""
        return [self.adapt_record(record) for record in raw_data]

    def load_and_adapt(self, file_path: str | Path) -> list[EvaluationCase]:
        """Load JSON data from disk and adapt it into canonical EvaluationCases."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Dataset file not found: {path}")

        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise ValueError(f"Expected a JSON list of records in {path}, got {type(data).__name__}")

        return self.adapt(data)


class SyntheticBankingIntentAdapter(DatasetAdapter):
    """
    Concrete adapter for the synthetic banking intent test dataset.

    Performs:
    - field mapping ('id' -> 'test_id', 'text' -> 'input', 'intent' -> 'expected_intent')
    - label normalization (lowercased, stripped)
    - text input trimming
    - deterministic mapping of simulated policy/risk outcomes
    - leaves missing fields explicitly as None (does not invent ground truth)
    """

    def adapt_record(self, raw_record: dict[str, Any]) -> EvaluationCase:
        if not isinstance(raw_record, dict):
            raise ValueError(f"Raw record must be a dict, got {type(raw_record).__name__}")

        # Required fields in source format
        test_id = raw_record.get("id") or raw_record.get("test_id")
        if not test_id or not isinstance(test_id, str):
            raise ValueError(f"Record missing required string 'id' or 'test_id': {raw_record}")

        raw_text = raw_record.get("text") or raw_record.get("input")
        if not raw_text or not isinstance(raw_text, str):
            raise ValueError(f"Record '{test_id}' missing required string 'text' or 'input'")

        cleaned_input = raw_text.strip()

        # Category mapping
        raw_category = raw_record.get("category")
        category = CaseCategory(raw_category) if raw_category else CaseCategory.INTENT

        # Expected intent normalization
        raw_intent = raw_record.get("intent") or raw_record.get("expected_intent")
        expected_intent = raw_intent.strip().lower() if isinstance(raw_intent, str) else None

        # Optional policy outcome
        raw_policy = raw_record.get("expected_policy_outcome")
        expected_policy_outcome = PolicyOutcome(raw_policy) if raw_policy else None

        # Optional risk outcome
        raw_risk = raw_record.get("expected_risk_outcome")
        expected_risk_outcome = RiskOutcome(raw_risk) if raw_risk else None

        # Optional safety-critical flag
        is_safety_critical = bool(raw_record.get("is_safety_critical", False))

        # Optional context
        context = raw_record.get("context")
        if context is not None and not isinstance(context, dict):
            raise ValueError(f"Context in record '{test_id}' must be a dictionary or None")

        # Construct canonical case (unprovided fields remain None)
        return EvaluationCase(
            test_id=test_id,
            category=category,
            input=cleaned_input,
            context=context,
            expected_intent=expected_intent,
            expected_action=raw_record.get("expected_action"),
            expected_parameters=raw_record.get("expected_parameters"),
            expected_policy_outcome=expected_policy_outcome,
            expected_risk_outcome=expected_risk_outcome,
            expected_tool=raw_record.get("expected_tool"),
            expected_approval=raw_record.get("expected_approval"),
            is_safety_critical=is_safety_critical,
        )
