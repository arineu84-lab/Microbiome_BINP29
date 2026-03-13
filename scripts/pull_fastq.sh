#!/bin/bash

input_file="raw_data/selected_samples.tsv"
metadata="raw_data/metadata.tsv"
output_dir="raw_data/fastq"

mkdir -p "$output_dir"

tail -n +2 "$input_file" | cut -f1 | while read -r RUN; do
    echo "Downloading FASTQs for $RUN"

    urls=$(awk -F'\t' -v run="$RUN" '$1==run {print $95}' "$metadata")

    echo "$urls" | tr ';' '\n' | while read -r url; do
        [ -n "$url" ] && wget -c -P "$output_dir" "$url"
    done

done