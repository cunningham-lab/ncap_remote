#!/bin/bash

### Import functions for workflow management. 
### Get the path to this function: 
execpath="$0"
scriptpath="$neurocaasrootdir/ncap_utils"

source "$scriptpath/workflow.sh"
## Import functions for data transfer 
source "$scriptpath/transfer.sh"

## Set up error logging. 
errorlog

# Custom setup for this workflow.
source .dlamirc

export PATH="/home/ubuntu/anaconda3/bin:$PATH"

source activate caiman

## Declare local storage locations: 
userhome="/home/ubuntu"
datastore="ncapdata/localdata/"
configstore="ncapdata/localconfig/"
outstore="ncapdata/localout/"
# Make local storage locations
accessdir "$userhome/$datastore" "$userhome/$configstore" "$userhome/$outstore"

## Stereotyped download script for data. The only reason this comes after something custom is because we depend upon the AWS CLI and installed credentials. 
download "$inputpath" "$bucketname" "$datastore"

## Stereotyped download script for config: 
download "$configpath" "$bucketname" "$configstore"
## Check if it's yaml, and if so convert to json: 
## Reset to correctly get out json:
configname=$(python $neurocaasrootdir/ncap_utils/yamltojson.py "$userhome"/"$configstore"/"$configname")

###############################################################################################
## Custom bulk processing. 
cd "$neurocaasrootdir"
export CAIMAN_DATA="/home/ubuntu/caiman_data"
## For efficiency: 
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
CAIMAN_DATA="$userhome/caiman_data"
echo  "parsing configuration file given"
python "$neurocaasrootdir"/caiman/parse_config_caiman.py "$bucketname" "$userhome/$configstore/$configname" "$userhome/$configstore"
echo  "starting analysis."
python "$neurocaasrootdir"/caiman/process_caiman.py "$userhome/$configstore/final_pickled_new" "$userhome/$datastore/$dataname" "$userhome/$outstore" "$userhome/$configstore/$configname"
cd $userhome
###############################################################################################
## Stereotyped upload script for the data
upload "$outstore" "$bucketname" "$groupdir" "$processdir" "mp4"

