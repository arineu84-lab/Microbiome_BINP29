#!/usr/bin/env python
# kraken2.py 

import os
import glob
import subprocess
from pathlib import Path
import shlex
import pandas as pd

database = "db/silva16s"
threads = 8
input_dir = "raw_data/fastq"
readlength = 150

# Restrict to selected_samples file
selected_tsv = "raw_data/selected_samples.tsv"
selected_columns = "run_accession"

# Select taxonomic levels for Bracken
tax_levels = ["D", "P", "C", "O", "F", "G", "S"]
# Domain, Phylum, Class, Order, Family, Genus, Species

def run_cmd(cmd_list):
    print(f"\n[CMD] {' '.join(shlex.quote(str(c)) for c in cmd_list)}")
    subprocess.run([str(c) for c in cmd_list], check=True)

def ensure_dirs(): # Create output directories
    Path("results/kraken2").mkdir(parents=True, exist_ok=True)
    Path("results/bracken").mkdir(parents=True, exist_ok=True)
    Path("results/krona").mkdir(parents=True, exist_ok=True)

def load_selected_ids(tsv_path: str, col: str) -> set: # Load selected run_accession IDs 
    if not Path(tsv_path).exists():
        raise SystemExit(f"[ERROR] Selected samples file not found: {tsv_path}")
    df = pd.read_csv(tsv_path, sep="\t", dtype=str)
    if col not in df.columns:
        raise SystemExit(f"[ERROR] Column '{col}' not found in {tsv_path}. "
                         f"Columns present: {list(df.columns)}")
    ids = set(df[col].dropna().astype(str).str.strip().tolist())
    if not ids:
        raise SystemExit(f"[ERROR] No IDs found in {tsv_path}:{col}")
    print(f"[INFO] Loaded {len(ids)} selected IDs from {tsv_path}")
    return ids

def detect_fastqs_for_selected(fastq_dir: str, selected_ids: set):
    paired = []
    single = []
    found_ids = set()
    for sid in sorted(selected_ids): # For each selected ID, try to discover files
        r1 = os.path.join(fastq_dir, f"{sid}_1.fastq.gz")
        r2 = os.path.join(fastq_dir, f"{sid}_2.fastq.gz")

        if os.path.exists(r1) and os.path.exists(r2):
            paired.append((r1, r2, sid))
            found_ids.add(sid)
            continue

        se = os.path.join(fastq_dir, f"{sid}.fastq.gz")
        if os.path.exists(se):
            single.append((se, sid))
            found_ids.add(sid)
            continue

        # in case of single-end as _R1 or _1 
        alt_r1 = os.path.join(fastq_dir, f"{sid}_R1.fastq.gz")
        if os.path.exists(alt_r1) and not os.path.exists(r2):
            single.append((alt_r1, sid)) # treat as single
            found_ids.add(sid)
            continue

        # glob all files starting with sid
        globbed = sorted(glob.glob(os.path.join(fastq_dir, f"{sid}*.fastq.gz")))
        if globbed:
            g_r1 = [p for p in globbed if p.endswith("_1.fastq.gz")]
            g_r2 = [p for p in globbed if p.endswith("_2.fastq.gz")]
            if g_r1 and g_r2:
                r1_guess = g_r1[0]
                r2_guess = r1_guess.replace("_1.fastq.gz", "_2.fastq.gz")
                if r2_guess in globbed:
                    paired.append((r1_guess, r2_guess, sid))
                    found_ids.add(sid)
                    continue
            if len(globbed) == 1:
                single.append((globbed[0], sid))
                found_ids.add(sid)
                continue

    missing = selected_ids - found_ids
    return paired, single, missing

# Main workflow
def main():
    print("=== Kraken2 + Bracken + Krona (ONLY selected samples) ===")
    ensure_dirs()

    selected_ids = load_selected_ids(selected_tsv, selected_columns) # Load selected IDs

    paired, single, missing = detect_fastqs_for_selected(input_dir, selected_ids) # Detect fastq files for selected IDs
    print(f"[INFO] Selected IDs: {len(selected_ids)}  |  Paired: {len(paired)}  Single: {len(single)}  Missing: {len(missing)}")
    if missing:
        print("[WARN] FASTQs not found for the following selected IDs:")
        for m in sorted(missing):
            print(f"  - {m}")

    if not paired and not single:
        print("[ERROR] No FASTQ files found for the selected IDs. Aborting.")
        return

    # Process paired-end 
    for r1, r2, sample in paired:
        print(f"\n=== Processing PE sample: {sample} ===")

        kraken_report = f"results/kraken2/{sample}.report"
        kraken_output = f"results/kraken2/{sample}.kraken"

        # Kraken2 
        run_cmd(["kraken2",
            "--db", database,
            "--threads", str(threads),
            "--paired",
            "--report", kraken_report,
            "--output", kraken_output,
            r1, r2])

        # Bracken for each level
        for level in tax_levels:
            out_tsv = f"results/bracken/{sample}_{level}.bracken.tsv"
            print(f"[INFO] Bracken level: {level}")
            try:
                run_cmd(["bracken",
                    "-d", database,
                    "-i", kraken_report,
                    "-o", out_tsv,
                    "-r", str(readlength),
                    "-l", level,
                    "-t", "1"])
            except subprocess.CalledProcessError:
                print(f"[WARN] Bracken failed for level {level} in sample {sample}. Skipping.")

        #  create Krona.tsv (readID \t taxID from kraken output)
        krona_tsv = f"results/krona/{sample}_krona.tsv"
        run_cmd(["bash", "-c",
            f"cut -f2,3 {shlex.quote(kraken_output)} | grep -v '^#' > {shlex.quote(krona_tsv)}"])

   
    # Process single-end
    for fq, sample in single:
        print(f"\n=== Processing SE sample: {sample} ===")

        kraken_report = f"results/kraken2/{sample}.report"
        kraken_output = f"results/kraken2/{sample}.kraken"

        # Kraken2 (single-end)
        run_cmd(["kraken2",
            "--db", database,
            "--threads", str(threads),
            "--report", kraken_report,
            "--output", kraken_output,
            fq])

        # Bracken for each level
        for level in tax_levels:
            out_tsv = f"results/bracken/{sample}_{level}.bracken.tsv"
            print(f"[INFO] Bracken level: {level}")
            try:
                run_cmd(["bracken",
                    "-d", database,
                    "-i", kraken_report,
                    "-o", out_tsv,
                    "-r", str(readlength),
                    "-l", level,
                    "-t", "1"])
            except subprocess.CalledProcessError:
                print(f"[WARN] Bracken failed for level {level} in sample {sample}. Skipping.")

        # create Krona.tsv (readID \t taxID from kraken output)
        krona_tsv = f"results/krona/{sample}_krona.tsv"
        run_cmd(["bash", "-c",
            f"cut -f2,3 {shlex.quote(kraken_output)} | grep -v '^#' > {shlex.quote(krona_tsv)}"])

    print("\n=== Done ===")
    print("Kraken2 results done")
    print("Bracken all levels done")
    print("Krona-ready TSVtsv files done")
    if missing:
        print(f"[NOTE] {len(missing)} selected IDs had no FASTQs — see above warnings.")

if __name__ == "__main__":
    main()