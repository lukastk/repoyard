## [0.1.5] - 2025-11-16

### 🚀 Features

- 'get_sync_status' now raises an exception if there is no local sync record, but there is a remote folder. this indicates that the sync was aborted.
- Safer syncing. syncing now creates an intermediate sync record signifying an ongoing sync, and also backups the synced files temporarily.
- Enabled 'soft interruption', intercepting OS signals to delay termination until it is safe to do so.
- Soft interruption will now force interrupt if 3 signals are sent
- Better in-progress output for multi-sync

### ⚙️ Miscellaneous Tasks

- Update CHANGELOG.md
- Update version in pyproject.toml
## [0.1.4] - 2025-11-16

### 🚀 Features

- Supports specifying the creation timestamp
- 'create_user_repo_group_symlinks' now removes empty folders that do not correspond to repo groups in the user repo group folder
- Can now pass paths instead of specifying repo names to certain CLI functions

### 🐛 Bug Fixes

- Creation timestamp specification wasn't working
- Typo in 'new'
- Removed some tests now that bisync is no longer supported
- Repo names were wrongly parsed from paths
- Cmds had changed

### ⚙️ Miscellaneous Tasks

- Update CHANGELOG.md
- Ran nbl prepare with new nblite version
- Update version in pyproject.toml
## [0.1.3] - 2025-11-16

### 🚀 Features

- Implemented new syncing system based on 'rclone sync' rather than 'rclone bisync'
- 'copy_from_path' in 'new_repo'
- RepoMeta.get_user_path
- Fuzzy string matching in repo_name and other modes
- Changed the form of repo ids to a more legible form
- Async support
- 'max_concurrent_rclone_ops' in cli 'sync-meta'
- CLI commands 'list', 'yard-status' and 'multi-sync'
- Enabled support for unique names in repo groups
- Create_user_symlinks
- Changed default
- Cli create-user-symlinks
- 'create_user_repos_symlinks' now removes old symlinks
- User symlink creation does now not delete symlinks that are meant to be there
- CLI commands now creates user symlinks automatically
- Logical expression filtering of groups
- Optimised group filtering

### 🐛 Bug Fixes

- 'new' doesnt reinitialise .git now
- Expanduser issues
- 'get_repo_full_name_from_sub_path' now resolves symlink paths
- Error in checking 'res_dry'
- Removed deprectated 'bisync_helper'
- Properly implemented repo_full_names and storage_locations filter
- Removed dud arguments
- Updated CLIs for the new cmd functions
- 'get_local_sync_record_path' wasn't used in '02_get_repo_sync_status'
- Removed the direction in SyncRecords as it was inconsistent with the approach
- Allow for __init__ in tests/
- Fixed SyncRecord logic
- Typo
- Removed old SyncConfig
- Missing await
- Async_throttler now propagates exceptions
- Create_user_symlinks was async
- Missing import
- Better repo name conflict handling

### 🚜 Refactor

- More sensible default
- Removed dud files
- Fixed import

### 🧪 Testing

- Test.utils
- Finished tests 00 and 01
- Run_cmd
- Test_02_remote
- Fixed test_02_remote

### ⚙️ Miscellaneous Tasks

- Update CHANGELOG.md
- Added module code so that you can install directly from git
- Uv.lock
- Nbl prepare
- Python-dotenv dev-dependency
- Uv.lock
- Update version in pyproject.toml
## [0.1.2] - 2025-11-14

### 🐛 Bug Fixes

- Was config.json instead of config.toml

### ⚙️ Miscellaneous Tasks

- Update CHANGELOG.md
- Update version in pyproject.toml
## [0.1.1] - 2025-11-14

### 🐛 Bug Fixes

- Issues with '~' in paths

### ⚙️ Miscellaneous Tasks

- Git-cliff
- Docs defined in nblite.toml
- Update version in pyproject.toml
## [0.1.0] - 2025-11-13

### ⚙️ Miscellaneous Tasks

- Updated nblite
- Updated nblite
- Publish script
- Update version in pyproject.toml
