# Token-saving: don't print a dot for each successful test, just print the summary at the end.
def pytest_report_teststatus(report, config):
    if report.when == "call" and report.passed:
        # Second value is the 'short' representation (the dot).
        # Making it an empty string forces pytest to print absolutely nothing for a pass.
        return report.outcome, "", "PASSED"
