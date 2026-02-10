# Bug Fix Plan

This document details the plan to fix each identified bug in the repoyard codebase.

---

## Critical Bugs

### 1. Infinite Recursion in `by_storage_location` Property

**File:** `pts/mod/_models.pct.py:228-238`

**Problem:** The property calls itself in the dict comprehension, causing infinite recursion.

**Current code:**
```python
@property
def by_storage_location(self) -> dict[str, dict[str, RepoMeta]]:
    if not hasattr(self, '__by_storage_location'):
        self.__by_storage_location = {
            sl_name: {
                repo_meta.index_name: repo_meta
                for repo_meta in self.repo_metas
                if repo_meta.storage_location == sl_name
            }
            for sl_name in self.by_storage_location  # BUG: infinite recursion
        }
    return self.__by_storage_location
```

**Fix:** Extract unique storage location names from `self.repo_metas` instead of calling `self.by_storage_location`.

```python
@property
def by_storage_location(self) -> dict[str, dict[str, RepoMeta]]:
    if not hasattr(self, '__by_storage_location'):
        storage_location_names = set(rm.storage_location for rm in self.repo_metas)
        self.__by_storage_location = {
            sl_name: {
                repo_meta.index_name: repo_meta
                for repo_meta in self.repo_metas
                if repo_meta.storage_location == sl_name
            }
            for sl_name in storage_location_names
        }
    return self.__by_storage_location
```

---

### 2. Wrong Return Type Annotation in `RepoMeta.load()`

**File:** `pts/mod/_models.pct.py:151`

**Problem:** Return type is `-> None` but the function returns a `RepoMeta` instance.

**Current code:**
```python
@classmethod
def load(cls, config: repoyard.config.Config, storage_location_name: str, repo_index_name: str) -> None:
```

**Fix:** Change return type annotation to `-> 'RepoMeta'`.

```python
@classmethod
def load(cls, config: repoyard.config.Config, storage_location_name: str, repo_index_name: str) -> 'RepoMeta':
```

---

### 3. Uninitialized Variable `local_path_is_empty`

**File:** `pts/mod/_models.pct.py:501-502, 550`

**Problem:** `local_path_is_empty` is only set inside a conditional block but used unconditionally later.

**Current code:**
```python
if local_path_is_dir and local_path_exists:
    local_path_is_empty = len(list(local_path.iterdir())) == 0
# ... later:
if (not local_path_is_dir) or (local_path_is_dir and not local_path_is_empty):
```

**Fix:** Initialize `local_path_is_empty` to a default value before the conditional, or restructure the logic.

```python
local_path_is_empty = True  # Default: treat as empty if doesn't exist or isn't a dir
if local_path_is_dir and local_path_exists:
    local_path_is_empty = len(list(local_path.iterdir())) == 0
```

---

### 4. Using `raise` on `typer.echo()` Return Value

**File:** `pts/mod/_cli/main.pct.py:482`

**Problem:** `typer.echo()` returns `None`, so `raise typer.echo(...)` raises `TypeError`.

**Current code:**
```python
if group_name not in repo_meta.groups:
    raise typer.echo(f"Repository `{repo_index_name}` not in group `{group_name}`.")
```

**Fix:** Separate the echo and raise statements.

```python
if group_name not in repo_meta.groups:
    typer.echo(f"Repository `{repo_index_name}` not in group `{group_name}`.")
    raise typer.Exit(code=1)
```

---

### 5. Wrong Object Method Call in `path` Command

**File:** `pts/mod/_cli/main.pct.py:995`

**Problem:** Calling `config.get_local_path(config)` but `Config` has no such method. Should be on `repo_meta`.

**Current code:**
```python
elif path_option == 'root':
    typer.echo(config.get_local_path(config).as_posix())
```

**Fix:** Call the method on `repo_meta` instead of `config`.

```python
elif path_option == 'root':
    typer.echo(repo_meta.get_local_path(config).as_posix())
```

---

### 6. Missing Return in `refresh_repoyard_meta()`

**File:** `pts/mod/_models.pct.py:277-281`

**Problem:** Function declares return type `-> RepoyardMeta` but doesn't return anything.

**Current code:**
```python
def refresh_repoyard_meta(
    config: repoyard.config.Config,
) -> RepoyardMeta:
    repoyard_meta = create_repoyard_meta(config)
    config.repoyard_meta_path.write_text(repoyard_meta.model_dump_json())
```

**Fix:** Add return statement.

```python
def refresh_repoyard_meta(
    config: repoyard.config.Config,
) -> RepoyardMeta:
    repoyard_meta = create_repoyard_meta(config)
    config.repoyard_meta_path.write_text(repoyard_meta.model_dump_json())
    return repoyard_meta
```

---

### 7. Wrong Variable in Group Filter Logic

**File:** `pts/mod/cmds/05_modify_repometa.pct.py:115`

**Problem:** Checking if group is in `modified_repo_meta.groups` instead of each `rm.groups`.

**Current code:**
```python
repo_metas_in_group = [rm for rm in _repo_metas if g in modified_repo_meta.groups]
```

**Fix:** Check each repo meta's groups.

```python
repo_metas_in_group = [rm for rm in _repo_metas if g in rm.groups]
```

---

### 8. Symlink Comparison Bug

**File:** `pts/mod/_models.pct.py:357-358`

**Problem:** Comparing `Path` objects against a list of tuples `(dest_path, symlink_path)`.

**Current code:**
```python
for path in config.user_repo_groups_path.glob('**/*'):
    if path in _symlinks: continue
    if path.is_symlink():
        path.unlink()
```

**Fix:** Extract symlink paths and compare against those.

```python
_symlink_paths = {symlink_path for _, symlink_path in _symlinks}
for path in config.user_repo_groups_path.glob('**/*'):
    if path in _symlink_paths: continue
    if path.is_symlink():
        path.unlink()
```

Note: `_symlink_paths` is already defined later at line 363, so we can either move that definition up or inline the set comprehension.

---

## Medium Priority Issues

### 9. Typo in Error Message

**File:** `pts/mod/_cli/main.pct.py:903`

**Current code:**
```python
typer.echo("Must provied repo full namae.")
```

**Fix:**
```python
typer.echo("Must provide repo full name.")
```

---

### 10. Trailing Backslash with No Continuation

**File:** `pts/mod/_cli/main.pct.py:911`

**Current code:**
```python
group_configs, virtual_repo_group_configs = get_repo_group_configs(config, [repo_meta])\
```

**Fix:** Remove the trailing backslash.

```python
group_configs, virtual_repo_group_configs = get_repo_group_configs(config, [repo_meta])
```

---

### 11. Type Annotation Mismatch

**File:** `pts/mod/config.pct.py:101-102`

**Problem:** Return type says `str` but returns `Path`.

**Current code:**
```python
@property
def default_rclone_exclude_path(self) -> str:
    return self.config_path.parent / "default.rclone_exclude"
```

**Fix:** Change return type to `Path`.

```python
@property
def default_rclone_exclude_path(self) -> Path:
    return self.config_path.parent / "default.rclone_exclude"
```

---

### 12. Parameter Name Inconsistency in CLI Sync Calls

**File:** `pts/mod/_cli/main.pct.py:419`

**Problem:** Passing `repo_index_names=repo_index_name` but function expects `repo_index_name`.

**Current code:**
```python
asyncio.run(sync_repo(
    config_path=app_state['config_path'],
    repo_index_names=repo_index_name,  # Wrong parameter name
    ...
))
```

**Fix:** Use correct parameter name.

```python
asyncio.run(sync_repo(
    config_path=app_state['config_path'],
    repo_index_name=repo_index_name,
    ...
))
```

---

## Execution Order

Recommended order of fixes (by risk and dependency):

1. **Bug #1** - Infinite recursion (critical, blocks functionality)
2. **Bug #3** - Uninitialized variable (critical, runtime crash)
3. **Bug #4** - raise on typer.echo (critical, runtime crash)
4. **Bug #5** - Wrong object method (critical, runtime crash)
5. **Bug #6** - Missing return (critical, silent failure)
6. **Bug #7** - Wrong variable in filter (critical, logic error)
7. **Bug #8** - Symlink comparison (critical, logic error)
8. **Bug #2** - Return type annotation (medium, type checking)
9. **Bug #11** - Type annotation mismatch (medium, type checking)
10. **Bug #12** - Parameter name (medium, clarity)
11. **Bug #9** - Typo (low, cosmetic)
12. **Bug #10** - Trailing backslash (low, cosmetic)

---

## Post-Fix Verification

After applying fixes:

1. Run `nbl export --reverse` to sync pts → nbs
2. Run `nbl export` to regenerate src/repoyard/
3. Run `pytest tests/` to verify no regressions
4. Run `nbl test` to verify notebooks execute correctly
