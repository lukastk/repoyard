# Integration Test Isolation Plan

## Problem Statement

Integration tests currently create temporary configs via `create_repoyards()` in `/tmp/`, but there are issues:

1. **Lock directory leakage**: The lock paths may still reference the user's actual `~/.repoyard/locks/` directory, causing stale lock issues during test runs
2. **No persistent test configs**: Test configurations are recreated from scratch each time, making it harder to debug or have reproducible test environments
3. **Remote sync tests**: Tests that need actual remote storage (S3, SFTP, etc.) have no standardized way to access credentials - they either skip or fail

## Proposed Solution

### 1. Dedicated Test Config Directory Structure

Create a new directory structure in the repo:

```
tests/
  fixtures/
    configs/
      default/                          # Default test config (shared by most tests)
        config.toml                     # Test configuration
        repoyard_rclone.conf           # Local-only rclone config (committed)
        repoyard_rclone_remote.conf    # Real remote config (gitignored)
        repoyard_rclone_remote.conf.template  # Template for remote config
        default.rclone_exclude          # Default exclude patterns

      # Future: additional configs for specific test scenarios
      # multi_storage/
      # custom_groups/
```

### 2. Config File Details

#### `config.toml` (committed)
```toml
# Test configuration - uses paths relative to test temp directory
# These paths are overwritten at runtime by test fixtures

default_storage_location = "local_test"
repoyard_data_path = "/tmp/repoyard_test_data"  # Overwritten at runtime

[storage_locations.local_test]
storage_type = "local"
store_path = "/tmp/repoyard_test_store"  # Overwritten at runtime

[storage_locations.remote_test]
storage_type = "rclone"
store_path = "repoyard_test"
```

#### `repoyard_rclone.conf` (committed)
```ini
# Local-only rclone config for tests that don't need real remotes
# Uses alias type pointing to local directories

[local_test]
type = alias
remote = /tmp/repoyard_local_test
```

#### `repoyard_rclone_remote.conf.template` (committed)
```ini
# Template for remote rclone config
# Copy to repoyard_rclone_remote.conf and fill in your credentials
#
# This file is gitignored - do not commit actual credentials!

[test_remote]
type = s3
provider = AWS
# env_auth = true  # Or use explicit credentials below
# access_key_id = YOUR_ACCESS_KEY
# secret_access_key = YOUR_SECRET_KEY
# region = us-east-1
# endpoint = https://your-endpoint.com
```

#### `repoyard_rclone_remote.conf` (gitignored)
- Real credentials for remote sync tests
- Created by developers who want to run remote tests
- Tests skip gracefully if this file doesn't exist

### 3. Updated `.gitignore`

Add to `.gitignore`:
```
# Test remote credentials (contains secrets)
tests/fixtures/configs/*/repoyard_rclone_remote.conf
```

### 4. Test Fixture Changes

#### New `conftest.py` fixture approach:

```python
import pytest
from pathlib import Path
import shutil
import tempfile
import toml

# Path to fixture configs in the repo
FIXTURE_CONFIGS_PATH = Path(__file__).parent.parent / "fixtures" / "configs"

@pytest.fixture
def test_repoyard(tmp_path):
    """
    Create an isolated test repoyard environment.

    Uses config templates from tests/fixtures/configs/default/
    but creates all data in tmp_path for isolation.
    """
    config_name = "default"
    fixture_config_dir = FIXTURE_CONFIGS_PATH / config_name

    # Create test directory structure
    test_config_dir = tmp_path / ".config" / "repoyard"
    test_data_dir = tmp_path / ".repoyard"
    test_local_store = tmp_path / "local_store"
    test_user_repos = tmp_path / "repos"
    test_user_groups = tmp_path / "repo-groups"

    test_config_dir.mkdir(parents=True)
    test_data_dir.mkdir(parents=True)
    test_local_store.mkdir(parents=True)
    test_user_repos.mkdir(parents=True)
    test_user_groups.mkdir(parents=True)

    # Copy and customize config.toml
    config_path = test_config_dir / "config.toml"
    config_data = toml.load(fixture_config_dir / "config.toml")

    # Override paths to use temp directory
    config_data["repoyard_data_path"] = str(test_data_dir)
    config_data["user_repos_path"] = str(test_user_repos)
    config_data["user_repo_groups_path"] = str(test_user_groups)

    # Update storage location paths
    for sl_name, sl_config in config_data.get("storage_locations", {}).items():
        if sl_config.get("storage_type") == "local":
            sl_config["store_path"] = str(test_local_store / sl_name)

    with open(config_path, "w") as f:
        toml.dump(config_data, f)

    # Copy rclone config (local-only version)
    rclone_config_path = test_config_dir / "repoyard_rclone.conf"
    shutil.copy(fixture_config_dir / "repoyard_rclone.conf", rclone_config_path)

    # Update rclone config paths to use temp directory
    rclone_content = rclone_config_path.read_text()
    rclone_content = rclone_content.replace(
        "/tmp/repoyard_local_test",
        str(test_local_store / "rclone_alias")
    )
    rclone_config_path.write_text(rclone_content)

    # Copy exclude file
    shutil.copy(
        fixture_config_dir / "default.rclone_exclude",
        test_config_dir / "default.rclone_exclude"
    )

    # Initialize repoyard data structures
    from repoyard.config import get_config
    config = get_config(config_path)

    # Create necessary directories
    (test_data_dir / "local_store").mkdir(exist_ok=True)
    (test_data_dir / "sync_records").mkdir(exist_ok=True)
    (test_data_dir / "locks").mkdir(exist_ok=True)

    return {
        "config": config,
        "config_path": config_path,
        "data_path": test_data_dir,
        "local_store": test_local_store,
        "user_repos": test_user_repos,
        "user_groups": test_user_groups,
    }


@pytest.fixture
def test_repoyard_with_remote(test_repoyard):
    """
    Like test_repoyard but with real remote credentials if available.

    Skips the test if repoyard_rclone_remote.conf doesn't exist.
    """
    fixture_config_dir = FIXTURE_CONFIGS_PATH / "default"
    remote_rclone_path = fixture_config_dir / "repoyard_rclone_remote.conf"

    if not remote_rclone_path.exists():
        pytest.skip(
            "Remote rclone config not found. "
            "Copy repoyard_rclone_remote.conf.template to repoyard_rclone_remote.conf "
            "and add your credentials to run remote sync tests."
        )

    # Append remote config to the test rclone config
    config_dir = test_repoyard["config_path"].parent
    rclone_config_path = config_dir / "repoyard_rclone.conf"

    remote_content = remote_rclone_path.read_text()
    current_content = rclone_config_path.read_text()
    rclone_config_path.write_text(current_content + "\n" + remote_content)

    # Reload config
    from repoyard.config import get_config
    test_repoyard["config"] = get_config(test_repoyard["config_path"])
    test_repoyard["has_remote"] = True

    return test_repoyard
```

### 5. Test Migration Strategy

#### Phase 1: Create fixture directory structure
- Create `tests/fixtures/configs/default/` directory
- Add config.toml, rclone configs, and template
- Update .gitignore

#### Phase 2: Update conftest.py
- Add new `test_repoyard` and `test_repoyard_with_remote` fixtures
- Keep `create_repoyards()` for backward compatibility initially

#### Phase 3: Migrate existing tests
- Update integration tests to use new fixtures
- Mark remote-dependent tests with `@pytest.mark.remote`
- Ensure all tests use explicit `config_path` from fixture

#### Phase 4: Cleanup
- Remove legacy `create_repoyards()` function once all tests migrated
- Remove `.env` test variables that pointed to user config

### 6. Test Markers

Add pytest markers in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = [
    "integration: marks tests as integration tests",
    "remote: marks tests that require remote storage credentials",
]
```

Usage:
```python
@pytest.mark.integration
@pytest.mark.remote
def test_sync_to_s3(test_repoyard_with_remote):
    """This test requires real S3 credentials."""
    ...
```

Run options:
```bash
# Run all tests except remote
pytest -m "not remote"

# Run only integration tests with remote
pytest -m "integration and remote"
```

### 7. Key Benefits

1. **Complete isolation**: Each test gets its own temp directory with all paths (including locks) fully contained
2. **Reproducible configs**: Base configs are committed and versioned
3. **Secure credentials**: Remote credentials are gitignored with clear template
4. **Graceful degradation**: Tests skip cleanly when remote config is unavailable
5. **Easy debugging**: Can inspect fixture configs to understand test setup
6. **Extensible**: Easy to add new config variations for specific test scenarios

### 8. Files to Create/Modify

| File | Action |
|------|--------|
| `tests/fixtures/configs/default/config.toml` | Create |
| `tests/fixtures/configs/default/repoyard_rclone.conf` | Create |
| `tests/fixtures/configs/default/repoyard_rclone_remote.conf.template` | Create |
| `tests/fixtures/configs/default/default.rclone_exclude` | Create |
| `.gitignore` | Modify (add remote conf pattern) |
| `pyproject.toml` | Modify (add markers) |
| `tests/conftest.py` or `pts/tests/conftest.pct.py` | Modify (add fixtures) |
| `pts/tests/integration/conftest.pct.py` | Modify (update fixtures) |
| Integration test files | Modify (use new fixtures) |

### 9. Implementation Order

1. Create directory structure and fixture config files
2. Update .gitignore
3. Add pytest markers to pyproject.toml
4. Implement new fixtures in conftest
5. Update one integration test as proof of concept
6. Migrate remaining integration tests
7. Remove legacy `create_repoyards()` and `.env` references
