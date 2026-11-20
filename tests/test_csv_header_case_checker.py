#!/usr/bin/env python3
"""Tests for csv_header_case_checker — stdlib unittest only."""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import csv_header_case_checker as checker

REPO = Path(__file__).resolve().parent.parent


def run_cli(argv):
    """Run main(argv), capture stdout/stderr, return (code, out, err)."""
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            code = checker.main(argv)
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def write(tmp, name, text, encoding="utf-8"):
    path = Path(tmp) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text, encoding=encoding)
    return str(path)


def findings_of(text):
    return checker.check_text(text)


class TestHeaders(unittest.TestCase):
    def test_clean_file_passes(self):
        bad, errors = findings_of("user_id,first_name\n1,Ada\n")
        self.assertEqual(bad, [])
        self.assertEqual(errors, [])

    def test_plain_bad_header_flagged(self):
        bad, _ = findings_of("UserID,first_name\n1,Ada\n")
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["line"], 1)
        self.assertEqual(bad[0]["column"], 1)
        self.assertEqual(bad[0]["header"], "UserID")

    def test_several_bad_headers_in_order(self):
        bad, _ = findings_of("UserID,first_name,Last Name,user-id\n")
        self.assertEqual(len(bad), 3)
        self.assertEqual([item["column"] for item in bad], [1, 3, 4])
        self.assertEqual([item["header"] for item in bad],
                         ["UserID", "Last Name", "user-id"])

    def test_uppercase_header_flagged(self):
        bad, _ = findings_of("Name,first_name\nAda,x\n")
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["column"], 1)

    def test_header_with_space_flagged(self):
        bad, _ = findings_of("user_id,first name\n1,Ada\n")
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["column"], 2)

    def test_header_with_hyphen_flagged(self):
        bad, _ = findings_of("user-id,first_name\n1,Ada\n")
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["header"], "user-id")

    def test_header_starting_with_digit_flagged(self):
        bad, _ = findings_of("2fa_code,first_name\n1,Ada\n")
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["header"], "2fa_code")

    def test_header_starting_with_underscore_flagged(self):
        bad, _ = findings_of("_user_id,first_name\n1,Ada\n")
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["header"], "_user_id")

    def test_empty_header_flagged(self):
        bad, _ = findings_of("user_id,,first_name\n1,,Ada\n")
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["column"], 2)
        self.assertEqual(bad[0]["header"], "")

    def test_header_with_trailing_underscore_passes(self):
        bad, _ = findings_of("user_id_,first_name\n1,Ada\n")
        self.assertEqual(bad, [])

    def test_single_letter_header_passes(self):
        bad, _ = findings_of("a,b\n1,2\n")
        self.assertEqual(bad, [])

    def test_header_with_digits_passes(self):
        bad, _ = findings_of("retry_count_2,address_line_1\n3,Main St\n")
        self.assertEqual(bad, [])

    def test_quoted_header_with_comma_is_one_header(self):
        bad, _ = findings_of('"user_id","first,name"\n1,Ada\n')
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["column"], 2)
        self.assertEqual(bad[0]["header"], "first,name")

    def test_header_with_leading_space_flagged(self):
        bad, _ = findings_of("user_id, first_name\n1,Ada\n")
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["column"], 2)
        self.assertEqual(bad[0]["header"], " first_name")

    def test_header_with_trailing_space_flagged(self):
        bad, _ = findings_of("user_id ,first_name\n1,Ada\n")
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["column"], 1)
        self.assertEqual(bad[0]["header"], "user_id ")

    def test_bom_stripped_before_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bom.csv",
                         b"\xef\xbb\xbfuser_id,first_name\n1,Ada\n")
            bad, errors = checker.check_file(path)
            self.assertEqual(bad, [])
            self.assertEqual(errors, [])

    def test_empty_file_is_an_error(self):
        bad, errors = findings_of("")
        self.assertEqual(bad, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("no header row", errors[0])

    def test_blank_line_only_is_an_error(self):
        bad, errors = findings_of("\n")
        self.assertEqual(bad, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("empty header row", errors[0])

    def test_data_rows_never_checked(self):
        bad, _ = findings_of("user_id,first_name\nBadHeader,BadName\n")
        self.assertEqual(bad, [])

    def test_header_spanning_lines_through_quoted_newline(self):
        bad, _ = findings_of('"a\nb",ok\n1,2\n')
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["line"], 1)
        self.assertEqual(bad[0]["column"], 1)
        self.assertEqual(bad[0]["header"], "a\nb")


class TestCli(unittest.TestCase):
    def test_clean_file_exit_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "ok.csv", "user_id,first_name\n1,Ada\n")
            code, out, _ = run_cli([path])
            self.assertEqual(code, 0)
            self.assertIn("OK", out)
            self.assertIn("every header is snake_case", out)

    def test_flagged_file_exit_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.csv", "UserID,first_name\n1,Ada\n")
            code, out, _ = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn(
                'FAIL %s: line 1, column 1: header "UserID" is not '
                "snake_case" % path, out)
            self.assertIn("1 header(s) not snake_case", out)

    def test_folder_walk(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "a.csv", "user_id\n1\n")
            write(tmp, "b.csv", "UserID\n1\n")
            write(tmp, "notes.txt", "UserID\n1\n")
            code, out, _ = run_cli([tmp])
            self.assertEqual(code, 1)
            self.assertIn("Checked 2 file(s)", out)
            self.assertNotIn("notes.txt", out)

    def test_nested_folders(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "sub/deep.csv", "UserID\n1\n")
            code, out, _ = run_cli([tmp])
            self.assertEqual(code, 1)
            self.assertIn("deep.csv", out)

    def test_no_recursive(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "top.csv", "user_id\n1\n")
            write(tmp, "sub/deep.csv", "UserID\n1\n")
            code, out, _ = run_cli(["--no-recursive", tmp])
            self.assertEqual(code, 0)
            self.assertIn("OK — 1 file(s) checked", out)

    def test_exclude_skips_a_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "a.csv", "UserID\n1\n")
            write(tmp, "skip.csv", "UserID\n1\n")
            code, out, _ = run_cli(["--exclude", "skip.csv", tmp])
            self.assertEqual(code, 1)
            self.assertIn("Checked 1 file(s)", out)
            self.assertNotIn("skip.csv", out)

    def test_git_folder_skipped_in_walk(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, ".git/hooks/bad.csv", "UserID\n1\n")
            write(tmp, "a.csv", "user_id\n1\n")
            code, out, _ = run_cli([tmp])
            self.assertEqual(code, 0)
            self.assertIn("OK — 1 file(s) checked", out)

    def test_direct_file_checked_whatever_its_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "data.txt", "UserID\n1\n")
            code, out, _ = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn("data.txt", out)

    def test_duplicate_paths_checked_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.csv", "UserID\n1\n")
            code, out, _ = run_cli([path, path])
            self.assertEqual(code, 1)
            self.assertIn("Checked 1 file(s)", out)

    def test_json_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.csv", "UserID\n1\n")
            code, out, _ = run_cli(["--json", path])
            self.assertEqual(code, 1)
            data = json.loads(out)
            self.assertEqual(data["checked"], 1)
            self.assertEqual(data["findings"], 1)
            self.assertEqual(
                data["files"][0]["findings"][0]["line"], 1)
            self.assertEqual(
                data["files"][0]["findings"][0]["column"], 1)
            self.assertEqual(
                data["files"][0]["findings"][0]["header"], "UserID")
            self.assertEqual(data["files"][0]["errors"], [])

    def test_stdin_clean(self):
        old_stdin = sys.stdin
        sys.stdin = io.StringIO("user_id\n1\n")
        try:
            code, out, _ = run_cli(["--stdin"])
        finally:
            sys.stdin = old_stdin
        self.assertEqual(code, 0)
        self.assertIn("every header is snake_case", out)

    def test_stdin_dirty(self):
        old_stdin = sys.stdin
        sys.stdin = io.StringIO("UserID\n1\n")
        try:
            code, out, _ = run_cli(["--stdin"])
        finally:
            sys.stdin = old_stdin
        self.assertEqual(code, 1)
        self.assertIn('FAIL <stdin>: line 1, column 1: header "UserID"',
                      out)

    def test_stdin_with_paths_is_usage_error(self):
        code, _, err = run_cli(["--stdin", "a.csv"])
        self.assertEqual(code, 2)

    def test_no_paths_is_usage_error(self):
        code, _, err = run_cli([])
        self.assertEqual(code, 2)

    def test_missing_path_exit_2(self):
        code, _, err = run_cli(["/no/such/file.csv"])
        self.assertEqual(code, 2)
        self.assertIn("no such file or folder", err)

    def test_empty_folder_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = run_cli([tmp])
            self.assertEqual(code, 2)
            self.assertIn("no .csv files found", err)

    def test_bad_flag_exit_2(self):
        code, _, _ = run_cli(["--nope", "a.csv"])
        self.assertEqual(code, 2)

    def test_version(self):
        code, out, _ = run_cli(["--version"])
        self.assertEqual(code, 0)
        self.assertIn("csv_header_case_checker", out)

    def test_non_utf8_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.csv", b"\xff\xfe{}")
            code, out, _ = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn("not valid UTF-8", out)

    def test_input_files_left_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = "UserID\n1\n"
            path = write(tmp, "bad.csv", text)
            run_cli([path])
            self.assertEqual(Path(path).read_text(), text)

    def test_cli_runs_from_another_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.csv", "UserID\n1\n")
            result = subprocess.run(
                [sys.executable,
                 str(REPO / "src" / "csv_header_case_checker.py"), path],
                capture_output=True, text=True, cwd="/")
            self.assertEqual(result.returncode, 1)
            self.assertIn('header "UserID" is not snake_case',
                          result.stdout)

    def test_cli_runs_under_fake_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.csv", "UserID\n1\n")
            env = dict(os.environ, HOME=tmp)
            result = subprocess.run(
                [sys.executable,
                 str(REPO / "src" / "csv_header_case_checker.py"), path],
                capture_output=True, text=True, cwd=tmp, env=env)
            self.assertEqual(result.returncode, 1)

    def test_run_example_output_matches_sample(self):
        sample = (REPO / "examples" / "sample-output.md").read_text()
        result = subprocess.run(
            ["sh", str(REPO / "examples" / "run-example.sh")],
            capture_output=True, text=True, cwd=str(REPO))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), sample.strip())

    def test_readme_quotes_match_real_runs(self):
        readme = (REPO / "README.md").read_text()
        flagged = (REPO / "examples" / "flagged.csv").read_text()
        bad, _ = checker.check_text(flagged)
        for item in bad:
            line = ("FAIL examples/flagged.csv: line %d, column %d: %s"
                    % (item["line"], item["column"], item["reason"]))
            self.assertIn(line, readme)
        self.assertIn(
            "OK — 1 file(s) checked, every header is snake_case.",
            readme)


class TestExamples(unittest.TestCase):
    def test_clean_example_passes(self):
        code, _, _ = run_cli([str(REPO / "examples" / "clean.csv")])
        self.assertEqual(code, 0)

    def test_flagged_example_fails_with_three(self):
        bad, _ = checker.check_text(
            (REPO / "examples" / "flagged.csv").read_text())
        self.assertEqual(len(bad), 3)
        self.assertEqual([item["column"] for item in bad], [1, 3, 4])
        self.assertEqual(bad[0]["header"], "UserID")
        self.assertEqual(bad[1]["header"], "Last Name")
        self.assertEqual(bad[2]["header"], "user-id")

    def test_edge_example_passes(self):
        code, _, _ = run_cli([str(REPO / "examples" / "edge.csv")])
        self.assertEqual(code, 0)


class TestHygiene(unittest.TestCase):
    def _repo_files(self, skip_tests=True):
        """Every file in the repo, minus .git and caches."""
        for path in REPO.rglob("*"):
            if path.is_dir():
                continue
            if ".git" in path.parts or "__pycache__" in path.parts:
                continue
            if path.suffix == ".pyc":
                continue
            if skip_tests and "tests" in path.parts:
                continue
            yield path

    def test_no_placeholder_text(self):
        banned = ["TODO", "coming soon", "lorem", "FIXME", "XXX"]
        hits = []
        for path in self._repo_files(skip_tests=True):
            text = path.read_text(errors="ignore")
            for word in banned:
                if word in text:
                    hits.append("%s: %s" % (path.name, word))
        self.assertEqual(hits, [])

    def test_no_absolute_paths(self):
        hits = []
        for path in self._repo_files(skip_tests=True):
            text = path.read_text(errors="ignore")
            for marker in ("/home/", "/Users/", "C:\\", "/tmp/"):
                if marker in text:
                    hits.append("%s: %s" % (path.name, marker))
        self.assertEqual(hits, [])

    def test_stdlib_imports_only(self):
        import ast
        stdlib = set(sys.stdlib_module_names)
        for target in (REPO / "src" / "csv_header_case_checker.py",
                       REPO / "tests" / "test_csv_header_case_checker.py"):
            tree = ast.parse(target.read_text())
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(a.name.split(".")[0]
                                    for a in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".")[0])
            self.assertFalse(
                imported - stdlib - {"csv_header_case_checker"},
                (target.name, imported))
            self.assertNotIn("yaml", imported)

    def test_no_network_use_in_src(self):
        src = (REPO / "src" / "csv_header_case_checker.py").read_text()
        for marker in ("urllib.request", "requests", "socket",
                       "http.client", "urlopen", "urlretrieve"):
            self.assertNotIn(marker, src, marker)

    def test_gitignore_lists_env_first(self):
        lines = (REPO / ".gitignore").read_text().splitlines()
        self.assertTrue(lines, ".gitignore is empty")
        self.assertEqual(lines[0], ".env")

    def test_ci_runs_the_test_suite(self):
        ci = (REPO / ".github" / "workflows" / "ci.yml").read_text()
        self.assertIn("python3 -m unittest discover -s tests", ci)
        self.assertIn("ubuntu-latest", ci)
        self.assertIn("3.12", ci)
        self.assertIn("actions/checkout", ci)
        self.assertIn("setup-python", ci)
        self.assertIn("push", ci)
        self.assertIn("pull_request", ci)

    def test_readme_names_the_neighbouring_repos(self):
        readme = (REPO / "README.md").read_text()
        for name in ("csv-header-checker-cli",
                     "csv-delimiter-checker-cli",
                     "csv-duplicate-row-checker-cli",
                     "csv-empty-checker-cli"):
            self.assertIn(name, readme)


if __name__ == "__main__":
    unittest.main(verbosity=2)
