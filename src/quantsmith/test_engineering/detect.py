"""Stack detection (spec 0097): what is in this repository, what tests it has, and what can run here.

Reads files only; it runs nothing. For each language it reports evidence (the files and lines that
justify the claim), the test frameworks it found, test directories, suggested commands, and which
tools are installed. Python and C++ are supported; JavaScript/TypeScript are recognised and reported
as detected-but-unsupported rather than silently ignored.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", ".venv", "venv", "env", "__pycache__", ".tox", ".nox", ".mypy_cache",
             ".ruff_cache", ".pytest_cache", "build", "dist", "cmake-build-debug", "cmake-build-release", ".eggs", "site-packages"}
MAX_FILES = 20_000
MAX_READ = 400_000
CPP_SOURCE = {".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx", ".h", ".c"}
TOOLS = ("python3", "pytest", "coverage", "cmake", "ctest", "make", "ninja", "clang++", "g++", "node", "npm")


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:MAX_READ]
    except OSError:
        return ""


def _walk(root: Path) -> List[Path]:
    out: List[Path] = []
    stack = [root]
    while stack and len(out) < MAX_FILES:
        d = stack.pop()
        try:
            entries = sorted(d.iterdir(), key=lambda p: p.name)
        except OSError:
            continue
        for p in entries:
            if p.is_symlink():
                continue
            if p.is_dir():
                if p.name not in SKIP_DIRS and not p.name.startswith("."):
                    stack.append(p)
            else:
                out.append(p)
    return sorted(out)


def _python_module_installed(name: str) -> bool:
    import importlib.util
    return importlib.util.find_spec(name) is not None


def toolchain() -> Dict[str, Optional[str]]:
    found: Dict[str, Optional[str]] = {t: shutil.which(t) for t in TOOLS}
    found["coverage"] = found["coverage"] or ("python module" if _python_module_installed("coverage") else None)
    found["pytest"] = found["pytest"] or ("python module" if _python_module_installed("pytest") else None)
    found["hypothesis"] = "python module" if _python_module_installed("hypothesis") else None
    return found


def _detect_python(root: Path, files: List[Path]) -> Optional[Dict[str, Any]]:
    rel = lambda p: p.relative_to(root).as_posix()                                    # noqa: E731
    evidence: List[str] = []
    frameworks: set = set()
    test_dirs: set = set()
    for p in files:
        name = p.name
        if name in ("pyproject.toml", "setup.py", "setup.cfg", "pytest.ini", "tox.ini", "conftest.py", ".coveragerc", "uv.lock",
                    "poetry.lock", "Pipfile") or re.fullmatch(r"requirements.*\.txt", name):
            evidence.append(rel(p))
        if name == "conftest.py" or name == "pytest.ini":
            frameworks.add("pytest")
        if name == ".coveragerc":
            frameworks.add("coverage")
        if re.fullmatch(r"test_.*\.py|.*_test\.py", name):
            evidence.append(rel(p))
            test_dirs.add(rel(p.parent) if p.parent != root else ".")
    for name in ("pyproject.toml", "setup.cfg", "tox.ini", "pytest.ini"):
        f = root / name
        if f.is_file():
            text = _read(f)
            if re.search(r"\[tool\.pytest|\[pytest\]|\[tool:pytest\]|pytest", text):
                frameworks.add("pytest")
            if re.search(r"hypothesis", text):
                frameworks.add("hypothesis")
            if re.search(r"\[tool\.coverage|coverage", text):
                frameworks.add("coverage")
    for p in [q for q in files if q.suffix == ".py"][:600]:
        text = _read(p)[:20_000]
        if re.search(r"^\s*(import|from)\s+pytest\b", text, re.M):
            frameworks.add("pytest")
        if re.search(r"^\s*(import|from)\s+unittest\b", text, re.M):
            frameworks.add("unittest")
        if re.search(r"^\s*(import|from)\s+hypothesis\b", text, re.M):
            frameworks.add("hypothesis")
    py_files = [p for p in files if p.suffix == ".py"]
    if not evidence and not py_files:
        return None
    confidence = "high" if any(e.endswith(("pyproject.toml", "setup.py", "pytest.ini", "conftest.py")) or "test_" in e for e in evidence) else "medium"
    cmds = []
    if "unittest" in frameworks and "pytest" not in frameworks:
        cmds.append({"purpose": "run tests", "argv": ["python", "-m", "unittest", "discover"]})
    else:
        cmds.append({"purpose": "run tests", "argv": ["python", "-m", "pytest", "-q"]})
    return {"language": "python", "confidence": confidence, "evidence": sorted(set(evidence))[:25],
            "frameworks": sorted(frameworks), "test_dirs": sorted(test_dirs)[:15], "supported": True, "suggested_commands": cmds}


def _detect_cpp(root: Path, files: List[Path]) -> Optional[Dict[str, Any]]:
    rel = lambda p: p.relative_to(root).as_posix()                                    # noqa: E731
    sources = [p for p in files if p.suffix in CPP_SOURCE and p.suffix != ".c"]
    cmake = [p for p in files if p.name == "CMakeLists.txt"]
    make = [p for p in files if p.name in ("Makefile", "makefile")]
    meson = [p for p in files if p.name == "meson.build"]
    if not (sources or cmake):
        return None
    evidence = [rel(p) for p in (cmake + make + meson)][:12]
    frameworks: set = set()
    flags: set = set()
    fuzz_targets: List[str] = []
    test_dirs: set = set()
    has_enable_testing = has_add_test = False
    for p in cmake:
        t = _read(p)
        has_enable_testing |= bool(re.search(r"enable_testing\s*\(|include\s*\(\s*CTest", t, re.I))
        has_add_test |= bool(re.search(r"add_test\s*\(|gtest_discover_tests|catch_discover_tests|doctest_discover_tests", t, re.I))
        if re.search(r"GTest|googletest|gtest_discover_tests", t, re.I):
            frameworks.add("googletest")
        if re.search(r"Catch2|catch_discover_tests", t, re.I):
            frameworks.add("catch2")
        if re.search(r"doctest", t, re.I):
            frameworks.add("doctest")
        for fl in ("address", "undefined", "thread", "memory", "fuzzer"):
            if re.search(rf"-fsanitize=[^\s\"')]*{fl}", t):
                flags.add(fl)
    for p in sources[:800]:
        t = _read(p)[:30_000]
        if re.search(r"#\s*include\s*[<\"]gtest/gtest\.h[>\"]", t):
            frameworks.add("googletest")
            test_dirs.add(rel(p.parent) if p.parent != root else ".")
        if re.search(r"#\s*include\s*[<\"](catch2/|catch\.hpp)", t):
            frameworks.add("catch2")
            test_dirs.add(rel(p.parent) if p.parent != root else ".")
        if re.search(r"#\s*include\s*[<\"]doctest(/doctest)?\.h[>\"]", t):
            frameworks.add("doctest")
        if "LLVMFuzzerTestOneInput" in t:
            fuzz_targets.append(rel(p))
    cmds = []
    if cmake:
        cmds += [{"purpose": "configure", "argv": ["cmake", "-S", ".", "-B", "build"]},
                 {"purpose": "build", "argv": ["cmake", "--build", "build"]}]
        if has_enable_testing or has_add_test:
            cmds.append({"purpose": "run tests", "argv": ["ctest", "--test-dir", "build", "--output-on-failure"]})
    elif make and re.search(r"^test\s*:", _read(make[0]), re.M):
        cmds.append({"purpose": "run tests", "argv": ["make", "test"]})
    confidence = "high" if (cmake or frameworks) else "medium"
    return {"language": "cpp", "confidence": confidence, "evidence": evidence, "frameworks": sorted(frameworks),
            "test_dirs": sorted(test_dirs)[:15], "sanitizer_flags": sorted(flags), "fuzz_targets": sorted(fuzz_targets)[:15],
            "ctest_registered": bool(has_enable_testing or has_add_test), "supported": True, "suggested_commands": cmds}


def _detect_js(root: Path, files: List[Path]) -> Optional[Dict[str, Any]]:
    rel = lambda p: p.relative_to(root).as_posix()                                    # noqa: E731
    pkgs = [p for p in files if p.name == "package.json"]
    if not pkgs:
        return None
    frameworks: set = set()
    for p in pkgs:
        try:
            data = json.loads(_read(p) or "{}")
        except ValueError:
            continue
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        frameworks |= {f for f in ("jest", "vitest", "mocha") if f in deps}
    return {"language": "javascript/typescript", "confidence": "high", "evidence": [rel(p) for p in pkgs][:8],
            "frameworks": sorted(frameworks), "test_dirs": [], "supported": False, "suggested_commands": [],
            "note": "detected but not supported by this runtime yet"}


def detect_stack(root: str | Path) -> Dict[str, Any]:
    """Describe the repository at ``root`` (read-only). Deterministic for a given tree."""
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError(f"{root} is not a directory")
    files = _walk(root)
    languages = [d for d in (_detect_python(root, files), _detect_cpp(root, files), _detect_js(root, files)) if d]
    tools = toolchain()
    warnings: List[str] = []
    for lang in languages:
        if lang["language"] == "cpp":
            cmds = " ".join(c["argv"][0] for c in lang["suggested_commands"])
            if "cmake" in cmds and not tools["cmake"]:
                warnings.append("C++ project uses CMake but cmake is not installed")
            if "ctest" in cmds and not tools["ctest"]:
                warnings.append("C++ tests are registered with CTest but ctest is not installed")
            if not (tools["clang++"] or tools["g++"]):
                warnings.append("no C++ compiler found (clang++ or g++)")
            if not lang.get("ctest_registered") and lang["frameworks"]:
                warnings.append("a C++ test framework is used but no tests are registered with CTest; run the test binary directly")
        if lang["language"] == "python" and not tools["pytest"]:
            warnings.append("Python tests found but pytest is not installed")
    return {"root": str(root), "files_scanned": len(files), "truncated": len(files) >= MAX_FILES,
            "languages": languages, "toolchain": tools, "warnings": warnings,
            "unsupported": [x["language"] for x in languages if not x["supported"]]}
