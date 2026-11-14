"""Write SQL DDL for every table (Postgres + SQLite) into backend/migrations/. Usage: python -m scripts.export_schema"""
from pathlib import Path

from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.schema import CreateIndex, CreateTable

from app import models, models_v2  # noqa: F401  (register all tables)
from app.db import Base

out = Path(__file__).resolve().parent.parent / "migrations"
out.mkdir(exist_ok=True)
for name, dialect in (("postgres", postgresql.dialect()), ("sqlite", sqlite.dialect())):
    parts = [f"-- EduNest 2.0 schema ({name}). Generated from SQLAlchemy models: python -m scripts.export_schema\n"]
    if name == "postgres":
        parts.append("-- Optional vector search: CREATE EXTENSION IF NOT EXISTS vector;  (see README: pgvector)\n")
    for t in Base.metadata.sorted_tables:
        parts.append(str(CreateTable(t).compile(dialect=dialect)).strip() + ";\n")
        for ix in sorted(t.indexes, key=lambda i: i.name or ""):
            parts.append(str(CreateIndex(ix).compile(dialect=dialect)).strip() + ";\n")
    (out / f"001_initial_{name}.sql").write_text("\n".join(parts))
    print("wrote", out / f"001_initial_{name}.sql", len(Base.metadata.sorted_tables), "tables")
