#!/usr/bin/env python3
"""Check CSV header names all use snake_case.

Run: python3 src/csv_header_case_checker.py data.csv
     python3 src/csv_header_case_checker.py data/
     python3 src/csv_header_case_checker.py --stdin < data.csv

Mixed-case headers (UserID next to user_id next to
User Id) break case-sensitive consumers — a downstream
script looking for user_id silently finds nothing,
and the failure lands in the consumer, not in the
file. This tool reads the first row of each CSV file,
checks every header name is snake_case (lowercase
letters, digits and underscores, starting with a
letter), and reports each header that is not, with
the file, the line and the column. It exits 1 when
any header fails, so it can fail a CI run. A file
whose headers are all snake_case exits 0.

Only the first row is checked — the header row. Data
rows are never read for content, and a header is
checked exactly as written: a leading or trailing
space makes it fail, because the name on disk is not
snake_case. A file given directly on the command line
is always checked, whatever its name. A folder is
walked for files ending in .csv only, recursively by
default (--no-recursive stops at the top level). .git
folders are never walked, and directory links are
never followed.

It never edits a file, never touches the network, and
reads only the files and folders you point it at.
"""

import argparse
import csv
import fnmatch
import io
import json
import os
import re
import sys
from pathlib import Path

__version__ = "1.0.0"

CSV_SUFFIX = ".csv"

SNAKE_CASE = re.compile(r"^[a-z][a-z0-9_]*$")


def check_text(text):
    """Check one CSV document given as text.

    Returns (findings, errors). A finding is a dict
    with "line", "column" and "header": line is always
    1, the header row, and column is the header's
    position in the row, counting from 1.
    """
    try:
        rows = list(csv.reader(io.StringIO(text)))
    except csv.Error as exc:
        return [], ["not valid CSV: %s" % exc]
    if not rows:
        return [], ["empty file, no header row"]
    header = rows[0]
    if not header:
        return [], ["empty header row"]
    findings = []
    for column, name in enumerate(header, start=1):
        if not SNAKE_CASE.match(name):
            findings.append({
                "line": 1,
                "column": column,
                "header": name,
                "reason": (
                    'header "%s" is not snake_case '
                    "(lowercase letters, digits and "
                    "underscores, starting with a letter)"
                    % name),
            })
    return findings, []


def check_file(path):
    """Check one file. Returns (findings, errors)."""
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return [], ["not valid UTF-8"]
    except OSError as exc:
        return [], ["could not read the file: %s" % exc]
    return check_text(text)


def _is_excluded(name, patterns):
    return any(fnmatch.fnmatch(name, pat) for pat in patterns)


def collect_paths(paths, recursive, exclude):
    """Turn command-line paths into a sorted list of files.

    A file given directly is always checked, whatever its
    name. A folder is walked for files ending in .csv
    only. .git folders are never walked, and directory
    links are never followed.
    """
    found = []
    seen = set()
    for given in paths:
        target = Path(given)
        if target.is_file():
            key = str(target.resolve())
            if key not in seen:
                seen.add(key)
                found.append(str(target))
        elif target.is_dir():
            if recursive:
                walker = os.walk(target, followlinks=False)
            else:
                walker = [(str(target), [], sorted(
                    p.name for p in target.iterdir() if p.is_file()))]
            for root, dirs, files in walker:
                dirs[:] = sorted(
                    d for d in dirs if d != ".git")
                for name in sorted(files):
                    if not name.endswith(CSV_SUFFIX):
                        continue
                    if _is_excluded(name, exclude):
                        continue
                    full = os.path.join(root, name)
                    key = str(Path(full).resolve())
                    if key not in seen:
                        seen.add(key)
                        found.append(full)
        else:
            found.append(given)
    return sorted(found)


def _fail_line(path, finding):
    return ('FAIL %s: line %d, column %d: %s'
            % (path, finding["line"], finding["column"],
               finding["reason"]))


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="csv_header_case_checker",
        description="Check CSV header names all use snake_case.")
    parser.add_argument("paths", nargs="*", metavar="PATH",
                        help="CSV file or folder to check")
    parser.add_argument("--json", action="store_true",
                        help="print the result as JSON")
    parser.add_argument("--stdin", action="store_true",
                        help="check one CSV document from standard input")
    parser.add_argument("--no-recursive", action="store_true",
                        help="do not walk into subfolders")
    parser.add_argument("--exclude", action="append", default=[],
                        metavar="PATTERN",
                        help="skip files whose name matches the pattern "
                        "(may be given more than once)")
    parser.add_argument("--version", action="version",
                        version="csv_header_case_checker " + __version__)
    args = parser.parse_args(argv)

    results = []
    if args.stdin:
        if args.paths:
            print("error: --stdin takes no paths",
                  file=sys.stderr)
            return 2
        text = sys.stdin.read()
        findings, errors = check_text(text)
        results.append(("<stdin>", findings, errors))
    else:
        if not args.paths:
            print("error: give at least one file or folder to check",
                  file=sys.stderr)
            return 2
        missing = [p for p in args.paths
                   if not Path(p).exists()]
        if missing:
            for path in missing:
                print("error: no such file or folder: %s" % path,
                      file=sys.stderr)
            return 2
        files = collect_paths(args.paths, not args.no_recursive,
                              args.exclude)
        if not files:
            print("error: no .csv files found", file=sys.stderr)
            return 2
        for path in files:
            findings, errors = check_file(path)
            results.append((path, findings, errors))

    checked = len(results)
    total_findings = sum(len(f) for _, f, _ in results)
    bad_files = sum(1 for _, f, e in results if f or e)

    if args.json:
        print(json.dumps({
            "files": [
                {"path": path, "findings": findings,
                 "errors": errors}
                for path, findings, errors in results
            ],
            "checked": checked,
            "findings": total_findings,
        }, indent=2))
    else:
        for path, findings, errors in results:
            for finding in findings:
                print(_fail_line(path, finding))
            for error in errors:
                print("ERROR %s: %s" % (path, error))
        if total_findings == 0 and bad_files == 0:
            print("OK — %d file(s) checked, every header is "
                  "snake_case." % checked)
        else:
            print("Checked %d file(s), %d header(s) not snake_case "
                  "in %d file(s)."
                  % (checked, total_findings, bad_files))

    if total_findings or bad_files:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
