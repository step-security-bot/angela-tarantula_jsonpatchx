# How to Contribute

Thanks for your interest in contributing to jsonpatchx! Here are a few general
guidelines on contributing and reporting bugs that we ask you to review.
Following these guidelines helps to communicate that you respect the time of the
contributors managing and developing this open source project. In return, they
should reciprocate that respect in addressing your issue, assessing changes, and
helping you finalize your pull requests. In that spirit of mutual respect, we
endeavor to review incoming issues and pull requests within 10 days, and will
close any lingering issues or pull requests after 60 days of inactivity.

Please note that all of your interactions in the project are subject to our
[Code of Conduct](/CODE_OF_CONDUCT.md). This includes creation of issues or pull
requests, commenting on issues or pull requests, and extends to all interactions
in any real-time space e.g., Slack, Discord, etc.

## Prerequisites

Install
[uv](https://docs.astral.sh/uv/getting-started/installation/#installing-uv)

```sh
python -m pip install --upgrade pip uv
```

## Installation

1. Clone the repository

   ```sh
   git clone https://github.com/angela-tarantula/jsonpatchx
   cd jsonpatchx
   ```

2. Initialize Git
   [submodules](https://git-scm.com/book/en/v2/Git-Tools-Submodules) (required
   for the external compliance suite)

   ```sh
   git submodule update --init
   ```

3. Install the dependencies

   ```sh
   uv sync
   ```

4. Install [prek](https://github.com/j178/prek) (pre-commit runner)

   ```sh
   uv tool install prek
   prek install
   ```

## Development

1. Run type checks with [mypy](https://www.mypy-lang.org/)

   ```sh
   uv run mypy .
   ```

2. Run tests with [pytest](https://docs.pytest.org/en/stable/)

   ```sh
   uv run pytest -v
   ```

3. View test coverage with
   [pytest-cov](https://github.com/pytest-dev/pytest-cov)

   ```sh
   uv run pytest --cov=jsonpatchx --cov-report=html
   open htmlcov/index.html
   ```

4. Lint with [ruff](https://docs.astral.sh/ruff/)

   ```sh
   uv run ruff format
   ```

## Prek quick reference

- Run all configured hooks manually:

  ```sh
  prek run --all-files
  ```

- List available hook IDs:

  ```sh
  prek list
  ```

- Run one specific hook:

  ```sh
  prek run checkov --all-files
  ```

- Skip one hook for one commit:

  ```sh
  PREK_SKIP=checkov git commit -m "message"
  ```

- Skip multiple hooks for one commit:

  ```sh
  PREK_SKIP=checkov,openapi git commit -m "message"
  ```

- Skip all hooks for one commit:

  ```sh
  git commit --no-verify -m "message"
  ```

CI still runs required checks on pushes and pull requests, so skipping local
hooks does not bypass CI requirements.

## Reporting Issues

Before reporting a new issue, please ensure that the issue was not already
reported or fixed by searching through our
[issues list](https://github.com/angela-tarantula/jsonpatchx/issues).

When creating a new issue, please be sure to include a **title and clear
description**, as much relevant information as possible, and, if possible, a
test case.

**If you discover a security bug, please do not report it through GitHub.
Instead, please see security procedures in [SECURITY.md](/SECURITY.md).**

## Sending Pull Requests

Before sending a new pull request, take a look at existing pull requests and
issues to see if the proposed change or fix has been discussed in the past, or
if the change was already implemented but not yet released.

We expect new pull requests to include tests for any affected behavior, and, as
we follow semantic versioning, we may reserve breaking changes until the next
major version release.

## Other Ways to Contribute

We welcome anyone that wants to contribute to jsonpatchx to triage and reply to
open issues to help troubleshoot and fix existing bugs. Here is what you can do:

- Help ensure that existing issues follows the recommendations from the
  _[Reporting Issues](#reporting-issues)_ section, providing feedback to the
  issue's author on what might be missing.
- Review and update the existing content of our
  [Wiki](https://github.com/angela-tarantula/jsonpatchx/wiki) with up-to-date
  instructions and code samples.
- Review existing pull requests, and testing patches against real existing
  applications that use jsonpatchx.
- Write a test, or add a missing test case to an existing test.

Thanks again for your interest on contributing to jsonpatchx!

:heart:
