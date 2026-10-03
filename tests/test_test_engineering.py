"""Tests for the test-engineering runtime (spec 0097).

The CTest and GoogleTest paths are exercised with XML fixtures and a stand-in shell script, because
CMake and GoogleTest are not assumed to be installed. Real compilation tests need a C++ compiler and skip
without one.
"""

import json
import shutil
import stat
import textwrap
from pathlib import Path

import pytest

from quantsmith.test_engineering import cli
from quantsmith.test_engineering.cpp_harness import UnsupportedSignature, build_cases, parse_signature, probe_cpp
from quantsmith.test_engineering.detect import detect_stack
from quantsmith.test_engineering.edgecases import edge_values, generate_pytest_source, probe_function
from quantsmith.test_engineering.flaky import check_pytest, to_node_id
from quantsmith.test_engineering.junit import parse_junit
from quantsmith.test_engineering.mutation import apply_mutant, enumerate_mutants, run_mutation
from quantsmith.test_engineering.report import RunReport, CommandResult
from quantsmith.test_engineering.runners import run_command, run_gtest_binary, run_pytest
from quantsmith.test_engineering.sanitizers import parse_sanitizer_output

HAS_CXX = bool(shutil.which("clang++") or shutil.which("g++"))


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text), encoding="utf-8")
    return path


# ---- report / junit / sanitizers --------------------------------------------------------------

def test_zero_tests_is_never_a_pass():
    rep = RunReport(tool="pytest", command=CommandResult(argv=["x"], cwd=".", returncode=5, stdout="", stderr="", duration_s=0.0, timed_out=False))
    assert rep.verdict == "no_tests"


def test_parse_junit_pytest_and_gtest_forms():
    pytest_xml = '<testsuites><testsuite><testcase classname="a.b" name="t1" time="0.1"/><testcase classname="a.b" name="t2"><failure message="boom"/></testcase><testcase classname="a.b" name="t3"><skipped/></testcase></testsuite></testsuites>'
    got = {r.id: r.status for r in parse_junit(pytest_xml)}
    assert got == {"a.b::t1": "passed", "a.b::t2": "failed", "a.b::t3": "skipped"}
    gtest_xml = '<testsuites><testsuite name="Suite"><testcase name="Case" classname="Suite" status="run"><failure message="x"/></testcase></testsuite></testsuites>'
    assert [r.status for r in parse_junit(gtest_xml)] == ["failed"]


def test_parse_junit_rejects_oversize():
    with pytest.raises(ValueError):
        parse_junit("<a>" + "x" * (21 * 1024 * 1024) + "</a>")


def test_sanitizer_parsing_kinds():
    ubsan = "lib.hpp:3:40: runtime error: signed integer overflow: 2147483647 + 1 cannot be represented in type 'int'"
    f = parse_sanitizer_output(ubsan)
    assert f and f[0]["sanitizer"] == "UndefinedBehaviorSanitizer" and f[0]["kind"] == "signed-integer-overflow"
    asan = "==1==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x1\n    #0 0x1 in at lib.hpp:4"
    assert parse_sanitizer_output(asan)[0]["kind"] == "heap-buffer-overflow"
    assert parse_sanitizer_output("all good") == []


# ---- runners ----------------------------------------------------------------------------------

def test_run_command_rejects_string_argv(tmp_path):
    with pytest.raises(TypeError):
        run_command("echo hi", tmp_path, 5)  # type: ignore[arg-type]


def test_run_command_times_out_and_caps_output(tmp_path):
    r = run_command(["python3", "-c", "import time; time.sleep(30)"], tmp_path, 0.5)
    assert r.timed_out
    big = run_command(["python3", "-c", "print('x' * 5000000)"], tmp_path, 20, max_output=1000)
    assert len(big.stdout) <= 1200


def test_run_pytest_reports_pass_fail_and_no_tests(tmp_path):
    write(tmp_path / "test_ok.py", "def test_a():\n    assert True\n")
    assert run_pytest(tmp_path).verdict == "passed"
    write(tmp_path / "test_bad.py", "def test_b():\n    assert False\n")
    rep = run_pytest(tmp_path)
    assert rep.verdict == "failed" and rep.summary["failed"] == 1
    empty = tmp_path / "empty"
    empty.mkdir()
    assert run_pytest(empty).verdict in ("no_tests", "error")


def test_gtest_stand_in_binary_parses_xml(tmp_path):
    """Stand-in: a script that writes GoogleTest-shaped XML to --gtest_output (real GoogleTest not required)."""
    script = write(tmp_path / "fake_gtest", """\
        #!/bin/sh
        for a in "$@"; do case "$a" in --gtest_output=xml:*) out="${a#--gtest_output=xml:}";; esac; done
        echo '<testsuites><testsuite name="S"><testcase name="A" classname="S"/><testcase name="B" classname="S"><failure message="no"/></testcase></testsuite></testsuites>' > "$out"
        exit 1
    """)
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    rep = run_gtest_binary(script, tmp_path)
    assert rep.summary["passed"] == 1 and rep.summary["failed"] == 1 and rep.verdict == "failed"


# ---- detect -----------------------------------------------------------------------------------

def test_detect_python_and_cpp(tmp_path):
    write(tmp_path / "pyproject.toml", "[project]\nname='x'\n")
    write(tmp_path / "tests" / "test_a.py", "def test_a(): pass\n")
    write(tmp_path / "CMakeLists.txt", "enable_testing()\nadd_executable(t t.cpp)\nadd_test(NAME t COMMAND t)\n")
    write(tmp_path / "t.cpp", "int main(){return 0;}\n")
    write(tmp_path / "node_modules" / "skipped.py", "x=1\n")
    res = detect_stack(tmp_path)
    langs = {x["language"]: x for x in res["languages"]}
    assert "python" in langs and "cpp" in langs
    assert not any("node_modules" in e for e in langs["python"]["evidence"])


def test_detect_marks_javascript_unsupported(tmp_path):
    write(tmp_path / "package.json", "{}")
    write(tmp_path / "a.js", "1\n")
    res = detect_stack(tmp_path)
    assert "javascript/typescript" in res["unsupported"]
    assert {x["language"]: x for x in res["languages"]}["javascript/typescript"]["supported"] is False


# ---- edge cases -------------------------------------------------------------------------------

def test_edge_catalog_has_the_classics():
    values = {e.value for e in edge_values(int)}
    assert {0, -1} <= values and any(v > 2**31 for v in values)
    assert any(e.value != e.value for e in edge_values(float))  # NaN
    assert edge_values("not a type") == [] or isinstance(edge_values("not a type"), list)


def test_probe_finds_divide_by_zero_and_empty_index():
    def ratio(a: float, b: float) -> float:
        return a / b

    def first(xs: list):
        return xs[0]

    r = probe_function(ratio)
    assert any("ZeroDivisionError" in json.dumps(f) for f in r["findings"])
    assert any("IndexError" in json.dumps(f) for f in probe_function(first)["findings"])


def test_probe_respects_documented_exceptions():
    def strict(x: int) -> int:
        if x < 0:
            raise ValueError("negative")
        return x
    assert probe_function(strict, allowed_exceptions=[ValueError])["findings"] == []


def test_probe_flags_input_mutation():
    def sneaky(xs: list):
        xs.append(1)
        return len(xs)
    assert any("mutated" in json.dumps(f) for f in probe_function(sneaky)["findings"])


def test_generated_characterization_tests_are_valid_python():
    def double(x: int) -> int:
        return x * 2
    src = generate_pytest_source("demo", "double", probe_function(double), double)
    compile(src, "<generated>", "exec")
    assert "characterization" in src.lower()


# ---- mutation ---------------------------------------------------------------------------------

CALC = "def clamp(x, lo, hi):\n    if x < lo:\n        return lo\n    if x > hi:\n        return hi\n    return x\n"


def test_mutants_are_deterministic_and_change_source():
    sites = enumerate_mutants(CALC)
    assert sites == enumerate_mutants(CALC) and len(sites) >= 5
    assert {s.operator for s in sites} >= {"ROR", "COND", "RET"}
    assert all(apply_mutant(CALC, s.index) != apply_mutant(CALC, -1) for s in sites)


def test_docstrings_are_not_mutated():
    src = 'def f():\n    "doc 1"\n    return 1\n'
    assert all(s.line != 2 for s in enumerate_mutants(src))


def test_mutation_kills_with_good_tests_and_reports_survivor_and_uncovered(tmp_path):
    write(tmp_path / "calc.py", CALC + "\ndef untested(a):\n    return a * 2\n\ndef weak(a):\n    return a + 1\n")
    write(tmp_path / "test_calc.py", """\
        from calc import clamp, weak
        def test_clamp():
            assert clamp(5, 0, 10) == 5
            assert clamp(-1, 0, 10) == 0
            assert clamp(11, 0, 10) == 10
        def test_weak_runs():
            weak(1)
    """)
    res = run_mutation(tmp_path, "calc.py")
    assert res["baseline"] == "passed"
    assert res["uncovered"] >= 1 and any(u["line"] >= 8 for u in res["uncovered_mutants"])
    assert any(s["operator"] in ("AOR", "RET", "CONST") for s in res["survivors"])
    assert (tmp_path / "calc.py").read_text().startswith("def clamp")  # working tree untouched


def test_mutation_refuses_a_failing_baseline(tmp_path):
    write(tmp_path / "m.py", "def f():\n    return 1\n")
    write(tmp_path / "test_m.py", "from m import f\ndef test_f():\n    assert f() == 2\n")
    res = run_mutation(tmp_path, "m.py")
    assert res["score"] is None and res["baseline"] != "passed"


def test_mutation_rejects_target_outside_root(tmp_path):
    with pytest.raises(ValueError):
        run_mutation(tmp_path, "../elsewhere.py")


# ---- flakiness --------------------------------------------------------------------------------

def test_to_node_id_converts_dotted_names(tmp_path):
    write(tmp_path / "pkg" / "test_m.py", "")
    assert to_node_id(tmp_path, "pkg.test_m.TestC::test_x") == "pkg/test_m.py::TestC::test_x"
    assert to_node_id(tmp_path, "test_gone::test_x") == "test_gone::test_x"


def test_flaky_detects_order_and_hash_dependence(tmp_path):
    write(tmp_path / "test_f.py", """\
        import os
        STATE = []
        def test_a_sets_state():
            STATE.append(1)
        def test_b_needs_state():
            assert STATE == [1]
        def test_hash_seed_one_fails():
            assert os.environ.get("PYTHONHASHSEED") != "1"
        def test_ok():
            assert True
    """)
    res = check_pytest(tmp_path, runs=2, shuffles=8, hash_seeds=("0", "1"))
    assert res["verdict"] == "flakiness_found"
    assert any(o["test"].endswith("test_b_needs_state") for o in res["order_dependent"])
    assert any(h["test"].endswith("test_hash_seed_one_fails") for h in res["hash_seed_dependent"])
    assert res["classification"]["test_f::test_ok"] == "stable"


def test_flaky_reports_no_tests_instead_of_stable(tmp_path):
    res = check_pytest(tmp_path, runs=2, shuffles=1)
    assert res["tests"] == 0 and res["verdict"] != "no_flakiness_observed"


# ---- C++ harness ------------------------------------------------------------------------------

def test_parse_signature_and_unsupported():
    ret, name, params = parse_signature("int at(const std::vector<int>& v, std::size_t i)")
    assert (ret, name) == ("int", "at") and [p.type for p in params] == ["std::vector<int>", "std::size_t"]
    with pytest.raises(UnsupportedSignature):
        parse_signature("int f(Widget w)")


def test_cases_vary_one_parameter_at_a_time():
    _, _, params = parse_signature("int add(int a, int b)")
    cases = build_cases(params)
    assert {c["param"] for c in cases} == {"a", "b"} and len({c["id"] for c in cases}) == len(cases)


@pytest.mark.skipif(not HAS_CXX, reason="needs a C++ compiler")
def test_cpp_probe_finds_real_undefined_behaviour(tmp_path):
    write(tmp_path / "lib.hpp", """\
        #pragma once
        #include <cstring>
        #include <vector>
        inline int add(int a, int b) { return a + b; }
        inline std::size_t len(const char* s) { return std::strlen(s); }
        inline int safe(int a) { return a; }
    """)
    add = probe_cpp("lib.hpp", "int add(int a, int b)", cwd=tmp_path)
    assert add["built"] and any(f["sanitizer"] and f["sanitizer"][0]["kind"] == "signed-integer-overflow" for f in add["findings"])
    assert probe_cpp("lib.hpp", "std::size_t len(const char* s)", cwd=tmp_path)["findings"]
    assert probe_cpp("lib.hpp", "int safe(int a)", cwd=tmp_path)["findings"] == []


@pytest.mark.skipif(not HAS_CXX, reason="needs a C++ compiler")
def test_cpp_probe_reports_compile_failure_not_success(tmp_path):
    write(tmp_path / "lib.hpp", "#pragma once\n")
    res = probe_cpp("lib.hpp", "int missing(int a)", cwd=tmp_path)
    assert res["built"] is False and res["compile_errors"]


# ---- CLI --------------------------------------------------------------------------------------

def test_cli_detect_and_exit_codes(tmp_path, capsys):
    write(tmp_path / "test_a.py", "def test_a(): pass\n")
    assert cli.main(["detect", "--root", str(tmp_path)]) == 0
    assert "python" in capsys.readouterr().out
    assert cli.main(["edges", "--root", str(tmp_path), "--target", "nodots"]) == 2
    assert json.loads(capsys.readouterr().out)["error"] == "bad_input"


def test_cli_run_returns_one_on_failure(tmp_path, capsys):
    write(tmp_path / "test_bad.py", "def test_b():\n    assert False\n")
    assert cli.main(["run", "--tool", "pytest", "--root", str(tmp_path)]) == 1


def test_cli_passes_extra_args_after_double_dash(tmp_path, capsys):
    write(tmp_path / "test_a.py", "def test_a1(): pass\ndef test_a2(): pass\n")
    cli.main(["run", "--tool", "pytest", "--root", str(tmp_path), "--", "-k", "a1"])
    assert json.loads(capsys.readouterr().out)["summary"]["total"] == 1


def test_cli_missing_tool_exits_two(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("PATH", "")
    assert cli.main(["run", "--tool", "ctest", "--root", str(tmp_path)]) == 2
    assert json.loads(capsys.readouterr().out)["error"] == "tool_missing"


# ---- found by validating against a real project (BugsInPy cookiecutter), see specs/0097/validation.md ----

def test_untyped_function_reports_nothing_probed_not_clean():
    def untyped(value):
        return value

    res = probe_function(untyped)
    assert res["status"] == "nothing_probed" and res["cases"] == 0 and "NOTHING WAS PROBED" in res["note"]
    assert probe_function(untyped, param_types={"value": str})["cases"] > 0


def test_probe_infers_type_from_simple_default():
    def f(n=3):
        return n
    res = probe_function(f)
    assert res["status"] == "probed" and res["hint_source"]["n"] == "inferred from default"


def test_probe_isolates_relative_file_side_effects(tmp_path, monkeypatch):
    import os
    monkeypatch.chdir(tmp_path)

    def make_dir(path: str):
        try:
            os.makedirs(path)
        except OSError:
            return False
        return True

    res = probe_function(make_dir)
    assert res["isolated_cwd"] is True and list(tmp_path.iterdir()) == []
    assert os.getcwd() == str(tmp_path.resolve()) or os.getcwd() == str(tmp_path)


def test_cli_edges_exit_two_when_nothing_probed(tmp_path, capsys):
    write(tmp_path / "legacy_mod.py", "def f(value):\n    return value\n")
    assert cli.main(["edges", "--root", str(tmp_path), "--target", "legacy_mod:f"]) == 2
    assert cli.main(["edges", "--root", str(tmp_path), "--target", "legacy_mod:f", "--hint", "value=str"]) == 0
    capsys.readouterr()
    assert cli.main(["edges", "--root", str(tmp_path), "--target", "legacy_mod:f", "--hint", "value=widget"]) == 2


def test_run_passes_env_so_environment_dependent_bugs_reproduce(tmp_path, capsys):
    write(tmp_path / "test_env.py", "import os\ndef test_locale_flag():\n    assert os.environ.get('QTE_FLAG') != 'on'\n")
    assert cli.main(["run", "--tool", "pytest", "--root", str(tmp_path)]) == 0
    assert cli.main(["run", "--tool", "pytest", "--root", str(tmp_path), "--env", "QTE_FLAG=on"]) == 1
    capsys.readouterr()
    assert cli.main(["run", "--tool", "pytest", "--root", str(tmp_path), "--env", "BADPAIR"]) == 2


def test_run_uses_the_projects_interpreter_flag(tmp_path, capsys):
    import sys
    write(tmp_path / "test_ok.py", "def test_ok():\n    assert True\n")
    assert cli.main(["run", "--tool", "pytest", "--root", str(tmp_path), "--python", sys.executable]) == 0


def test_same_named_tests_in_different_modules_keep_distinct_ids_and_record_all_seeds(tmp_path):
    write(tmp_path / "pkg" / "__init__.py", "")
    write(tmp_path / "pkg" / "test_one.py", "import os\ndef test_same():\n    os.mkdir('shared')\n")
    write(tmp_path / "pkg" / "test_two.py", "import os\ndef test_same():\n    os.mkdir('shared')\n")
    res = check_pytest(tmp_path, runs=2, shuffles=3, hash_seeds=("0",))
    assert len({t for t in res["classification"]}) == 2


def test_order_dependence_reports_every_failing_seed(tmp_path):
    write(tmp_path / "test_o.py", "S = []\ndef test_a():\n    S.append(1)\ndef test_b():\n    assert S == [1]\n")
    res = check_pytest(tmp_path, runs=2, shuffles=8, hash_seeds=("0",))
    hit = next(o for o in res["order_dependent"] if o["test"].endswith("test_b"))
    assert hit["seed"] == hit["seeds"][0] and hit["failed_in_shuffles"] == len(hit["seeds"]) >= 1
