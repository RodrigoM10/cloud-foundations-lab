"""
Consulta analitica local con DuckDB.
Equivalente local de Athena sobre S3.

Athena real:
  - datos en s3://bucket/processed/
  - tabla definida en Glue Data Catalog
  - motor serverless, costo por datos escaneados

Aqui:
  - datos en data/processed/
  - DuckDB lee directamente el archivo JSON
  - mismo SQL, sin infraestructura adicional
"""

import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
json_file = ROOT / "data" / "processed" / "push_events.json"


def run_query(json_path: Path) -> list[tuple]:
    conn = duckdb.connect()
    try:
        return conn.execute(f"""
            SELECT repo, COUNT(*) AS pushes
            FROM read_json_auto('{json_path}')
            GROUP BY repo
            ORDER BY pushes DESC
            LIMIT 10
        """).fetchall()
    except duckdb.BinderException:
        return []


def main(json_path: Path = None) -> None:
    path = json_path or json_file

    if not path.exists():
        print(f"Archivo no encontrado: {path}")
        print()
        print("Generarlo con:")
        print("  python scripts/process_events.py")
        sys.exit(1)

    result = run_query(path)

    print("== Top repositorios por pushes ==")
    print(f"{'repo':<50} {'pushes':>6}")
    print("-" * 58)
    for repo, pushes in result:
        print(f"{repo:<50} {pushes:>6}")
    print()
    print(f"Archivo consultado: {path}")
    print()
    print("Equivalente en AWS:")
    print("  SELECT repo, COUNT(*) AS pushes")
    print("  FROM glue_catalog.processed.push_events")
    print("  GROUP BY repo ORDER BY pushes DESC LIMIT 10")
    print("  -- Athena cobra por datos escaneados, no por tiempo de ejecucion")


if __name__ == "__main__":
    main()
