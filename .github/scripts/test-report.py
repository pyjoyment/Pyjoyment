"""
The summary of the summaries of the jobs of a workflow, in Markdown, from the
JUnit XML that each job uploads as an artifact named "junit-" and the name of
the job, which download-artifact puts in a directory of the same name, with the
name of the workflow, Tests by default, as its title:

    PYTHONPATH=. python .github/scripts/test-report.py reports > report.md
    PYTHONPATH=. python .github/scripts/test-report.py reports jobs.tsv "Docker Smoke Test" > report.md

The file of the jobs has the name and the URL of each job of the run, separated
by a tab, as the API of the jobs of a run gives them, which link the jobs.

A row for each job, with its tests that passed, were skipped and failed, the
totals, and the tests that failed, with the name of their job. It starts with a
comment that marks it, with its title, so that the comment of the pull request
that has it is found and edited, instead of a new one for each run, and the
comments of two workflows are apart. The time is left out, as
the one of Pyjo.Prove is the sum of the scripts, which run at the same time,
and the one of pytest is the time of the run.
"""

import Pyjo.DOM

import os
import sys


# The tests that failed in the summary, at most, as a comment has at most 65536 characters
FAILED = 50


def main(directory: str, links: str | None = None, title: str = 'Tests') -> None:
    urls: dict[str, str] = {}
    if links is not None:
        with open(links, encoding='utf-8') as f:
            for line in f:
                name, _, url = line.rstrip('\n').partition('\t')
                urls[name] = url

    def link(job: str, text: str) -> str:
        return f'[{text}]({url})' if (url := urls.get(job)) else text

    jobs = []
    for name in sorted(os.listdir(directory)):
        path = os.path.join(directory, name)
        if not name.startswith('junit-') or not os.path.isdir(path):
            continue
        counts = {'tests': 0, 'failures': 0, 'errors': 0, 'skipped': 0}
        failed = []
        for file in sorted(os.listdir(path)):
            if not file.endswith('.xml'):
                continue
            with open(os.path.join(path, file), encoding='utf-8') as f:
                report = Pyjo.DOM.new(f.read())
            for suite in report.find('testsuite'):
                for key in counts:
                    counts[key] += int(suite.attr(key) or 0)
            for case in report.find('testcase'):
                if (problem := case.at('failure, error')) is not None:
                    message = (problem.attr('message') or problem.text or '').strip().split('\n')[0]
                    test = case.attr('name') or ''
                    script = case.attr('file') or case.attr('classname') or ''
                    # The message of Pyjo.Prove that only repeats the test point
                    if message == f'not ok {test}':
                        message = ''
                    failed.append((script, '' if test == script else test, message))
        jobs.append((name.removeprefix('junit-'), counts, failed))

    lines = [f'<!-- pyjo-prove-report: {title} -->', f'### {_cell(title)}', '']
    if not jobs:
        lines.append('No reports of the jobs.')
    else:
        lines += [
            '| Job | Tests | Passed ✅ | Skipped ⚠️ | Failed ❌ | | Log |',
            '| :--- | ---: | ---: | ---: | ---: | :---: | :--- |',
        ]
        totals = {'tests': 0, 'passed': 0, 'skipped': 0, 'failed': 0}
        for job, counts, _ in jobs:
            row = {
                'tests': counts['tests'],
                'passed': counts['tests'] - counts['failures'] - counts['errors'] - counts['skipped'],
                'skipped': counts['skipped'],
                'failed': counts['failures'] + counts['errors'],
            }
            for key in totals:
                totals[key] += row[key]
            status = '❌' if row['failed'] else '✅'
            lines.append(
                f'| {_cell(job)} | {row["tests"]} | {row["passed"]} | {row["skipped"]} | {row["failed"]} | {status} '
                f'| {link(job, urls[job].rstrip("/").rpartition("/")[2]) if job in urls else ""} |'
            )
        status = '❌' if totals['failed'] else '✅'
        lines.append(
            f'| **All** | **{totals["tests"]}** | **{totals["passed"]}** | **{totals["skipped"]}** '
            f'| **{totals["failed"]}** | {status} | |'
        )

        failed = [(job, *failure) for job, counts, failures in jobs for failure in failures]
        if failed:
            lines += ['', '| Job | Script | Test | Message |', '| :--- | :--- | :--- | :--- |']
            lines += [
                f'| {link(job, _cell(job))} | {" | ".join(_cell(value) for value in row)} |'
                for job, *row in failed[:FAILED]
            ]
            if len(failed) > FAILED:
                lines += ['', f'And {len(failed) - FAILED} more.']

    # The run of the workflow, with the summaries and the logs of the jobs
    if (server := os.environ.get('GITHUB_SERVER_URL')) and (repository := os.environ.get('GITHUB_REPOSITORY')):
        if run := os.environ.get('GITHUB_RUN_ID'):
            lines += ['', f'[The run of the workflow]({server}/{repository}/actions/runs/{run})']
    print('\n'.join(lines))


def _cell(text: str) -> str:
    # The text of a cell of a table of Markdown, with its pipes escaped
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('|', '\\|')


if __name__ == '__main__':
    main(*sys.argv[1:4])
