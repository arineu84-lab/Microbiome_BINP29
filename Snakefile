# usage:
#   conda activate snakemake
#   snakemake -j 8 --use-conda --rerun-incomplete

import os
sample_ids   = "raw_data/NCBI.skin.metagenome.sampleID.txt"

# natural earth → geojson 
ne_zip       = "raw_data/ne_110m_admin_0_countries.zip"
ne_dir       = "raw_data/ne_110m_admin_0_countries"
ne_geojs     = "data/ne_countries.geojson"

# metadata & filtered tables
metadata_tsv = "raw_data/metadata.tsv"
filtered_tsv = "raw_data/filtered_meta.tsv"
selected_tsv = "raw_data/selected_samples.tsv"

# results
plots_dir    = "plots"
fastq_dir    = "raw_data/fastq"
db_dir       = "db/silva16s"
map_html     = "results/map/interactive_map.html"
krona_html   = "results/krona_html"


rule all:
    input:
        f"{plots_dir}/country_distribution.png",
        f"{plots_dir}/country_worldmap.png",
        map_html


rule download_natural_earth:
    output: ne_zip
    conda: "envs/nettools.yaml"
    shell:
        r"""
        set -euo pipefail
        mkdir -p raw_data
        wget -q -O {output} https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip
        """

rule extract_natural_earth:
    input: ne_zip
    output: directory(ne_dir)
    conda: "envs/nettools.yaml"
    shell:
        r"""
        set -euo pipefail
        unzip -o {input} -d raw_data
        """

rule ne_to_geojson:
    input: ne_dir              
    output: ne_geojs
    conda: "envs/geo.yaml"
    shell:
        r"""
        python - << 'PY'
import geopandas as gpd, glob, os, sys
indir = {input!r}
files = glob.glob(os.path.join(indir, '*.shp'))
if not files:
    sys.exit("no shapefile found in natural earth directory: " + indir)
gdf = gpd.read_file(files[0])
os.makedirs(os.path.dirname({output!r}), exist_ok=True)
gdf.to_file({output!r}, driver='GeoJSON')
print("wrote", {output!r})
PY
        """


rule fetch_metadata:
    input: sample_ids
    output: metadata_tsv
    conda: "envs/nettools.yaml"
    shell:
        r"""
        set -euo pipefail
        : > {output}
        first=1
        while read id; do
            echo "[info] fetching metadata for $id"
            if [ $first -eq 1 ]; then
                curl -s "https://www.ebi.ac.uk/ena/portal/api/search?result=read_run&query=sample_accession=${id}&fields=all&format=tsv" >> {output}
                first=0
            else
                curl -s "https://www.ebi.ac.uk/ena/portal/api/search?result=read_run&query=sample_accession=${id}&fields=all&format=tsv" | tail -n +2 >> {output}
            fi
            sleep 0.2
        done < {input}
        """

rule filter_columns:
    input: metadata_tsv
    output: filtered_tsv
    conda: "envs/geo.yaml"
    shell:
        r"""
        python scripts/filter_columns.py
        """


rule country_distribution:
    input: filtered_tsv, ne_geojs
    output: f"{plots_dir}/country_distribution.png"
    conda: "envs/geo.yaml"
    shell:
        r"""
        mkdir -p {plots_dir}
        python scripts/country_distribution.py
        """

rule sequence_type_map:
    input: filtered_tsv, ne_geojs
    output: f"{plots_dir}/country_worldmap.png"
    conda: "envs/geo.yaml"
    shell:
        r"""
        mkdir -p {plots_dir}
        python scripts/sequence_type.py
        """


rule select_samples:
    input: filtered_tsv
    output: selected_tsv
    conda: "envs/geo.yaml"
    shell:
        r"""
        python scripts/select_samples.py \
          --country denmark --n 3 --strategy amplicon \
          --fallback germany,austria,finland,sweden,norway
        """

rule pull_fastq:
    input: selected_tsv, metadata_tsv
    output: touch(f"{fastq_dir}/.done")
    conda: "envs/nettools.yaml"
    shell:
        r"""
        mkdir -p {fastq_dir}
        bash scripts/pull_fastq.sh
        touch {output}
        """


rule build_kraken_silva:
    output: touch(f"{db_dir}/.built")
    conda: "envs/kraken.yaml"
    threads: 8
    shell:
        r"""
        set -euo pipefail
        mkdir -p {db_dir}
        kraken2-build --special silva --db {db_dir} --threads {threads}
        kraken2-build --build   --db {db_dir} --threads {threads}
        touch {output}
        """

rule bracken_build:
    input: f"{db_dir}/.built"
    output: touch(f"{db_dir}/.bracken_kmer_150.done")
    conda: "envs/kraken.yaml"
    threads: 8
    shell:
        r"""
        set -euo pipefail
        bracken-build -d {db_dir} -t {threads} -k 35 -l 150
        touch {output}
        """


rule kraken2_and_krona_prep:
    input:
        fastqs        = f"{fastq_dir}/.done",
        db            = f"{db_dir}/.built",
        bracken_kmer  = f"{db_dir}/.bracken_kmer_150.done",
        selected      = selected_tsv
    output:
        touch("results/.profile_done")
    conda: "envs/kraken.yaml"
    threads: 8
    shell:
        r"""
        python scripts/kraken2.py
        touch {output}
        """

rule krona_html:
    input: "results/.profile_done", "results/.krona_taxonomy_ready"
    output: touch(f"{krona_html}/.done")
    conda: "envs/kraken.yaml"
    shell:
        r"""
        set -euo pipefail
        python scripts/krona_bracken.py

        # verify at least one krona html exists before touching .done
        if ! compgen -G "results/krona_html/*.krona.html" > /dev/null; then
          echo "[error] krona htmls were not generated. check scripts/krona_bracken.py output." >&2
          exit 1
        fi
        touch {output}
        """
rule krona_update_taxonomy:
    output: touch("results/.krona_taxonomy_ready")
    conda: "envs/kraken.yaml"
    shell:
        r"""
        set -euo pipefail
        ktUpdateTaxonomy.sh
        touch {output}
        """

rule krona_lineage:
    input: f"{krona_html}/.done"
    output: touch("results/lineage/.done")
    conda: "envs/kraken.yaml"
    shell:
        r"""
        set -euo pipefail
        shopt -s nullglob
        mkdir -p results/lineage
        for f in results/krona/*_krona.tsv; do
          s=$(basename "$f" _krona.tsv)
          echo "[lineage] $s"
          paste <(cut -f1 "$f") <(cut -f2 "$f" | taxonkit lineage | cut -f2-) \
            > "results/lineage/${{s}}_lineage.tsv"
        done
        # ensure at least one lineage file exists
        if ! compgen -G "results/lineage/*_lineage.tsv" > /dev/null; then
          echo "[error] no lineage files produced" >&2
          exit 1
        fi
        touch {output}
        """


rule interactive_map:
    input:
        filtered_tsv,
        selected_tsv,
        ne_geojs,
        f"{krona_html}/.done",
        "results/lineage/.done"
    output: map_html
    conda: "envs/geo.yaml"
    shell:
        r"""
        python scripts/interactive_map.py
        """