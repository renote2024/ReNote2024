import sys
import argparse
import json
import os
import collections.abc
from diskcache import Index

if sys.version_info >= (3, 12):
    # Add compatibility layer for Python 3.12+
    collections.Mapping = collections.abc.Mapping
    collections.MutableMapping = collections.abc.MutableMapping
    collections.Iterable = collections.abc.Iterable
    collections.MutableSet = collections.abc.MutableSet
    collections.Callable = collections.abc.Callable
    
sys.path.append('../RenoteUtils/')
from process_nb import processNB


def main(json_path):
    # Read the json file
    with open(json_path, "r", encoding='utf-8') as json_file:
        data = json.load(json_file)

    # Get the data
    repo_path = data["repo_path"]
    nb_paths = data["nb_paths"]
    results_cache_path = data["results_cache_path"]
    err_cache_path = data["err_cache_path"]
    resume = data["resume"]

    # Process the notebooks
    for i, nb_path in enumerate(nb_paths):
        nb_name = os.path.basename(nb_path)
        print(
            f"                 ------------ [{i + 1}/{len(nb_paths)}] START of Renote Analysis for {nb_name} ------------")
        try:
            processNB(nb_path=nb_path, results_cache_path=results_cache_path, err_cache_path=err_cache_path, resume=resume)
        except Exception as e:
            err_cache = Index(err_cache_path)
            err_cache[nb_path] = {"nb_path": nb_path, "status": str(e)}

    # Remove the json file
    if os.path.exists(json_path):
        os.remove(json_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Analysize a Single .ipynb file.')
    parser.add_argument('--json_path', type=str, required=True, help='Path to the json file')
    args = parser.parse_args()

    main(json_path=args.json_path)
