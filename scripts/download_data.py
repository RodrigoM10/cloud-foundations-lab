"""
Descarga los datasets completos usados en el módulo.

Uso:
    python scripts/download_data.py                  # descarga todo
    python scripts/download_data.py --olist          # solo Olist
    python scripts/download_data.py --github         # solo GitHub Archive
    python scripts/download_data.py --github-date 2024-01-15 --github-hour 14

Requisitos:
    pip install kaggle
    Crear token en https://www.kaggle.com/settings → API → Create New Token
    Guardar en ~/.kaggle/kaggle.json
"""

import argparse
import gzip
import json
import shutil
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW  = ROOT / "data" / "raw"


def download_olist():
    dest = RAW / "olist"
    dest.mkdir(parents=True, exist_ok=True)
    print("Descargando Olist Brazilian E-Commerce desde Kaggle...")
    print("Requiere kaggle CLI configurado: https://www.kaggle.com/settings → API")
    subprocess.run(
        ["kaggle", "datasets", "download",
         "-d", "olistbr/brazilian-ecommerce",
         "-p", str(dest), "--unzip"],
        check=True,
    )
    print(f"Olist descargado en {dest}/")


def download_github(date="2024-01-15", hour=14):
    dest = RAW / "events"
    dest.mkdir(parents=True, exist_ok=True)
    filename = f"{date}-{hour}.json.gz"
    url = f"https://data.gharchive.org/{filename}"
    out_gz   = dest / filename
    out_json = dest / filename.replace(".gz", "")

    print(f"Descargando GitHub Archive: {url}")
    urllib.request.urlretrieve(url, out_gz)

    print(f"Descomprimiendo → {out_json}")
    with gzip.open(out_gz, "rb") as f_in, open(out_json, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    out_gz.unlink()
    print(f"GitHub Archive descargado: {out_json}")
    print(f"  Eventos: {sum(1 for _ in open(out_json))}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--olist",        action="store_true")
    parser.add_argument("--github",       action="store_true")
    parser.add_argument("--github-date",  default="2024-01-15")
    parser.add_argument("--github-hour",  type=int, default=14)
    args = parser.parse_args()

    run_all = not args.olist and not args.github
    if args.olist  or run_all: download_olist()
    if args.github or run_all: download_github(args.github_date, args.github_hour)
