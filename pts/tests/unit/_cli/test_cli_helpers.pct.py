# ---
# jupyter:
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Unit Tests for CLI Helper Functions
#
# Tests for CLI utility functions like subsequence matching, name matching modes,
# and repo filtering.

# %%
#|default_exp unit._cli.test_cli_helpers

# %%
#|export
import pytest
from unittest.mock import MagicMock
from repoyard._cli.main import _is_subsequence_match, NameMatchMode, _get_filtered_repo_metas


# ============================================================================
# Tests for _is_subsequence_match
# ============================================================================

# %%
#|export
class TestIsSubsequenceMatch:
    """Tests for the _is_subsequence_match helper function."""

    def test_exact_match(self):
        """Exact string matches."""
        assert _is_subsequence_match("hello", "hello") == True

    def test_subsequence_at_start(self):
        """Subsequence at the start of the string."""
        assert _is_subsequence_match("hel", "hello") == True

    def test_subsequence_at_end(self):
        """Subsequence at the end of the string."""
        assert _is_subsequence_match("llo", "hello") == True

    def test_subsequence_scattered(self):
        """Subsequence with characters scattered throughout."""
        assert _is_subsequence_match("hlo", "hello") == True

    def test_subsequence_with_gaps(self):
        """Subsequence with larger gaps between characters."""
        assert _is_subsequence_match("ad", "abcd") == True

    def test_lukas_in_lukastk(self):
        """Real example: lukas in lukastk."""
        assert _is_subsequence_match("lukas", "lukastk") == True

    def test_lukas_in_sentence(self):
        """Subsequence found in a longer sentence."""
        assert _is_subsequence_match("lukas", "I am lukastk") == True

    def test_non_subsequence(self):
        """Characters not in correct order fail."""
        assert _is_subsequence_match("acbd", "abcd") == False

    def test_term_longer_than_name(self):
        """Term longer than name fails."""
        assert _is_subsequence_match("hello world", "hello") == False

    def test_empty_term(self):
        """Empty term matches any string."""
        assert _is_subsequence_match("", "anything") == True

    def test_empty_name(self):
        """Non-empty term doesn't match empty name."""
        assert _is_subsequence_match("a", "") == False

    def test_both_empty(self):
        """Empty term matches empty name."""
        assert _is_subsequence_match("", "") == True

    def test_single_char_match(self):
        """Single character match."""
        assert _is_subsequence_match("a", "abc") == True

    def test_single_char_no_match(self):
        """Single character no match."""
        assert _is_subsequence_match("z", "abc") == False

    def test_repeated_chars_in_term(self):
        """Repeated characters in term."""
        assert _is_subsequence_match("aa", "abab") == True
        assert _is_subsequence_match("aaa", "abab") == False

    def test_case_sensitive(self):
        """Match is case sensitive."""
        assert _is_subsequence_match("ABC", "abc") == False
        assert _is_subsequence_match("abc", "ABC") == False
        assert _is_subsequence_match("ABC", "ABC") == True

    def test_special_characters(self):
        """Special characters are matched literally."""
        assert _is_subsequence_match("a-b", "a-b-c") == True
        assert _is_subsequence_match("a_b", "a_b_c") == True

    def test_numbers(self):
        """Numbers are matched correctly."""
        assert _is_subsequence_match("123", "a1b2c3") == True
        assert _is_subsequence_match("321", "a1b2c3") == False

    def test_unicode_characters(self):
        """Unicode characters are handled."""
        assert _is_subsequence_match("日本", "日本語") == True
        assert _is_subsequence_match("こに", "こんにちは") == True


# ============================================================================
# Tests for NameMatchMode enum
# ============================================================================

# %%
#|export
class TestNameMatchMode:
    """Tests for the NameMatchMode enum."""

    def test_exact_value(self):
        """EXACT has correct value."""
        assert NameMatchMode.EXACT.value == "exact"

    def test_contains_value(self):
        """CONTAINS has correct value."""
        assert NameMatchMode.CONTAINS.value == "contains"

    def test_subsequence_value(self):
        """SUBSEQUENCE has correct value."""
        assert NameMatchMode.SUBSEQUENCE.value == "subsequence"

    def test_mode_count(self):
        """There are exactly 3 name match modes."""
        assert len(NameMatchMode) == 3

    def test_modes_from_string(self):
        """Modes can be created from string values."""
        assert NameMatchMode("exact") == NameMatchMode.EXACT
        assert NameMatchMode("contains") == NameMatchMode.CONTAINS
        assert NameMatchMode("subsequence") == NameMatchMode.SUBSEQUENCE

    def test_invalid_mode_raises(self):
        """Invalid mode string raises ValueError."""
        with pytest.raises(ValueError):
            NameMatchMode("invalid")


# ============================================================================
# Tests for _get_filtered_repo_metas
# ============================================================================

# %%
#|export
def _create_mock_repo_meta(name: str, groups: list[str]) -> MagicMock:
    """Create a mock RepoMeta with name and groups."""
    mock = MagicMock()
    mock.name = name
    mock.groups = groups
    return mock


# %%
#|export
class TestGetFilteredRepoMetas:
    """Tests for the _get_filtered_repo_metas function."""

    def test_no_filters_returns_all(self):
        """With no filters, all repos are returned."""
        repos = [
            _create_mock_repo_meta("repo1", ["backend"]),
            _create_mock_repo_meta("repo2", ["frontend"]),
            _create_mock_repo_meta("repo3", ["backend", "api"]),
        ]

        result = _get_filtered_repo_metas(repos, None, None, None)
        assert len(result) == 3

    def test_include_single_group(self):
        """Include filter with single group."""
        repos = [
            _create_mock_repo_meta("repo1", ["backend"]),
            _create_mock_repo_meta("repo2", ["frontend"]),
            _create_mock_repo_meta("repo3", ["backend", "api"]),
        ]

        result = _get_filtered_repo_metas(repos, ["backend"], None, None)
        assert len(result) == 2
        assert all("backend" in r.groups for r in result)

    def test_include_multiple_groups(self):
        """Include filter with multiple groups (OR logic)."""
        repos = [
            _create_mock_repo_meta("repo1", ["backend"]),
            _create_mock_repo_meta("repo2", ["frontend"]),
            _create_mock_repo_meta("repo3", ["api"]),
            _create_mock_repo_meta("repo4", ["other"]),
        ]

        result = _get_filtered_repo_metas(repos, ["backend", "frontend"], None, None)
        assert len(result) == 2

    def test_exclude_single_group(self):
        """Exclude filter with single group."""
        repos = [
            _create_mock_repo_meta("repo1", ["backend"]),
            _create_mock_repo_meta("repo2", ["frontend"]),
            _create_mock_repo_meta("repo3", ["backend", "deprecated"]),
        ]

        result = _get_filtered_repo_metas(repos, None, ["deprecated"], None)
        assert len(result) == 2
        assert all("deprecated" not in r.groups for r in result)

    def test_exclude_multiple_groups(self):
        """Exclude filter with multiple groups."""
        repos = [
            _create_mock_repo_meta("repo1", ["backend"]),
            _create_mock_repo_meta("repo2", ["frontend", "deprecated"]),
            _create_mock_repo_meta("repo3", ["api", "legacy"]),
            _create_mock_repo_meta("repo4", ["other"]),
        ]

        result = _get_filtered_repo_metas(repos, None, ["deprecated", "legacy"], None)
        assert len(result) == 2

    def test_include_and_exclude_combined(self):
        """Include and exclude filters work together."""
        repos = [
            _create_mock_repo_meta("repo1", ["backend"]),
            _create_mock_repo_meta("repo2", ["backend", "deprecated"]),
            _create_mock_repo_meta("repo3", ["frontend"]),
        ]

        result = _get_filtered_repo_metas(repos, ["backend"], ["deprecated"], None)
        assert len(result) == 1
        assert result[0].name == "repo1"

    def test_group_filter_simple(self):
        """Group filter with simple expression."""
        repos = [
            _create_mock_repo_meta("repo1", ["backend"]),
            _create_mock_repo_meta("repo2", ["frontend"]),
            _create_mock_repo_meta("repo3", ["backend", "api"]),
        ]

        result = _get_filtered_repo_metas(repos, None, None, "backend")
        assert len(result) == 2
        assert all("backend" in r.groups for r in result)

    def test_group_filter_and_expression(self):
        """Group filter with AND expression."""
        repos = [
            _create_mock_repo_meta("repo1", ["backend"]),
            _create_mock_repo_meta("repo2", ["backend", "api"]),
            _create_mock_repo_meta("repo3", ["frontend", "api"]),
        ]

        result = _get_filtered_repo_metas(repos, None, None, "backend AND api")
        assert len(result) == 1
        assert result[0].name == "repo2"

    def test_group_filter_or_expression(self):
        """Group filter with OR expression."""
        repos = [
            _create_mock_repo_meta("repo1", ["backend"]),
            _create_mock_repo_meta("repo2", ["frontend"]),
            _create_mock_repo_meta("repo3", ["other"]),
        ]

        result = _get_filtered_repo_metas(repos, None, None, "backend OR frontend")
        assert len(result) == 2

    def test_group_filter_not_expression(self):
        """Group filter with NOT expression."""
        repos = [
            _create_mock_repo_meta("repo1", ["backend"]),
            _create_mock_repo_meta("repo2", ["backend", "deprecated"]),
            _create_mock_repo_meta("repo3", ["frontend"]),
        ]

        result = _get_filtered_repo_metas(repos, None, None, "backend AND NOT deprecated")
        assert len(result) == 1
        assert result[0].name == "repo1"

    def test_group_filter_complex_expression(self):
        """Group filter with complex expression."""
        repos = [
            _create_mock_repo_meta("repo1", ["backend", "prod"]),
            _create_mock_repo_meta("repo2", ["backend", "staging"]),
            _create_mock_repo_meta("repo3", ["frontend", "prod"]),
            _create_mock_repo_meta("repo4", ["backend", "prod", "deprecated"]),
        ]

        result = _get_filtered_repo_metas(
            repos, None, None, "(backend OR frontend) AND prod AND NOT deprecated"
        )
        assert len(result) == 2
        names = [r.name for r in result]
        assert "repo1" in names
        assert "repo3" in names

    def test_all_filters_combined(self):
        """Include, exclude, and group filter all together."""
        repos = [
            _create_mock_repo_meta("repo1", ["backend", "api"]),
            _create_mock_repo_meta("repo2", ["backend", "api", "deprecated"]),
            _create_mock_repo_meta("repo3", ["frontend", "api"]),
            _create_mock_repo_meta("repo4", ["other"]),
        ]

        # Include api, exclude deprecated, then filter for backend
        result = _get_filtered_repo_metas(repos, ["api"], ["deprecated"], "backend")
        assert len(result) == 1
        assert result[0].name == "repo1"

    def test_empty_repo_list(self):
        """Empty repo list returns empty result."""
        result = _get_filtered_repo_metas([], ["backend"], None, None)
        assert len(result) == 0

    def test_no_matches_returns_empty(self):
        """No matching repos returns empty list."""
        repos = [
            _create_mock_repo_meta("repo1", ["frontend"]),
            _create_mock_repo_meta("repo2", ["other"]),
        ]

        result = _get_filtered_repo_metas(repos, ["backend"], None, None)
        assert len(result) == 0

    def test_repo_with_no_groups(self):
        """Repo with no groups is handled correctly."""
        repos = [
            _create_mock_repo_meta("repo1", []),
            _create_mock_repo_meta("repo2", ["backend"]),
        ]

        # Include filter excludes repo with no groups
        result = _get_filtered_repo_metas(repos, ["backend"], None, None)
        assert len(result) == 1

        # Exclude filter keeps repo with no groups
        result = _get_filtered_repo_metas(repos, None, ["backend"], None)
        assert len(result) == 1
        assert result[0].name == "repo1"

    def test_group_filter_with_empty_groups(self):
        """Group filter handles repos with empty groups."""
        repos = [
            _create_mock_repo_meta("repo1", []),
            _create_mock_repo_meta("repo2", ["backend"]),
        ]

        result = _get_filtered_repo_metas(repos, None, None, "NOT backend")
        assert len(result) == 1
        assert result[0].name == "repo1"


# ============================================================================
# Tests for timestamp parsing (from cli_new)
# ============================================================================

# %%
#|export
from datetime import datetime
from repoyard import const


class TestTimestampParsing:
    """Tests for timestamp parsing in CLI commands."""

    def test_full_timestamp_format(self):
        """Full timestamp format YYYYMMDD_HHMMSS is parsed correctly."""
        timestamp_str = "20251116_105532"
        result = datetime.strptime(timestamp_str, const.REPO_TIMESTAMP_FORMAT)
        assert result.year == 2025
        assert result.month == 11
        assert result.day == 16
        assert result.hour == 10
        assert result.minute == 55
        assert result.second == 32

    def test_date_only_format(self):
        """Date-only format YYYYMMDD is parsed correctly."""
        timestamp_str = "20251116"
        result = datetime.strptime(timestamp_str, const.REPO_TIMESTAMP_FORMAT_DATE_ONLY)
        assert result.year == 2025
        assert result.month == 11
        assert result.day == 16
        assert result.hour == 0
        assert result.minute == 0
        assert result.second == 0

    def test_invalid_timestamp_raises(self):
        """Invalid timestamp format raises ValueError."""
        with pytest.raises(ValueError):
            datetime.strptime("2025-11-16", const.REPO_TIMESTAMP_FORMAT)

    def test_invalid_date_only_raises(self):
        """Invalid date-only format raises ValueError."""
        with pytest.raises(ValueError):
            datetime.strptime("2025-11-16", const.REPO_TIMESTAMP_FORMAT_DATE_ONLY)

    def test_partial_timestamp_raises(self):
        """Partial timestamp raises ValueError."""
        with pytest.raises(ValueError):
            datetime.strptime("20251116_10", const.REPO_TIMESTAMP_FORMAT)


# ============================================================================
# Tests for repo path inference helper
# ============================================================================

# %%
#|export
from unittest.mock import patch


class TestRepoPathInference:
    """Tests for get_repo_index_name_from_sub_path function.

    Uses real temp directories since the function calls Path.resolve().
    """

    def test_path_within_repo_data(self, tmp_path):
        """Path within repo data directory returns index name."""
        from repoyard._utils import get_repo_index_name_from_sub_path

        # Create real directory structure
        repos_path = tmp_path / "repos"
        repo_dir = repos_path / "20251116_123456_abc12__myrepo" / "subdir"
        repo_dir.mkdir(parents=True)

        mock_config = MagicMock()
        mock_config.user_repos_path = repos_path

        result = get_repo_index_name_from_sub_path(mock_config, repo_dir)
        assert result == "20251116_123456_abc12__myrepo"

    def test_path_at_repo_root(self, tmp_path):
        """Path at repo root returns index name."""
        from repoyard._utils import get_repo_index_name_from_sub_path

        repos_path = tmp_path / "repos"
        repo_dir = repos_path / "20251116_123456_abc12__myrepo"
        repo_dir.mkdir(parents=True)

        mock_config = MagicMock()
        mock_config.user_repos_path = repos_path

        result = get_repo_index_name_from_sub_path(mock_config, repo_dir)
        assert result == "20251116_123456_abc12__myrepo"

    def test_path_outside_repos(self, tmp_path):
        """Path outside repos directory returns None."""
        from repoyard._utils import get_repo_index_name_from_sub_path

        repos_path = tmp_path / "repos"
        repos_path.mkdir(parents=True)
        other_dir = tmp_path / "other" / "directory"
        other_dir.mkdir(parents=True)

        mock_config = MagicMock()
        mock_config.user_repos_path = repos_path

        result = get_repo_index_name_from_sub_path(mock_config, other_dir)
        assert result is None

    def test_path_at_repos_root(self, tmp_path):
        """Path at repos root (not inside a repo) returns None."""
        from repoyard._utils import get_repo_index_name_from_sub_path

        repos_path = tmp_path / "repos"
        repos_path.mkdir(parents=True)

        mock_config = MagicMock()
        mock_config.user_repos_path = repos_path

        result = get_repo_index_name_from_sub_path(mock_config, repos_path)
        assert result is None

    def test_deeply_nested_path(self, tmp_path):
        """Deeply nested path still returns correct index name."""
        from repoyard._utils import get_repo_index_name_from_sub_path

        repos_path = tmp_path / "repos"
        deep_dir = repos_path / "20251116_123456_abc12__myrepo" / "a" / "b" / "c" / "d" / "e"
        deep_dir.mkdir(parents=True)

        mock_config = MagicMock()
        mock_config.user_repos_path = repos_path

        result = get_repo_index_name_from_sub_path(mock_config, deep_dir)
        assert result == "20251116_123456_abc12__myrepo"
