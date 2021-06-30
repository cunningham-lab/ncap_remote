#!/bin/bash

## Import functions for workflow management. 
## Get the path to this function: 
execpath="$0"
scriptpath="$(dirname "$execpath")/ncap_utils"

source "$scriptpath/workflow.sh"
## Import functions for data transfer 
source "$scriptpath/transfer.sh"

## Set up error logging. 
errorlog

## Custom setup for this workflow.
source .dlamirc

## Environment setup
export PATH="/home/ubuntu/anaconda3/bin:$PATH"
source activate yass

## Declare local storage locations: 
userhome="/home/ubuntu"
scripthome="$userhome/neurocaas_remote"
datastore="$userhome/yass/samples/localdata"
outstore="$userhome/yass/samples/localdata/tmp"
accessdir "$datastore" "$outstore"

## Move into script directory
cd "$scripthome"

## Download config file first
echo "Downloading config.json ..."
aws s3 cp "s3://$bucketname/$configpath" "$scripthome"

## Parser will return an array of formatted strings representing key-value pairs of file type and file name
echo "Parsing files from config.json ..."
file_output=$(python parse_files.py "$scripthome/config.json")

if [ $? != 0 ];
then
	echo "Error while parsing config, exiting ..."
	exit 1
fi 

IFS=',' read -ra FILES <<< "$file_output"

for file in "${FILES[@]}" ; do
    
    FILETYPE="${file%:*}"
    FILENAME="${file#*:}"

    aws s3 cp "s3://$bucketname/$(dirname "$inputpath")/$FILENAME" "$datastore"
    echo "Downloading file $FILENAME" to "$datastore"

done

## Another parser, this time returning key-value pairs of analysis options and bash commands
echo "Parsing analysis options from config.json ..."
option_output=$(python parse_options.py "$scripthome/config.json")

if [ $? != 0 ];
then
	echo "Error while parsing config, exiting..."
	exit 1
fi

IFS=',' read -ra OPTIONS <<< "$option_output"
for option in "${OPTIONS[@]}" ; do
    OPTION="${option%:*}"
    COMMAND="${option#*:}"
    echo "option is $OPTION, command is $COMMAND"
    eval "$OPTION=\"$COMMAND\""

done

## Begin YASS analysis
echo "File downloads complete, beginning analysis..."
cd "$datastore"
eval "$retrain"
eval "$run"

## Go to result directory
cd "$outstore"
aws s3 sync ./ "s3://$bucketname/$groupdir/$processdir"
cd "$userhome"
