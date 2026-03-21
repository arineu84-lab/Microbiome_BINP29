#!/usr/bin/env bash
set -euo pipefail

INPUT_FILE="raw_data/NCBI.skin.metagenome.sampleID.txt"
OUTPUT_FILE="raw_data/metadata.tsv"
CHUNK_SIZE=1000           
FIELDS="all"               
RESULT="read_run"
BASE_URL="https://www.ebi.ac.uk/ena/portal/api/search"

mkdir -p raw_data
: > "$OUTPUT_FILE"      

# Read all IDs into an array
mapfile -t IDS < "$INPUT_FILE"
TOTAL=${#IDS[@]}
if [[ $TOTAL -eq 0 ]]; then
  echo "No IDs found in $INPUT_FILE" >&2
  exit 1
fi

echo "Total IDs: $TOTAL"
HEADER_WRITTEN=0
chunk_idx=0

while (( chunk_idx < TOTAL )); do
  CHUNK_IDS=( "${IDS[@]:chunk_idx:CHUNK_SIZE}" )
  chunk_idx=$((chunk_idx + CHUNK_SIZE))

  
  QUERY=""
  for sid in "${CHUNK_IDS[@]}"; do
    sid="${sid//$'\r'/}"
    [[ -z "$sid" ]] && continue
    QUERY+="sample_accession=${sid} OR "
  done
  QUERY="${QUERY::-4}"

  echo "Fetching chunk (size=${#CHUNK_IDS[@]}) ..."

  curl -s --get "$BASE_URL" \
       --data-urlencode "result=$RESULT" \
       --data-urlencode "query=$QUERY" \
       --data-urlencode "fields=$FIELDS" \
       --data-urlencode "format=tsv" > tmp_chunk.tsv

  if [[ ! -s tmp_chunk.tsv ]]; then
    echo "Warning: empty response for this chunk; continuing..." >&2
    continue
  fi

  if [[ $HEADER_WRITTEN -eq 0 ]]; then
    cat tmp_chunk.tsv >> "$OUTPUT_FILE"
    HEADER_WRITTEN=1
  else
    tail -n +2 tmp_chunk.tsv >> "$OUTPUT_FILE"
  fi


  sleep 0.5
done

rm -f tmp_chunk.tsv
echo "Done. Wrote: $OUTPUT_FILE"