# Token-saving: don't print a dot for each successful test, just print the summary at the end.
def pytest_report_teststatus(report, config):
    # `wasxfail` is left to pytest's own skipping plugin: this hook is firstresult and conftest
    # plugins run before the builtins, so claiming an xpassed report here would file it under
    # "passed" and lose the xpassed category entirely.
    if report.when == "call" and report.passed and not hasattr(report, "wasxfail"):
        # Second value is the 'short' representation (the dot).
        # Making it an empty string forces pytest to print absolutely nothing for a pass.
        return report.outcome, "", "PASSED"
