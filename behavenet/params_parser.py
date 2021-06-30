import sys
import shutil
import json
import argparse
from pathlib import Path

PARAMETERS = [
    'lab',
    'expt',
    'animal',
    'session',
    'x_pixels',
    'y_pixels',
    'n_input_channels',
    'use_output_mask',
    'frame_rate',
    'neural_type',
    'neural_bin_size',
    'approx_batch_size'
]


def json_to_dict(filename):
    try:
        with open(filename) as f:
            dictionary = json.load(f)
        return dictionary
    except ValueError:
        sys.exit('failed to load {}'.format(filename))


def check_data(paramdata):
    for param in PARAMETERS:
        if param not in paramdata:
            sys.exit('missing parameter {}'.format(param))


def create_directory_structure(paramsdata, datafile, homedir):
    datadir = json_to_dict(homedir)["data_dir"]
    filepath = '{}/{}/{}/{}/{}'.format(
        datadir, paramsdata['lab'], paramsdata['expt'], paramsdata['animal'], paramsdata['session'])
    Path(filepath).mkdir(parents=True, exist_ok=True)
    shutil.move(datafile, "{}/data.hdf5".format(filepath))
    print("moved {} to {}/data.hdf5".format(datafile, filepath))

def main(args):
    paramsfile = args.params[0]
    datafile = args.data[0]
    dirfile = args.dir[0]
    paramsdata = json_to_dict(paramsfile)
    check_data(paramsdata)
    create_directory_structure(paramsdata, datafile, dirfile)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'params', help='path to .json params file', nargs=1)
    parser.add_argument(
        'data', help='path to .hdf5 data file', nargs=1)
    parser.add_argument(
        'dir', help='path to directories.json file (in .behavenet in home dir)', nargs=1)
    args = parser.parse_args()

    main(args)
