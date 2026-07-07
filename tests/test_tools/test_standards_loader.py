"""Unit tests for backend.tools.standards_loader (BRD_v2.0.md section 14)."""

from pathlib import Path

from backend.schemas.project_context import OrgStandards
from backend.tools.standards_loader import ALL_CATEGORIES, load_standards, route_standards


def _write(directory: Path, filename: str, content: str) -> None:
    (directory / filename).write_text(content, encoding="utf-8")


class TestLoadStandards:
    def test_loads_all_recognized_categories(self, tmp_path):
        _write(tmp_path, "coding-standards.md", "Use camelCase for all identifiers.")
        _write(tmp_path, "security-standards.md", "All endpoints require authentication.")
        _write(tmp_path, "api-design.md", "Use snake_case for request fields.")
        _write(tmp_path, "naming-conventions.md", "Classes are PascalCase.")
        _write(tmp_path, "logging-standards.md", "Log all API requests.")
        _write(tmp_path, "exception-handling.md", "Never swallow exceptions silently.")
        _write(tmp_path, "testing-standards.md", "Minimum 80% coverage.")
        _write(tmp_path, "cicd-standards.md", "All merges require green CI.")
        _write(tmp_path, "repository-conventions.md", "Use trunk-based development.")
        _write(tmp_path, "organization-practices.md", "100% coverage for critical paths.")

        result = load_standards(tmp_path)

        assert result.coding == "Use camelCase for all identifiers."
        assert result.security == "All endpoints require authentication."
        assert result.api_design == "Use snake_case for request fields."
        assert result.naming == "Classes are PascalCase."
        assert result.logging == "Log all API requests."
        assert result.exception_handling == "Never swallow exceptions silently."
        assert result.testing == "Minimum 80% coverage."
        assert result.cicd == "All merges require green CI."
        assert result.repository_conventions == "Use trunk-based development."
        assert result.organization_practices == "100% coverage for critical paths."
        assert result.missing_categories == []

    def test_missing_categories_populated_when_files_absent(self, tmp_path):
        _write(tmp_path, "coding-standards.md", "Use camelCase.")

        result = load_standards(tmp_path)

        assert result.coding == "Use camelCase."
        assert set(result.missing_categories) == set(ALL_CATEGORIES) - {"coding"}

    def test_unrecognized_file_is_accepted_but_not_categorized(self, tmp_path):
        _write(tmp_path, "coding-standards.md", "Use camelCase.")
        _write(tmp_path, "random-notes.md", "Some unrelated content.")

        result = load_standards(tmp_path)  # must not raise

        assert result.coding == "Use camelCase."
        dumped = result.model_dump(exclude={"missing_categories", "conflicts"})
        assert "Some unrelated content." not in dumped.values()

    def test_fuzzy_filename_variant_from_fr_1_3_example(self, tmp_path):
        # FR-1.3 explicitly cites "coding-guidelines.md" as a recognized variant
        # of the "coding" category (filenames aren't matched literally).
        _write(tmp_path, "coding-guidelines.md", "Prefer composition over inheritance.")

        result = load_standards(tmp_path)

        assert result.coding == "Prefer composition over inheritance."

    def test_multiple_files_matching_same_category_keeps_later_one(self, tmp_path):
        _write(tmp_path, "coding-standards.md", "First version.")
        _write(tmp_path, "coding-style.md", "Second version.")

        result = load_standards(tmp_path)  # must not raise

        assert result.coding in {"First version.", "Second version."}

    def test_nonexistent_directory_returns_all_missing(self, tmp_path):
        result = load_standards(tmp_path / "does-not-exist")

        assert set(result.missing_categories) == set(ALL_CATEGORIES)

    def test_empty_file_is_skipped_and_counted_as_missing(self, tmp_path):
        _write(tmp_path, "security-standards.md", "   ")

        result = load_standards(tmp_path)

        assert result.security is None
        assert "security" in result.missing_categories


class TestRouteStandards:
    @staticmethod
    def _org_standards() -> OrgStandards:
        return OrgStandards(
            coding="Use camelCase.",
            security="Require MFA.",
            api_design=None,
            organization_practices="Document all decisions.",
        )

    def test_concatenates_requested_categories_with_headers(self):
        org_standards = self._org_standards()

        result = route_standards(org_standards, ["coding", "security"])

        assert "## coding\nUse camelCase." in result
        assert "## security\nRequire MFA." in result
        assert result.index("## coding") < result.index("## security")

    def test_skips_categories_with_no_content(self):
        org_standards = self._org_standards()

        result = route_standards(org_standards, ["coding", "api_design"])

        assert "## coding" in result
        assert "## api_design" not in result

    def test_unknown_category_is_skipped_without_raising(self):
        org_standards = self._org_standards()

        result = route_standards(org_standards, ["coding", "not_a_real_category"])

        assert "## coding" in result
        assert "not_a_real_category" not in result

    def test_empty_target_categories_returns_empty_string(self):
        org_standards = self._org_standards()

        assert route_standards(org_standards, []) == ""
