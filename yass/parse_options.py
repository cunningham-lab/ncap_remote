import argparse
import sys
import copy

from parse_files import yaml_to_dict, dict_to_bash_str, FILE_TYPES

COMMAND_TEMPLATE = {
    "retrain": {
        "yes": "yass train \'config\'",
        "no": "echo Using default neural networks ..."
    },
    "run": {
        "yes": "yass sort \'config\'",
        "no": "echo Doing nothing, goodbye!"
    }
}


def check_options(options):
    for action, option in options.items():
        try:
            test = COMMAND_TEMPLATE[action][option]
        except KeyError:
            sys.exit("{} is not a valid option for {}!".format(action, option))


def substitute_file_names(command, file_data):
    for file_type in FILE_TYPES:
        try:
            command = command.replace("\'{}\'".format(file_type), file_data[file_type])
        except KeyError:
            continue
    return command


def create_options_dict(files):
    options_dict = copy.deepcopy(COMMAND_TEMPLATE)
    for option in options_dict:
        for setting in options_dict[option]:
            options_dict[option][setting] = substitute_file_names(options_dict[option][setting], files)
    return options_dict


def replace_option_commands(options_data, options_dict):
    for option in options_data:
        options_data[option] = options_dict[option][options_data[option]]


def main(args):
    meta_data = yaml_to_dict(args.meta[0])
    file_data = meta_data["files"]
    option_data = meta_data["options"]

    try:
        check_options(option_data)
    except KeyError:
        sys.exit(
            "Improperly formatted meta.json file. Check examples on the NeuroCAAS repository at "
            "https://github.com/cunningham-lab/neurocaas_contrib")
    options_dict = create_options_dict(file_data)
    replace_option_commands(option_data, options_dict)
    print(dict_to_bash_str(option_data))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("meta", nargs=1)
    parsed_args = parser.parse_args()

    main(parsed_args)
