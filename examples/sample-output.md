== examples/clean.csv ==
OK — 1 file(s) checked, every header is snake_case.

== examples/flagged.csv ==
FAIL examples/flagged.csv: line 1, column 1: header "UserID" is not snake_case (lowercase letters, digits and underscores, starting with a letter)
FAIL examples/flagged.csv: line 1, column 3: header "Last Name" is not snake_case (lowercase letters, digits and underscores, starting with a letter)
FAIL examples/flagged.csv: line 1, column 4: header "user-id" is not snake_case (lowercase letters, digits and underscores, starting with a letter)
Checked 1 file(s), 3 header(s) not snake_case in 1 file(s).

== examples/edge.csv ==
OK — 1 file(s) checked, every header is snake_case.

== examples/ : the whole folder ==
FAIL examples/flagged.csv: line 1, column 1: header "UserID" is not snake_case (lowercase letters, digits and underscores, starting with a letter)
FAIL examples/flagged.csv: line 1, column 3: header "Last Name" is not snake_case (lowercase letters, digits and underscores, starting with a letter)
FAIL examples/flagged.csv: line 1, column 4: header "user-id" is not snake_case (lowercase letters, digits and underscores, starting with a letter)
Checked 3 file(s), 3 header(s) not snake_case in 1 file(s).
