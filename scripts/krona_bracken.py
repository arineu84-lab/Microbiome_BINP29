#!/usr/bin/env python
# krona_bracken.py 

import os
import sys
import subprocess
import pandas as pd
import shlex
from pathlib import Path

results_dir = Path("results")
kraken2_dir = results_dir / "kraken2"
krona_tsv_dir = results_dir / "krona"
krona_html_dir = results_dir / "krona_html"
bracken_dir = results_dir / "bracken"
summary_dir = results_dir / "summary"
lineage_dir = results_dir / "lineage"

levels = ["D", "P", "C", "O", "F", "G"]  

use_taxonkit = True
taxonkit_db = os.environ.get("TAXONKIT_DB", "")

def run_cmd(cmd_list, env=None, input_bytes=None, capture_output=False):
    print(f"[CMD] {' '.join(shlex.quote(str(c)) for c in cmd_list)}")
    return subprocess.run(
        [str(c) for c in cmd_list],
        check=True,
        env=env,
        input=input_bytes,
        capture_output=capture_output)

def ensure_dirs():
    for d in [krona_html_dir, summary_dir, lineage_dir]:
        d.mkdir(parents=True, exist_ok=True)

def which(prog):
    try:
        subprocess.run(["which", prog], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except subprocess.CalledProcessError:
        return False

def check_krona_installed():
    if not which("ktImportTaxonomy"):
        raise RuntimeError("ERROR: ktImportTaxonomy not found. Install via:\n  conda install -c bioconda krona")

def check_taxonkit_installed():
    if use_taxonkit and not which("taxonkit"):
        raise RuntimeError("ERROR: taxonkit not found. Install via:\n  conda install -c bioconda taxonkit")
    if use_taxonkit:
        print(f"[INFO] taxonkit db: {taxonkit_db}")

def krona_tsv_path(sample: str) -> Path:
    return krona_tsv_dir / f"{sample}_krona.tsv"

def find_samples_from_krona_tsv() -> list[str]:
    return sorted([p.stem.replace("_krona", "") for p in krona_tsv_dir.glob("*_krona.tsv")])

def find_samples_from_kraken() -> list[str]:
    return sorted([p.stem for p in kraken2_dir.glob("*.kraken")])

def ensure_krona_tsv_from_kraken(sample: str) -> Path | None:
    """Generate TSV (col1=readID, col2=taxID) from Kraken output if missing."""
    tsv = krona_tsv_path(sample)
    if tsv.exists():
        return tsv

    kraken_file = kraken2_dir / f"{sample}.kraken"
    if not kraken_file.exists():
        print(f"[WARN] Kraken output missing for sample {sample}")
        return None

    krona_tsv_dir.mkdir(parents=True, exist_ok=True)
    cmd = f"cut -f2,3 {shlex.quote(str(kraken_file))} | grep -v '^#' > {shlex.quote(str(tsv))}"
    run_cmd(["bash", "-c", cmd])
    return tsv

def assert_file_nonempty(path: Path, label: str):
    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeError(f"ERROR: Expected {label} not created or empty: {path}")

# building Krona html files 
def build_per_sample_krona(sample: str) -> Path | None:
    tsv = ensure_krona_tsv_from_kraken(sample)
    if not tsv:
        return None

    out_html = krona_html_dir / f"{sample}.krona.html"
    run_cmd([
        "ktImportTaxonomy",
        "-q", "1",  # col1 query/read ID
        "-t", "2",  # col2 taxID
        str(tsv),
        "-o", str(out_html)])

    assert_file_nonempty(out_html, f"krona html for {sample}")
    return out_html

def build_combined_krona(samples: list[str]) -> Path | None:
    if len(samples) <= 1:
        print("[INFO] only one sample → skipping combined krona")
        return None

    out_html = krona_html_dir / "all_samples.krona.html"
    cmd = ["ktImportTaxonomy", "-q", "1", "-t", "2", "-o", str(out_html)]
    for s in samples:
        tsv = krona_tsv_path(s)
        if tsv.exists():
            cmd.append(f"{tsv},{s}")
        else:
            print(f"[WARN] missing TSV for {s}")

    run_cmd(cmd)
    assert_file_nonempty(out_html, "combined krona html")
    return out_html

# TaxonKit lineage
def taxonkit_lineage_for_taxids(unique_taxids: list[str]) -> dict[str, str]:
    if not unique_taxids:
        return {}
    txt = "\n".join(unique_taxids).encode()
    env = os.environ.copy()
    if taxonkit_db:
        env["TAXONKIT_DB"] = taxonkit_db

    proc = run_cmd(["taxonkit", "lineage"], env=env, input_bytes=txt, capture_output=True)
    mapping = {}
    for line in proc.stdout.decode().splitlines():
        parts = line.rstrip("\n").split("\t")
        mapping[parts[0]] = parts[1] if len(parts) > 1 else "NA"
    return mapping

# Bracken summaries and lineage
def parse_sample_and_level(path: Path) -> tuple[str | None, str | None]:
    base = path.name
    if not base.endswith(".bracken.tsv"):
        return None, None
    core = base[:-12]  # drop '.bracken.tsv'
    sample, level = core.rsplit("_", 1)
    if level not in levels:
        return None, None
    return sample, level

def load_bracken_table(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep="\t", dtype={"taxonomy_id": str})

def build_bracken_summaries_with_lineage():
    files = list(bracken_dir.glob("*.bracken.tsv"))
    long_rows: list[pd.DataFrame] = []

    for f in files:
        sample, level = parse_sample_and_level(f)
        if sample is None:
            continue
        df = load_bracken_table(f)
        df["sample"] = sample
        df["level"] = level
        long_rows.append(df)

    if not long_rows:
        print("[WARN] no bracken files found")
        return

    long_df = pd.concat(long_rows, ignore_index=True)

    if use_taxonkit:
        taxids = sorted(long_df["taxonomy_id"].dropna().unique().tolist())
        mapping = taxonkit_lineage_for_taxids(taxids)
        long_df["lineage"] = long_df["taxonomy_id"].map(mapping).fillna("NA")

    summary_dir.mkdir(parents=True, exist_ok=True)
    out_long = summary_dir / "bracken_long_with_lineage.tsv"
    long_df.to_csv(out_long, sep="\t", index=False)
    print(f"[OK] wrote lineage table: {out_long}")

# main script
def main():
    print("=== krona + bracken summary ===")
    if not results_dir.exists():
        print("[ERR] This script expects to be run from the project root containing 'results/'.")
        print("      Current working directory:", Path.cwd())
        sys.exit(1)

    ensure_dirs()
    check_krona_installed()
    if use_taxonkit:
        check_taxonkit_installed()

    print("[DEBUG] cwd:", os.getcwd())
    print("[DEBUG] krona html dir:", krona_html_dir.resolve())
    print("[DEBUG] writable:", os.access(krona_html_dir, os.W_OK))

    samples = find_samples_from_krona_tsv()
    if not samples:
        print("[INFO] No Krona TSVs found — falling back to Kraken outputs to derive samples.")
        samples = find_samples_from_kraken()

    if not samples:
        print("[ERROR] No samples found in either:", krona_tsv_dir, "or", kraken2_dir)
        return

# Restrict to selected samples if available (analysis/selected_samples.tsv)
    selected_tsv = Path("analysis") / "selected_samples.tsv"
    if selected_tsv.exists():
        try:
            sel = pd.read_csv(selected_tsv, sep="\t", dtype=str)
            if "run_accession" in sel.columns:
                sel_ids = set(sel["run_accession"].dropna().astype(str).str.strip())
                before_n = len(samples)
                samples = [s for s in samples if s in sel_ids]
                print(f"[INFO] restricting to selected samples ({len(samples)}/{before_n})")
            else:
                print("[WARN] 'run_accession' column missing in selected_samples.tsv")
        except Exception as e:
            print(f"[WARN] could not read {selected_tsv}: {e}")
    else:
        print(f"[WARN] selected samples file not found: {selected_tsv} (continuing with all detected samples)")

    if not samples:
        print("[ERROR] no samples remaining after filtering")
        return

    # Build per-sample Krona
    built: list[str] = []
    for s in samples:
        try:
            html = build_per_sample_krona(s)
            if html:
                print(f"[OK] krona html: {html}")
                built.append(s)
        except subprocess.CalledProcessError as e:
            print(f"[ERR] krona failed for {s}: {e}")
        except Exception as e:
            print(f"[ERR] {e}")

    # Combined Krona
    try:
        combined = build_combined_krona(built)
        if combined:
            print(f"[OK] combined krona: {combined}")
    except subprocess.CalledProcessError as e:
        print(f"[ERR] combined krona failed: {e}")
    except Exception as e:
        print(f"[ERR] {e}")

    # Bracken lineage summary
    try:
        build_bracken_summaries_with_lineage()
    except Exception as e:
        print(f"[WARN] bracken lineage step failed: {e}")

    print("=== done ===")

if __name__ == "__main__":
    main()