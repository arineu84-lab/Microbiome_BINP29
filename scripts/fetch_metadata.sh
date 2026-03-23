#!/usr/bin/env bash
set -euo pipefail

input_file="raw_data/NCBI.skin.metagenome.sampleID.txt"
output_file="raw_data/metadata.tsv"
chunk_size=1000           
fields="all"               
result="read_run"
base_url="https://www.ebi.ac.uk/ena/portal/api/search"

mkdir -p raw_data
: > "$output_file"      

# Read all IDs into an array
mapfile -t IDS < "$input_file"
total=${#IDS[@]}
if [[ $total -eq 0 ]]; then
  echo "No IDs found in $input_file" >&2
  exit 1
fi

echo "Total IDs: $total"
header_written=0
chunk_idx=0

while (( chunk_idx < total )); do
  chunk_IDs=( "${IDS[@]:chunk_idx:chunk_size}" )
  chunk_idx=$((chunk_idx + CHUNK_SIZE))

  
  query=""
  for sid in "${chunk_IDs[@]}"; do
    sid="${sid//$'\r'/}"
    [[ -z "$sid" ]] && continue
    QUERY+="sample_accession=${sid} OR "
  done
  query="${query::-4}"

  echo "Fetching chunk (size=${#chunk_IDs[@]}) ..."

  curl -s --get "$base_url" \
       --data-urlencode "result=$result" \
       --data-urlencode "query=$query" \
       --data-urlencode "fields=$fields" \
       --data-urlencode "format=tsv" > tmp_chunk.tsv

  if [[ ! -s tmp_chunk.tsv ]]; then
    echo "Warning: empty response for this chunk; continuing..." >&2
    continue
  fi

  if [[ $header_written -eq 0 ]]; then
    cat tmp_chunk.tsv >> "$output_file"
    header_written=1
  else
    tail -n +2 tmp_chunk.tsv >> "$output_file"
  fi


  sleep 0.5
done

rm -f tmp_chunk.tsv
echo "Done. Wrote: $OUTPUT_FILE"
