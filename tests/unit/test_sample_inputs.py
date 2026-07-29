"""Tests for src/agents/main.py SAMPLE_DATA registry and the prior-auth baseline fixture.

What IS guaranteed:
  - SAMPLE_DATA is present in src/agents/main.py and is a non-empty dict (read via ast,
    without importing the module — agent_framework is absent from the dev dependency group).
  - The prior-auth SAMPLE_DATA entry resolves to an existing, parseable JSON file.
    If main.py is updated to point at a different path, this test FAILS — that is intentional.
  - Every SAMPLE_DATA entry whose file already exists on disk is well-formed JSON.
  - The prior-auth fixture carries the fields that prior_auth.py reads at runtime.

What is NOT guaranteed:
  - SAMPLE_DATA entries for workflows whose sample files have not yet been created are
    skipped by the existence guard; only the prior-auth entry is required to be present.

The prior-auth workflow (prior_auth.py) reads these keys from the request:
  member:   name, id, dob, state (falls back to plan when state absent)
  provider: npi, name, specialty
  service:  description, cpt_code/cpt_codes, icd10_codes, place_of_service, type
  diagnosis.icd10_codes — fallback when service.icd10_codes is absent
  clinical_summary — top-level

The sample file must use those exact keys so --demo produces a runnable workflow.
"""

import ast
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_MAIN_PY = REPO_ROOT / "src" / "agents" / "main.py"


def _extract_sample_data() -> dict:
    """Read SAMPLE_DATA from main.py without importing it (agent_framework absent from dev deps)."""
    tree = ast.parse(_MAIN_PY.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "SAMPLE_DATA":
                    return ast.literal_eval(node.value)
    raise AssertionError(f"SAMPLE_DATA constant not found in {_MAIN_PY}")


def _resolve_sample_path(raw: str) -> Path:
    """Mirror load_input()'s resolution order: try path as-is, then relative to REPO_ROOT."""
    candidate = Path(raw)
    if candidate.exists():
        return candidate
    return REPO_ROOT / raw


def _pa_request() -> dict:
    """Load the prior-auth baseline fixture, resolving its path the same way load_input() does."""
    sample_data = _extract_sample_data()
    raw = sample_data["prior-auth"]
    paths = [raw] if isinstance(raw, str) else raw
    for p in paths:
        resolved = _resolve_sample_path(p)
        if resolved.exists():
            return json.loads(resolved.read_text())
    raise FileNotFoundError(f"prior-auth sample file not found; tried: {paths}")


class TestSampleDataRegistry:
    """SAMPLE_DATA in main.py must point at real, parseable files (for entries that exist)."""

    def test_sample_data_extracted(self):
        """SAMPLE_DATA constant must be present and non-empty in src/agents/main.py."""
        data = _extract_sample_data()
        assert isinstance(data, dict) and data, "SAMPLE_DATA must be a non-empty dict"

    def test_prior_auth_entry_resolves(self):
        """The prior-auth SAMPLE_DATA entry must point at an existing, parseable JSON file.

        If main.py is updated to a different path without creating that file, this test fails.
        That is the regression this test exists to catch.
        """
        sample_data = _extract_sample_data()
        assert "prior-auth" in sample_data, "SAMPLE_DATA missing 'prior-auth' key"
        raw = sample_data["prior-auth"]
        paths = [raw] if isinstance(raw, str) else raw
        for p in paths:
            resolved = _resolve_sample_path(p)
            assert resolved.exists(), (
                f"SAMPLE_DATA['prior-auth'] → '{p}' does not exist at {resolved}.\n"
                f"  --demo will fail loudly; restore the file or update SAMPLE_DATA."
            )
            try:
                json.loads(resolved.read_text())
            except json.JSONDecodeError as exc:
                raise AssertionError(f"SAMPLE_DATA['prior-auth'] path '{p}' is not valid JSON: {exc}") from exc

    def test_all_existing_entries_are_parseable(self):
        """Every SAMPLE_DATA entry whose file already exists must be well-formed JSON."""
        sample_data = _extract_sample_data()
        for workflow, raw in sample_data.items():
            paths = [raw] if isinstance(raw, str) else raw
            for p in paths:
                resolved = _resolve_sample_path(p)
                if not resolved.exists():
                    continue  # not yet created — prior-auth is separately required above
                try:
                    json.loads(resolved.read_text())
                except json.JSONDecodeError as exc:
                    raise AssertionError(
                        f"SAMPLE_DATA['{workflow}'] path '{p}' is not valid JSON: {exc}"
                    ) from exc


class TestPriorAuthSampleShape:
    """Verify the top-level sections that prior_auth.py reads."""

    def test_has_required_top_level_keys(self):
        data = _pa_request()
        for key in ("request_id", "member", "provider", "service"):
            assert key in data, f"sample request missing top-level key '{key}'"

    def test_member_uses_workflow_keys(self):
        """prior_auth.py reads member.name, member.id, member.dob."""
        member = _pa_request()["member"]
        for key in ("name", "id", "dob"):
            assert key in member, (
                f"member block missing '{key}' — prior_auth.py will silently default to empty string"
            )

    def test_provider_uses_workflow_keys(self):
        """prior_auth.py reads provider.npi, provider.name, provider.specialty."""
        provider = _pa_request()["provider"]
        for key in ("npi", "name", "specialty"):
            assert key in provider, (
                f"provider block missing '{key}' — prior_auth.py will silently default to empty string"
            )

    def test_service_uses_workflow_keys(self):
        """prior_auth.py reads service.description and cpt_code or cpt_codes."""
        service = _pa_request()["service"]
        assert "description" in service, "service block missing 'description'"
        has_cpt = "cpt_code" in service or "cpt_codes" in service
        assert has_cpt, "service block missing both 'cpt_code' and 'cpt_codes'"

    def test_icd10_codes_reachable(self):
        """prior_auth.py reads service.icd10_codes; falls back to diagnosis.icd10_codes."""
        data = _pa_request()
        has_icd = data["service"].get("icd10_codes") or data.get("diagnosis", {}).get("icd10_codes")
        assert has_icd, "ICD-10 codes not found in service or diagnosis"


class TestPriorAuthSampleSentinel:
    def test_uses_demo_npi_sentinel(self):
        """NPI 1234567890 is the demo sentinel; prior_auth.py skips live NPI lookup for it."""
        data = _pa_request()
        assert data["provider"]["npi"] == "1234567890", (
            f"expected demo-sentinel NPI 1234567890, got {data['provider']['npi']!r}"
        )


class TestPriorAuthSampleSafety:
    def test_labelled_synthetic(self):
        """data_classification field must declare no real identifiers (checked on structured field)."""
        data = _pa_request()
        assert "SYNTHETIC" in data["data_classification"].upper(), (
            "sample data must contain 'SYNTHETIC' in data_classification to signal no real PHI"
        )
