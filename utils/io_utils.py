import io
import pandas as pd
import requests
from typing import List
from tqdm import tqdm

ENA_URL = "https://www.ebi.ac.uk/ena/portal/api/search"

def read_metadata_tsv(file) -> pd.DataFrame:
    # file can be a Path or a Streamlit UploadedFile
    return pd.read_csv(file, sep="\t", low_memory=False)

def fetch_ena_metadata(sample_ids: List[str], result="read_run", fields="all") -> pd.DataFrame:
    frames = []
    for i, sid in enumerate(tqdm(sample_ids, desc="Fetching ENA metadata")):
        params = {
            "result": result,
            "query": f"sample_accession={sid}",
            "fields": fields,
            "format": "tsv",
        }
        r = requests.get(ENA_URL, params=params, timeout=60)
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text), sep="\t", low_memory=False)
        # If ENA returns empty, skip
        if df.shape[0] == 0:
            continue
        frames.append(df)
    if not frames:
        return pd.DataFrame()

    # Align columns just in case, then concat
    all_cols = sorted(set().union(*[f.columns for f in frames]))
    frames = [f.reindex(columns=all_cols) for f in frames]
    out = pd.concat(frames, ignore_index=True)
    return out
