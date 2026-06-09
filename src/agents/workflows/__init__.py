"""
Healthcare Agent Workflow modules.

Each module implements a specific orchestration pattern:
- prior_auth: Sequential → Concurrent → Synthesis (hybrid)
- clinical_trials: Sequential (research → draft)
- patient_data: Single agent
- literature_search: Concurrent (PubMed + Trials)
"""
