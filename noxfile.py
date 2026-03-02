"""Nox file for automation."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

import nox

nox.options.default_venv_backend = "uv"

python_versions = (
    (Path(__file__).parent / ".python-versions").read_text().strip().split("\n")
)
python_version = (Path(__file__).parent / ".python-version").read_text().strip()


def install(
    session: nox.Session,
    *,
    groups: Iterable[str],
    root: bool = True,
    extras: bool = False,
) -> None:
    """Install the dependency groups using uv."""
    command = [
        "uv",
        "sync",
        "--frozen",
        "--no-default-groups",
        f"--python={session.virtualenv.location}",
        *(f"--{'group' if root else 'only-group'}={group}" for group in groups),
    ]
    if extras:
        command.append("--all-extras")

    session.run_install(
        *command, env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location}
    )


@nox.session(python=python_version)
def pre_commit(session: nox.Session) -> None:
    """Run pre-commit."""
    install(session, groups=["pre-commit"], root=False)
    session.run(
        "pre-commit",
        "run",
        "--all-files",
        "--show-diff-on-failure",
        "--hook-stage=manual",
    )


@nox.session(python=python_version)
def lock_dependencies(session: nox.Session) -> None:
    """Lock the dependencies."""
    session.run("uv", "lock")


@nox.session(python=python_version)
def lint_files(session: nox.Session) -> None:
    """Lint and fix files."""
    install(session, groups=["linting"], root=False)
    session.run("ruff", "check", ".", "--fix")


@nox.session(python=python_version)
def format_files(session: nox.Session) -> None:
    """Format files."""
    install(session, groups=["linting"], root=False)
    session.run("ruff", "format")


@nox.session(python=python_versions)
def type_check_code(session: nox.Session) -> None:
    """Type-check code."""
    install(session, groups=["typing"], root=True, extras=True)
    # mypy --install-types
    session.run("mypy")


@nox.session(python=python_versions)
def test_code(session: nox.Session) -> None:
    """Test code."""
    install(session, groups=["tests"], root=True, extras=True)
    session.run("pytest")


@nox.session(python=python_version)
def i18n_extract(session: nox.Session) -> None:
    """Extract translatable strings to POT file."""
    install(session, groups=["i18n"], root=True)
    version = session.run(
        "python",
        "-c",
        "import tomllib, pathlib; "
        "print(tomllib.loads(pathlib.Path('pyproject.toml').read_text())['project']['version'])",
        silent=True,
    ).strip()  # type: ignore[union-attr]
    session.run(
        "pybabel",
        "extract",
        "--keywords=t",
        "--output=src/ogdrb/locales/ogdrb.pot",
        "--project=ogdrb",
        f"--version={version}",
        "--copyright-holder=Micael Jarniac",
        "--msgid-bugs-address=https://github.com/MicaelJarniac/ogdrb/issues",
        "src/ogdrb/",
    )


@nox.session(python=python_version, default=False)
def i18n_init(session: nox.Session) -> None:
    """Initialize a new language catalog.  Pass the locale code as a positional arg."""
    install(session, groups=["i18n"], root=True)
    locale = session.posargs[0] if session.posargs else "pt_BR"
    session.run(
        "pybabel",
        "init",
        "-i",
        "src/ogdrb/locales/ogdrb.pot",
        "-d",
        "src/ogdrb/locales",
        "-l",
        locale,
        "-D",
        "ogdrb",
    )


@nox.session(python=python_version)
def i18n_update(session: nox.Session) -> None:
    """Update existing catalogs from the POT template."""
    install(session, groups=["i18n"], root=True)
    session.run(
        "pybabel",
        "update",
        "-i",
        "src/ogdrb/locales/ogdrb.pot",
        "-d",
        "src/ogdrb/locales",
        "-D",
        "ogdrb",
    )


@nox.session(python=python_version)
def i18n_compile(session: nox.Session) -> None:
    """Compile message catalogs to MO files."""
    install(session, groups=["i18n"], root=True)
    session.run(
        "pybabel",
        "compile",
        "-d",
        "src/ogdrb/locales",
        "-D",
        "ogdrb",
    )
