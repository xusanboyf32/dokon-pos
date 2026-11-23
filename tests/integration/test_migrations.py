"""Migratsiyalar tekshiruvi (docs/ENGINEERING.md, 8-bo'lim)."""

from alembic.config import Config as AlembicConfig

from alembic import command


def test_models_match_migrations(migrated_database: None, alembic_config: AlembicConfig) -> None:
    """Modelga o'zgarish kiritib, migratsiya yaratish unutilsa — shu test yiqiladi."""
    command.check(alembic_config)


def test_downgrade_to_base_and_upgrade_again(
    migrated_database: None, alembic_config: AlembicConfig
) -> None:
    """Har migratsiyaning downgrade() qismi ham ishlashi kerak."""
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")
