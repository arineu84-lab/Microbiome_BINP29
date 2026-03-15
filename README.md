## Visualising geographical distribution of a Skin Microbiome

Author: Ariane Neumann

Date: 2026-03-09

Description:  In this project, I received a list of IDs for skin microbiome samples. The data connected to the sample IDs contain metagenome information, like location of sampling, fastq info and more.
(An important note is here, that the data analysed are raw reads. Usually, one should clean them up before downstream analysis. A pipeline for the clean-up will be provided in this repository)

Tasks:
1. Extract metadata and visualise the geographical distribution of samples (number of samples from each country).
2. Visualise the distribution of sequencing types (16S rRNA amplicon vs shotgun metagenome) across different geographical regions.
3. Create an interactive map showing the locations where the microbiome samples were collected.
4. Select three 16S samples samples from Europe (decided on Austria and Germany 3 samples each).
5. Analyse and visualise the distribution of microbial species. If possible, attempt strain-level profiling.
6. Generate Krona plots to visualise the microbial composition of these samples.
7. Integrate this with the interactive map so that clicking on a sample location opens the Krona plot showing its microbiome composition (this will be done for only the three samples).

Input:
NCBI.skin.metagenome.sampleID.txt
metadata.tsv

Setting up the working environment 
Use txt file get the NCBI metadata, change the sample IDs (SAMEA121737266) to general name.
First download and store output in new tsv file, then later can be filtered

Versions:


Create conda environment
````bash
conda create -n skin_microbes
````

Create an empty output file
````bash
> metadata.tsv
````

Fetching all meta data and save into new tsv file
````bash
first=1
while read ID; do
    echo "Fetching metadata for $ID ..."
    if [ $first -eq 1 ]; then
        # First ID → keep the header
        curl -s "https://www.ebi.ac.uk/ena/portal/api/search?result=read_run&query=sample_accession=${ID}&fields=all&format=tsv" \
            >> metadata.tsv
        first=0
    else
        # All other IDs → drop the header (tail -n +2)
        curl -s "https://www.ebi.ac.uk/ena/portal/api/search?result=read_run&query=sample_accession=${ID}&fields=all&format=tsv" \
            | tail -n +2 >> metadata.tsv
    fi
done < NCBI.skin.metagenome.sampleID.txt
````
OBS: Here only meta data from 29k samples were used!

Get column numbers of NCBI metadata
````bash
head -n2 raw_data/metadata.tsv | sed 's/\t/\n/g' | nl -ba
````

The initial plan was to later select 3 samples from Sweden, for this the metadata.tsv
file was checked for certain longitudinal and latitudinal coordinates
````bash
awk -F'\t' '
  NR==1 { next }                       
  ($161 >= 55 && $161 <= 69) && ($133 >= 11 && $133 <= 24)
' raw_data/metadata.tsv | wc -l
````
This showed no match for Sweden

Therefore, it was decided to check which and how many samples are around "Sweden" found in the dataset
````bash
awk -F'\t' '  # count samples at certain coordinates
NR>1 &&
($161+0)>=54 && ($161+0)<=72 &&
($133+0)>=5  && ($133+0)<=32
' raw_data/metadata.tsv | wc -l

awk -F'\t' ' # name samples at certain coordinates
NR>1 &&
($161+0)>=54 && ($161+0)<=72 &&
($133+0)>=5  && ($133+0)<=32 {
    print $55
}
' raw_data/metadata.tsv | sort | uniq -c | sort -nr
````
Outcome:
- 315 Denmark: Aarhus
- 62 Finland
- 60 Finland: North Karelia
- 52 Russia: Republic of Karelia, Pitkaranta
- total 489 samples

Based on these findings, other samples were selected. While samples from neighbour countries were available, the interest was on the skin microbiome with focus on hand and palm. These body locations were not found for these countries, thus downstream analysis was performed with other european countries. However, based on the coordinates and body_sites, this selection can always be adapted to the research question. 

=========================================================
1. Filter data set 

Install the world package from natural earth (required for geopandas)
````bash
wget https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip
unzip ne_110m_admin_0_countries.zip
````
write python script to filter meta data for certain selected columns
e.g. longitude and latitude coordinates and well as body site
````bash
python scripts/filter_columns.py 

# check that all columns contain something
head -n2 raw_data/filtered_meta.tsv | sed 's/\t/\n/g' | nl -ba
````

2. Geographical distribution of all samples 

Next, filter for the countries in order to plot geographical distribution of all
samples. For this use a script that computes the number of samples per country
from lat/lon coordinates by reverse-geocoding points against Natural Earth country polygons.
````bash
python scripts/country_distribution.py 
````
3. Distribution of sequencing types 

First check for the different sequencing types in column 6
````bash
cut -f6 raw_data/filtered_meta.tsv | sort | uniq -c

# Based on previous discussion, it was decided here to continue with
# the 16S (another student will focus on shotgun).
conda install anaconda::seaborn # required for plotting
python scripts/sequence_type.py
````
4. Taxonomic profiling of selected samples 

This script assigns a country to each sample using its coordinates 
(reverse‑geocoding, which convert lat/lon columns to a country)
````bash
python scripts/select_samples.py 

# download the selected fastq files using bash script (in data/fastq)
# write script and make it executable
chmod +x pull_fastq.sh
bash scripts/pull_fastq.sh

# Install kraken2 for assigning taxonomic labels 
# create new (subdirectories)
conda install bioconda::kraken2
conda install bioconda::bracken # Bayesian Reestimation of Abundance with KrakEN
conda install bioconda::krona
mkdir results/kraken2 results/bracken results/krona 

# Also need a SILVA data base to be created and run properly
mkdir -p db
kraken2-build --special silva --db silva16s --threads 8
kraken2-build --build --db silva16s --threads 8

# test with one random file
kraken2 --db db/silva16s --threads 8 --report test.report \
        --output test.kraken data/fastq/ERR12384459.fastq.gz

# Build Bracken k-mer distribution for 150 bp reads
bracken-build -d "db/silva16s" -t 8 -k 35 -l 150

# write python script for Kraken2 and run
python scripts/kraken2.py 
# check all files in results/
# Need to check that all taxonomy levels are available
# this created kraken2 and bracken tsv files for later analysis
````

5. Krona and taxonomy lineage using bracken
````bash
# install taxonkit and update python script to create krona.tsv
conda install bioconda::taxonkit
python scripts/krona_bracken.py 

# be sure that Krona taxonomy is installed, otherwise use
updateTaxonomy.sh
# then run script again

# bash one liner for creating lineage.tsv files
for f in results/krona/*_krona.tsv; do
  s=$(basename "$f" _krona.tsv)
  echo "[LINEAGE] $s"
 paste <(cut -f1 "$f") <(cut -f2 "$f" | taxonkit lineage | cut -f2-) \
    > "results/lineage/${s}_lineage.tsv"
done
````
6. Integrate Krona plots into interactive map

Run script for interactive map using folium
````bash
pip install folium
python scripts/interactive_map.py 

# download html files to local computer
scp -r user@server/results/ .
````
