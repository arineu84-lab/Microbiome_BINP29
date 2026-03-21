# utils/krona_utils.py
from pathlib import Path

def krona_html_for_sample(sample_id: str, krona_dir: Path) -> Path | None:
    candidates = [
        krona_dir / f"{sample_id}_krona.html",
        krona_dir / f"{sample_id}.krona.html",
        krona_dir / f"{sample_id}.html",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None