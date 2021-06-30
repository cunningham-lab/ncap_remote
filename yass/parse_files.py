import os
import yaml
import argparse
import sys

# lists the files that are mandatory for the analysis to run
MANDATORY_FILES = ["data", "geom", "config"]

# maps the files required by the analysis to the correct file type
FILE_TYPES = {
    "data": ".bin",
    "geom": [".npy", ".txt"],
    "config": ".yaml"
}


def yaml_to_dict(file_name):
    try:
        with open(file_name) as f:
            dictionary = yaml.full_load(f)
        return dictionary
    except:
        sys.exit("Failed to load {}".format(file_name))


# formats a dict as a list so the external bash script can parse the printed output
def dict_to_bash_str(file_dict):
    str_list = []
    for file_type, file_name in file_dict.items():
        if file_name and not file_name.isspace() and file_name != "":
            str_list.append("{}:{}".format(file_type, file_name))

    return ','.join(str_list)


def check_data(file_data):
    for mandatory in MANDATORY_FILES:
        if mandatory not in file_data or not file_data[mandatory]:
            sys.exit("Missing mandatory file {}".format(mandatory))

    for file_type, file_name in file_data.items():
        if file_name:
            ext = os.path.splitext(file_name)[1]
            try:
                #
                if ((type(FILE_TYPES[file_type]) == str and ext != FILE_TYPES[file_type]) or
                        (type(FILE_TYPES[file_type]) == list and ext not in FILE_TYPES[file_type])):
                    if file_type not in MANDATORY_FILES and file_name == "":
                        continue
                    else:
                        sys.exit("{} is not a valid file type for {} - should be {}".format(
                            file_name, file_type, FILE_TYPES[file_type]
                        ))
            except KeyError:
                sys.exit("{} isn\'t supposed to be in here!".format(file_type))


def main(args):
    meta_data = yaml_to_dict(args.meta[0])
    file_data = meta_data["files"]
    option_data = meta_data["options"]

    try:
        check_data(file_data)
    except KeyError:
        sys.exit(
            "Improperly formatted meta.json file. Check examples on the NeuroCAAS repository at "
            "https://github.com/cunningham-lab/neurocaas_contrib")
    print(dict_to_bash_str(file_data))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("meta", nargs=1)
    parsed_args = parser.parse_args()

    main(parsed_args)
