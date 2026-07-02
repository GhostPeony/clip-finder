"""Guard against drift between the two mirrored Supabase migration directories.

The Supabase CLI applies migrations from ``supabase/migrations`` while the
backend contract tests read ``backend/supabase/migrations``. Every migration
must exist in both directories with identical content.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CLI_MIGRATIONS = REPO_ROOT / "supabase" / "migrations"
BACKEND_MIGRATIONS = REPO_ROOT / "backend" / "supabase" / "migrations"


def _sql_files(directory: Path) -> dict[str, Path]:
    return {path.name: path for path in sorted(directory.glob("*.sql"))}


def test_migration_directories_contain_same_files():
    cli_files = set(_sql_files(CLI_MIGRATIONS))
    backend_files = set(_sql_files(BACKEND_MIGRATIONS))

    missing_from_backend = sorted(cli_files - backend_files)
    missing_from_cli = sorted(backend_files - cli_files)

    assert not missing_from_backend, (
        f"Migrations missing from backend/supabase/migrations: {missing_from_backend}"
    )
    assert not missing_from_cli, f"Migrations missing from supabase/migrations: {missing_from_cli}"


def test_mirrored_migrations_have_identical_content():
    cli_files = _sql_files(CLI_MIGRATIONS)
    backend_files = _sql_files(BACKEND_MIGRATIONS)

    diverged = [
        name
        for name, cli_path in cli_files.items()
        if name in backend_files
        and cli_path.read_text(encoding="utf-8") != backend_files[name].read_text(encoding="utf-8")
    ]

    assert not diverged, f"Migration content differs between directories: {diverged}"
