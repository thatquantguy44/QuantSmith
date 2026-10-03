# Validation on a real project: BugsInPy / cookiecutter

- **Spec:** 0097-test-engineering-runtime
- **Date:** 2026-10-03
- **Corpus:** [BugsInPy](https://github.com/soarsmu/BugsInPy), project `cookiecutter`, bug 1 (a JSON context file opened without
  `encoding='utf-8'`; fails only under a non-UTF-8 locale). Nothing from the corpus is committed to this repository.
- **Setup:** clone cookiecutter at the fixed commit `7f6804c`, re-introduce the bug by reversing BugsInPy's `bug_patch.txt`, Python 3.11
  venv with pytest, pytest-cov and coverage, `--python` pointing at that venv.

## Results

| Check | Command shape | Result |
| --- | --- | --- |
| Detect the bug | `run --tool pytest` on the bug's test, with the bug in and out | Bug in: `failed`, exit 1, `ContextDecodingException`. Bug out: `passed`, exit 0. Only reproduced with `--env LC_ALL=C --env PYTHONUTF8=0`; the default UTF-8 locale hides it, as expected. |
| Honest reporting | the bug's test on the *buggy commit* (test absent) | `error`, never a pass. |
| Collection error | one test module missing a dependency | `failed` (one collection error), not a pass; the 294 other tests were not run, which the report shows. |
| Full suite baseline | `run` | 293 passed, 1 skipped, about 2 s. |
| Mutation | `mutate --target cookiecutter/utils.py` | 17 mutants: 15 killed, 2 survived, 0 uncovered, score 0.88. Both survivors are `return False` becoming `return None`: the tests check truthiness only. Genuine weak assertions. |
| Flakiness | `flaky`, 3 runs, 4 shuffles | No flaky or hash-seed-dependent test. One real order dependence: two tests named `test_should_find_existing_cookiecutter` in different modules share a fixture directory; the second errors with `FileExistsError` if the other ran first. Failed in all 4 shuffles. |
| Edge probes | `edges` on `is_repo_url`, `is_zip_file`, `expand_abbreviations`, `make_sure_path_exists` | One finding: `make_sure_path_exists("\x00")` raises an undocumented `ValueError`, where every other bad path returns `False`. |

## Defects in this runtime that the real project exposed (all fixed, each with a regression test)

1. `edges` on untyped code (the common case) probed nothing and returned an empty findings list, which read as clean.
   Now: `status: nothing_probed`, exit `2`, a `--hint name=type` option, and type inference from simple defaults.
2. `edges` created directories in the working directory. Now it runs in a throwaway directory (relative paths only; not a sandbox).
3. No way to run a project's tests with its own interpreter or environment. Added `--python` and repeatable `--env`.
4. The coverage check looked at the tool's interpreter, not the project's. It now checks the one given by `--python`.
5. Order-dependence reports named only the last failing seed. They now list every failing seed.

## Limits of this validation

One project, one bug, Python only. It shows the runner, mutation, flakiness and probe paths work on real code and exposed real
defects; it does not measure detection rates. The CTest and GoogleTest paths were not covered (CMake and GoogleTest not installed).
Kaggle was not used: its defect datasets hold metrics, not code. Larger studies should draw on IDoFT (flaky tests) and more BugsInPy bugs.
