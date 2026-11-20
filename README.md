# csv-header-case-checker-cli

Check CSV header names all use snake_case, fail CI when one does not.

[![CI](https://github.com/haiderstudio/csv-header-case-checker-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/haiderstudio/csv-header-case-checker-cli/actions/workflows/ci.yml) [![Licence: MIT](https://img.shields.io/badge/Licence-MIT-yellow.svg)](LICENSE)

## What it does

`csv_header_case_checker` reads the first row of
each CSV file, checks every header name is
snake_case (lowercase letters, digits and
underscores, starting with a letter), and reports
each header that is not, with the file, the line and
the column. It exits 1 when any header fails, so it
can fail a CI run. A file whose headers are all
snake_case exits 0.

- Mixed-case headers (`UserID` next to `user_id`
  next to `User Id`) break case-sensitive consumers
  — a downstream script looking for `user_id`
  silently finds nothing, and the failure lands in
  the consumer, not in the file. A gate that names
  the exact header and column turns it into a
  rename before the file ships.
- Only the first row is checked — the header row.
  Data rows are never read for content. The column
  is the header's position in the row, counting
  from 1, and the line is always 1, the header row.
- A header is checked exactly as written: a leading
  or trailing space makes it fail, because the name
  on disk is not snake_case. A quoted header that
  holds a comma is one header, not two — the CSV
  parser reads the quoting, so `"first,name"` is
  reported once, at column 2.
- A file given directly on the command line is
  always checked, whatever its name. A folder is
  walked for files ending in `.csv` only,
  recursively by default (`--no-recursive` stops
  at the top level). `.git` folders are never
  walked, and directory links are never followed.
- `--json` prints the result as JSON, and `--stdin`
  checks one CSV document read from standard input.
- A file that cannot be read — a file that is not
  valid UTF-8, or an empty file with no header row
  — is reported as an error and fails the check the
  same way a finding does. A UTF-8 byte-order mark
  at the start of the file is stripped before the
  check, so it never makes the first header fail.

## Who it is for

Anyone who ships CSV data files — which is every
team that hands data to another script, another
team, or a customer. One mixed-case header hides in
a file exported from a spreadsheet, and the
consumer fails silently for a reason no one traces
back to a header name. This is the gate that names
it at the pull request, before it ships.

## What it does NOT do

- It does not check whether a header is empty,
  duplicated, or holds spaces. That is repo #40,
  csv-header-checker-cli, which checks header
  cleanliness — empty, duplicate, spaces. The case
  convention of the headers that exist is a
  different check on the same row: a header can be
  clean and still be the wrong case, and a header
  can be the right case and still be duplicated.
- It does not check the delimiter. That is repo
  #95, csv-delimiter-checker-cli — the delimiter is
  a different check on the same files.
- It does not check data rows. That is repo #84,
  csv-duplicate-row-checker-cli, and repo #73,
  csv-empty-checker-cli — the data is a different
  check from the header row.
- It does not rewrite a header into snake_case or
  remove it. It reports, you rename the header.
- It never touches the network, and it only reads
  the files and folders you point it at.

## How this differs

- A fresh search of GitHub on Nov 18, 2026 found 0
  results for `"csv-header-case-checker-cli"` and 0
  results for `csv header case checker`. The field
  is empty for this job.
- So the narrow slice stands: the case convention
  of CSV headers only, per-header reporting with
  line and column, a CI exit code, and a
  report-only tool that never edits a file.

## Install

```sh
git clone https://github.com/haiderstudio/csv-header-case-checker-cli.git
cd csv-header-case-checker-cli
```

There is nothing else to install: Python 3.10 or newer,
standard library only, no dependencies.

## Usage

Check one CSV file:

```sh
python3 src/csv_header_case_checker.py data.csv
```

A file whose headers are all snake_case passes:

```sh
$ python3 src/csv_header_case_checker.py examples/clean.csv
OK — 1 file(s) checked, every header is snake_case.
```

A file with headers in the wrong case fails, with the
line and column for each one:

```sh
$ python3 src/csv_header_case_checker.py examples/flagged.csv
FAIL examples/flagged.csv: line 1, column 1: header "UserID" is not snake_case (lowercase letters, digits and underscores, starting with a letter)
FAIL examples/flagged.csv: line 1, column 3: header "Last Name" is not snake_case (lowercase letters, digits and underscores, starting with a letter)
FAIL examples/flagged.csv: line 1, column 4: header "user-id" is not snake_case (lowercase letters, digits and underscores, starting with a letter)
Checked 1 file(s), 3 header(s) not snake_case in 1 file(s).
```

Check a whole folder (`.csv` files only):

```sh
$ python3 src/csv_header_case_checker.py examples/
FAIL examples/flagged.csv: line 1, column 1: header "UserID" is not snake_case (lowercase letters, digits and underscores, starting with a letter)
FAIL examples/flagged.csv: line 1, column 3: header "Last Name" is not snake_case (lowercase letters, digits and underscores, starting with a letter)
FAIL examples/flagged.csv: line 1, column 4: header "user-id" is not snake_case (lowercase letters, digits and underscores, starting with a letter)
Checked 3 file(s), 3 header(s) not snake_case in 1 file(s).
```

Check one document from standard input:

```sh
$ printf 'user_id,first_name\n1,Ada\n' | python3 src/csv_header_case_checker.py --stdin
OK — 1 file(s) checked, every header is snake_case.
```

Machine-readable output:

```sh
$ python3 src/csv_header_case_checker.py --json examples/flagged.csv
{
  "files": [
    {
      "path": "examples/flagged.csv",
      "findings": [
        {
          "line": 1,
          "column": 1,
          "header": "UserID",
          "reason": "header \"UserID\" is not snake_case (lowercase letters, digits and underscores, starting with a letter)"
        },
        {
          "line": 1,
          "column": 3,
          "header": "Last Name",
          "reason": "header \"Last Name\" is not snake_case (lowercase letters, digits and underscores, starting with a letter)"
        },
        {
          "line": 1,
          "column": 4,
          "header": "user-id",
          "reason": "header \"user-id\" is not snake_case (lowercase letters, digits and underscores, starting with a letter)"
        }
      ],
      "errors": []
    }
  ],
  "checked": 1,
  "findings": 3
}
```

Exit codes: 0 when every header is snake_case, 1
when any header or file error is found, 2 for a
usage error (a missing path, a bad flag, or no
`.csv` files found).

## Examples

One header in the wrong case is caught with its
column:

```sh
$ printf 'UserID,first_name\n1,Ada\n' > two.csv
$ python3 src/csv_header_case_checker.py two.csv
FAIL two.csv: line 1, column 1: header "UserID" is not snake_case (lowercase letters, digits and underscores, starting with a letter)
Checked 1 file(s), 1 header(s) not snake_case in 1 file(s).
```

A quoted header that holds a comma is one header,
not two — it is reported once, at its own column:

```sh
$ printf '"user_id","first,name"\n1,Ada\n' > quoted.csv
$ python3 src/csv_header_case_checker.py quoted.csv
FAIL quoted.csv: line 1, column 2: header "first,name" is not snake_case (lowercase letters, digits and underscores, starting with a letter)
Checked 1 file(s), 1 header(s) not snake_case in 1 file(s).
```

A header with a space after the comma fails too —
the name on disk holds the space:

```sh
$ printf 'user_id, first_name\n1,Ada\n' > spaced.csv
$ python3 src/csv_header_case_checker.py spaced.csv
FAIL spaced.csv: line 1, column 2: header " first_name" is not snake_case (lowercase letters, digits and underscores, starting with a letter)
Checked 1 file(s), 1 header(s) not snake_case in 1 file(s).
```

Headers with digits and single-letter headers pass
— `examples/edge.csv` holds both, and it passes:

```sh
$ python3 src/csv_header_case_checker.py examples/edge.csv
OK — 1 file(s) checked, every header is snake_case.
```

Run every bundled example at once with `sh
examples/run-example.sh` — the output is saved in
[examples/sample-output.md](examples/sample-output.md).

## How it is tested

```sh
python3 -m unittest discover -s tests
```

The tests cover headers (a plain bad header, several
bad headers in order, an uppercase header, a header
with a space, a header with a hyphen, a header
starting with a digit, a header starting with an
underscore, an empty header, a header with a
trailing underscore, a single-letter header, a header
with digits, a quoted header holding a comma, a
header with a leading space, a header with a
trailing space, a UTF-8 byte-order mark stripped,
an empty file reported as an error, a file with
only a blank line, data rows never checked, a
header row that spans lines through a quoted
newline), the CLI (exit 0/1/2, folder walking for
several CSV files, nested folders, `--no-recursive`,
`--exclude`, `.git` skipped, a direct file checked
whatever its name, duplicate paths checked once,
`--json` output, `--stdin`, bad flags, missing
paths, empty folders, `--version`, a non-UTF-8 file
reported, input files left unchanged, the tool run
from `/` and under a fake HOME), the bundled
examples (sample output compared against a fresh
run, and the README-quoted outputs checked against
it), and hygiene checks (no placeholder text, no
absolute paths, stdlib imports only, no network use
in the source, `.env` first in `.gitignore`, CI
file runs the test suite, README names the
neighbouring repos).

## Contributing

Small, focused improvements are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT — see [LICENSE](LICENSE).

## Original work

This tool was written from scratch for this repo. The
idea of checking a naming convention is not new, and
the snake_case rule is a common convention — but no
existing tool does this one job, checking local CSV
headers for snake_case as a tested command-line
gate, as the search above shows — and every line of
code here is original, built on nothing but Python's
standard library.
