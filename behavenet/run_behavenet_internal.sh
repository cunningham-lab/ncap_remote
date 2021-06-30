#!/bin/bash

## Import functions for workflow management 
## Get the path to this function: 
execpath="$0"
scriptpath="$(dirname "$execpath")/ncap_utils"

source "$scriptpath/workflow.sh"
## Import functions for data transfer 
source "$scriptpath/transfer.sh"

## Set up error logging
errorlog

## Custom setup for this workflow
source .dlamirc

## Environment setup
export PATH="/home/ubuntu/anaconda3/bin:$PATH"
source activate nogamma 

## Declare local storage locations:
userhome="/home/ubuntu"
datastore="$userhome/neurocaas_data"
outstore="$userhome/neurocaas_output"
accessdir "$datastore" "$outstore"

## BehaveNet setup
cd "$userhome/neurocaas_remote"

## All JSON files in config go in .behavenet
jsonstore="$userhome/.behavenet"

## Make a second copy in .behavenet in root
rootjsonstore="/root/.behavenet"

## Download config file first
aws s3 cp "s3://$bucketname/$configpath" "$userhome"

## Parser will return an array of formatted strings representing key-value pairs 
output=$(python config_parser.py "$userhome/config.json") 

if [ $? != 0 ];
then
	echo "Error while parsing config, exiting..."
	exit 1
fi 

FILES=($(echo $output | tr -d '[],'))

for file in "${FILES[@]}" ; do
    
    file="${file%\'}"
    file="${file#\'}"
    FILETYPE="${file%:*}"
    FILENAME="${file#*:}"

    eval "$FILETYPE=$FILENAME"

    if [[ "$FILETYPE" = "data" ]]
    then
	    ## Stereotyped download script for data
	    aws s3 cp "s3://$bucketname/$(dirname "$inputpath")/${file#*:}" "$datastore"
	    echo "Downloading data $FILENAME"
    else
	    ## Stereotyped download script for jsons
	    aws s3 cp "s3://$bucketname/$(dirname "$inputpath")/${file#*:}" "$jsonstore"
	    aws s3 cp "s3://$bucketname/$(dirname "$inputpath")/${file#*:}" "$rootjsonstore"
	    echo "Downloading json $FILENAME"
    fi

done

## Begin BehaveNet analysis
echo "File downloads complete, beginning analysis..."
output=$(python params_parser.py "$jsonstore/$params" "$datastore/$data" "$jsonstore/directories.json")

if [ $? != 0 ];
then
	echo "Error while parsing $params, exiting..."
	exit 1
fi 

cd "$userhome/no-gamma-behavenet"

python behavenet/fitting/ae_grid_search.py --data_config "$jsonstore/$params" --model_config "$jsonstore/$model" --training_config "$jsonstore/$training" --compute_config "$jsonstore/$compute"

cd "$userhome/neurocaas_remote"
python run_hparam_search.py "$userhome/config.json" "$userhome"

## Stereotyped upload script for output
cd "$outstore"
aws s3 sync ./ "s3://$bucketname/$groupdir/$processdir"
cd "$userhome"
