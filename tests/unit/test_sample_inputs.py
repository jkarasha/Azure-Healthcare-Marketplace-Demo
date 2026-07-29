"""Every path in main.SAMPLE_DATA must resolve to a real, well-formed file.

The prior-auth workflow (prior_auth.py) reads these keys from the request:
  member:   name, id, dob, plan/state
  provider: npi, name, specialty
  service:  description, cpt_code/cpt_codes, icd10_codes, place_of_service, type
  diagnosis.icd10_codes — fallback when service.icd10_codes is absent
  clinical_summary — top-level

The sample file must use those exact keys so --demo produces a runnable workflow.
"""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PRIOR_AUTH_SAMPLE = REPO_ROOT / "data" / "sample_cases" / "prior_auth_baseline" / "pa_request.json"


def _load() -> dict:
    return json.loads(PRIOR_AUTH_SAMPLE.read_text())


class TestPriorAuthSampleExists:
    def test_file_is_present(self):
        assert PRIOR_AUTH_SAMPLE.exists(), (
            f"src/agents/main.py references "
            f"{PRIOR_AUTH_SAMPLE.relative_to(REPO_ROOT)} but it is missing"
        )

    def test_file_is_valid_json(self):
        _load()


class TestPriorAuthSampleShape:
    """Verify the top-level sections that prior_auth.py reads."""

    def test_has_required_top_level_keys(self):
        data = _load()
        for key in ("request_id", "member", "provider", "service"):
            assert key in data, f"sample request missing top-level key '{key}'"

    def test_member_uses_workflow_keys(self):
        """prior_auth.py reads member.name, member.id, member.dob."""
        member = _load()["member"]
        for key in ("name", "id", "dob"):
            assert key in member, (
                f"member block missing '{key}' — prior_auth.py will silently default to empty string"
            )

    def test_provider_uses_workflow_keys(self):
        """prior_auth.py reads provider.npi, provider.name, provider.specialty."""
        provider = _load()["provider"]
        for key in ("npi", "name", "specialty"):
            assert key in provider, (
                f"provider block missing '{key}' — prior_auth.py will silently default to empty string"
            )

    def test_service_uses_workflow_keys(self):
        """prior_auth.py reads service.description and cpt_code or cpt_codes."""
        service = _load()["service"]
        assert "description" in service, "service block missing 'description'"
        has_cpt = "cpt_code" in service or "cpt_codes" in service
        assert has_cpt, "service block missing both 'cpt_code' and 'cpt_codes'"

    def test_icd10_codes_reachable(self):
        """prior_auth.py reads service.icd10_codes; falls back to diagnosis.icd10_codes."""
        data = _load()
        has_icd = data["service"].get("icd10_codes") or data.get("diagnosis", {}).get("icd10_codes")
        assert has_icd, "ICD-10 codes not found in service or diagnosis"


class TestPriorAuthSampleSentinel:
    def test_uses_demo_npi_sentinel(self):
        """NPI 1234567890 is the demo sentinel (prior_auth.py line ~566 marks it verified)."""
        data = _load()
        assert data["provider"]["npi"] == "1234567890", (
            f"expected demo-sentinel NPI 1234567890, got {data['provider']['npi']!r}"
        )


class TestPriorAuthSampleSafety:
    def test_labelled_synthetic(self):
        """File must declare it contains no real identifiers."""
        raw = PRIOR_AUTH_SAMPLE.read_text()
        assert "SYNTHETIC" in raw or "synthetic" in raw, (
            "sample data must contain the word 'SYNTHETIC' or 'synthetic' to signal no real PHI"
        )
