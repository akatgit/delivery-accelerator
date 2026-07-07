"""Unit tests for backend.skills.extraction.detect_standard_conflicts."""

import pytest

from backend.schemas.project_context import OrgStandards
from backend.skills.extraction.detect_standard_conflicts import DetectStandardConflictsSkill


class _FakeResponse:
    def __init__(self, content: str):
        self.content = content


class _FakeLLM:
    def __init__(self, responses):
        self._responses = list(responses)
        self.prompts: list[str] = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return _FakeResponse(self._responses.pop(0))


@pytest.fixture
def org_standards() -> OrgStandards:
    return OrgStandards(
        coding="Use camelCase for all identifiers.",
        api_design="Use snake_case for request/response fields.",
    )


class TestBuildInputs:
    def test_includes_all_provided_categories_with_headers(self, org_standards):
        inputs = DetectStandardConflictsSkill.build_inputs(org_standards)

        content = inputs["org_standards_content"]
        assert "## coding\nUse camelCase for all identifiers." in content
        assert "## api_design\nUse snake_case for request/response fields." in content

    def test_omits_categories_with_no_content(self, org_standards):
        inputs = DetectStandardConflictsSkill.build_inputs(org_standards)

        assert "## security" not in inputs["org_standards_content"]


class TestInvoke:
    def test_reports_conflict_between_contradictory_standards(self, org_standards):
        conflict_json = (
            '[{"category_a": "coding", '
            '"statement_a": "Use camelCase for all identifiers.", '
            '"category_b": "api_design", '
            '"statement_b": "Use snake_case for request/response fields.", '
            '"description": "camelCase and snake_case cannot both be followed for the same identifiers.", '
            '"resolution": null}]'
        )
        llm = _FakeLLM([conflict_json])
        skill = DetectStandardConflictsSkill(llm=llm)

        result = skill.invoke(DetectStandardConflictsSkill.build_inputs(org_standards))

        assert len(result) == 1
        conflict = result[0]
        assert conflict["category_a"] == "coding"
        assert conflict["category_b"] == "api_design"
        assert conflict["resolution"] is None
        # the rendered prompt actually carries the standards content to the LLM
        assert "Use camelCase for all identifiers." in llm.prompts[0]
        assert "Use snake_case for request/response fields." in llm.prompts[0]

    def test_returns_empty_list_when_no_conflicts_found(self, org_standards):
        llm = _FakeLLM(["[]"])
        skill = DetectStandardConflictsSkill(llm=llm)

        result = skill.invoke(DetectStandardConflictsSkill.build_inputs(org_standards))

        assert result == []

    def test_prompt_version_loaded_from_template_header(self, org_standards):
        llm = _FakeLLM(["[]"])
        skill = DetectStandardConflictsSkill(llm=llm)

        assert skill.prompt_version == "1.0.0"

    def test_invalid_output_retries_with_correction_prompt(self, org_standards):
        llm = _FakeLLM(["not valid json", "[]"])
        skill = DetectStandardConflictsSkill(llm=llm)

        result = skill.invoke(DetectStandardConflictsSkill.build_inputs(org_standards))

        assert result == []
        assert len(llm.prompts) == 2
        assert "invalid" in llm.prompts[1].lower()

    def test_decision_log_records_skill_and_prompt_version(self, org_standards):
        llm = _FakeLLM(["[]"])
        skill = DetectStandardConflictsSkill(llm=llm)
        decision_log = []

        skill.invoke(
            DetectStandardConflictsSkill.build_inputs(org_standards),
            agent_name="document-parser",
            decision_log=decision_log,
        )

        assert len(decision_log) == 1
        assert decision_log[0].skill == "detect-standard-conflicts"
        assert decision_log[0].agent == "document-parser"
        assert decision_log[0].prompt_version == "1.0.0"
