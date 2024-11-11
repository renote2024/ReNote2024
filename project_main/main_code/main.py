import subprocess
import json
import sys
import argparse
import os
import shutil
import pandas as pd
from tqdm import tqdm
import diskcache as dc
from diskcache import Index
from joblib import Parallel, delayed

sys.path.append('../RenoteUtils/')
 
import collections.abc

if sys.version_info >= (3, 12):
    # Add compatibility layer for Python 3.12+
    collections.Mapping = collections.abc.Mapping
    collections.MutableMapping = collections.abc.MutableMapping
    collections.Iterable = collections.abc.Iterable
    collections.MutableSet = collections.abc.MutableSet
    collections.Callable = collections.abc.Callable

from process_nb import processNB, checkIfNBIsAlreadyEvaluated
from requirement_file_process import convertRequirementFile, findRequirementsFile
from nb_utils import readNoteBook


def divide_list_into_parts(lst, num_parts):
    out = []
    if num_parts < len(lst):
        step = len(lst) // num_parts
        i = 0
        count = 0
        while count < num_parts:
            out.append(lst[i:i + step])
            i += step
            count += 1

        while i < len(lst):
            out[-1].append(lst[i])
            i += 1
    else:
        for i in range(len(lst)):
            out.append([lst[i]])

    return out


def readAllCSVToDict(directory_path):
    # Initialize an empty dictionary to hold the combined data
    combined_dict = {}

    # Loop through all CSV files in the directory
    for filename in os.listdir(directory_path):
        if filename.endswith('.csv'):
            # Full path to the CSV file
            csv_path = os.path.join(directory_path, filename)

            # Read the CSV file into a DataFrame
            df = pd.read_csv(csv_path)

            # Convert nb_paths from a single string to a list (split by ';')
            df['ipynb_files'] = df['ipynb_files'].apply(lambda x: x.split(';') if pd.notna(x) else [])

            # Convert the DataFrame to a dictionary and merge it with the combined_dict
            current_dict = df.set_index('project_path')['ipynb_files'].to_dict()

            # Update the combined dictionary with the current CSV data
            for project_path, nb_paths in current_dict.items():
                if project_path in combined_dict:
                    # Append the notebook paths if project_path already exists
                    combined_dict[project_path].extend(nb_paths)
                else:
                    # Otherwise, add a new entry
                    combined_dict[project_path] = nb_paths

    return combined_dict


def combineAllNBPaths(project_dict):
    # Initialize an empty list to hold all notebook paths
    all_nb_paths = []

    # Iterate through the dictionary and extend the list with the notebook paths
    for nb_paths in project_dict.values():
        all_nb_paths.extend(nb_paths)

    return all_nb_paths


def filterEvaluatedNB(all_repos, results_cache, err_cache):
    filtered_dict = {}

    for repo_path, nb_paths in all_repos.items():
        filtered_nb_paths = []
        for nb_path in nb_paths:
            if "ipynb_checkpoints" in nb_path:
                continue
            nb_name = os.path.basename(nb_path)
            res = checkIfNBIsAlreadyEvaluated(results_cache, nb_name)
            res_err = checkIfNBIsAlreadyEvaluated(err_cache, nb_path)
            if res is None and res_err is None:
                # filtered_nb_paths.append(nb_path)
                result = readNoteBook(nb_path)
                if result[1] == "Success":
                    filtered_nb_paths.append(nb_path)
                else:
                    err_cache[nb_path] = {"nb_path": nb_path, "status": result[1]}
        if filtered_nb_paths:
            if repo_path not in filtered_dict:
                filtered_dict[repo_path] = []
            filtered_dict[repo_path] = filtered_nb_paths

    return filtered_dict


def shellProcessNB(local_env, config):
    repo_path = config['repo_path']
    nb_paths = config['nb_paths']       # list
    json_paths = config['json_paths']
    results_cache_path = config['results_cache_path']
    err_cache_path = config['err_cache_path']
    resume = config['resume']           # 1 or 0
    backup_venv_path = os.path.join(config['backup_envs_path'], local_env)
    source_venv_path = os.path.join(config['source_envs_path'], local_env)
    i = config['index']
    repo_name = os.path.basename(repo_path)

    print(
        f"        ############################# [{i + 1}/{config['total_repos']}] START ANALYSIS FOR REPO `{repo_name}` #############################")
    print(f'Env {local_env} is processing the repo {repo_name}')

    # Check if the backup path exists or not
    if not os.path.exists(backup_venv_path):
        raise FileNotFoundError(f"Backup virtual environment path '{backup_venv_path}' does not exist.")

    # Check if the old path exists or not
    if not os.path.exists(source_venv_path):
        print(f'Source venv not existing. Copying from the backup venv to {source_venv_path}')
        subprocess.run(f"cp -r {backup_venv_path} {config['source_envs_path']}", shell=True)
        # raise FileNotFoundError(f"Old virtual environment path '{source_venv_path}' does not exist.")
    else:
        # Delete the old venv
        print(f'Deleting the old venv: {source_venv_path}')
        subprocess.run(f'rm -rf {source_venv_path}', shell=True)

        # Copy the backup venv to the old venv
        print(f'Copying the backup venv to the old venv: {source_venv_path}')
        subprocess.run(f"cp -r {backup_venv_path} {config['source_envs_path']}", shell=True)

    # Activate the virtual environment
    activate_script = os.path.join(source_venv_path, 'bin', 'activate')
    command_activate = f'source {activate_script} &&'

    # Install requirements, if any
    requirements_file = findRequirementsFile(repo_path)
    out_req_file = None
    command_install_requirements = ''
    if requirements_file:
        out_req_file = convertRequirementFile(requirements_file)
        command_install_requirements = f'pip install -r {out_req_file} &&'

    data = {
        'repo_path': repo_path,
        'nb_paths': nb_paths,
        'results_cache_path': results_cache_path,
        'err_cache_path': err_cache_path,
        'resume': resume
    }

    # Save the data to a json file
    json_path = os.path.join(json_paths, f'{os.path.basename(source_venv_path)}.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

    # Run the process_repo.py script
    command_run_process_repo = f'python process_repo.py --json_path {json_path} &&'

    # Deactivate the virtual environment
    command_deactivate = 'deactivate'

    # Execute the full command
    try:    
        command = f'{command_activate} {command_install_requirements} {command_run_process_repo} {command_deactivate}'
        subprocess.run(command, shell=True)
    except Exception as e:
        print(f"=== Error occurred while processing the repo {repo_name} === \n{e}")

    # Delete the output requirements file
    if out_req_file:
        os.remove(out_req_file)

    print(
        f"        ############################# [{i + 1}/{config['total_repos']}] END ANALYSIS FOR REPO `{repo_name}` #############################")


def getAllReposWithNBLists(all_repo_dir_path, results_cache_path, err_cache_path):
    if not os.path.exists(results_cache_path):
        raise FileNotFoundError(f"Results cache path '{results_cache_path}' does not exist.")
    if not os.path.exists(err_cache_path):
        raise FileNotFoundError(f"Error cache path '{err_cache_path}' does not exist.")
    results_cache = Index(results_cache_path)
    err_cache = Index(err_cache_path)
    all_repos_unfiltered = readAllCSVToDict(all_repo_dir_path)  # dict
    all_repos = filterEvaluatedNB(all_repos_unfiltered, results_cache, err_cache)
    all_nbs = combineAllNBPaths(all_repos)
    return all_repos, all_nbs


def processNBFolderSequential(all_repo_dir_path, json_paths, results_cache_path, err_cache_path, resume):
    subprocess.run('cd / && cd tmp && rm -rf pyright*/ && rm -rf pip*/ && rm -rf tmp*/ && rm tmp*', shell=True)

    all_repos, all_nbs = getAllReposWithNBLists(all_repo_dir_path, results_cache_path, err_cache_path)

    print(f"TOTAL {len(all_repos)} REPOS & {len(all_nbs)} NOTEBOOKS NOT EVALUATED YET")

    backup_envs_path = "path_to_your_backup_envs" # Change this to the path where you backup the virtual environments
    source_envs_path = "path_to_your_source_envs" # Change this to the path where you create virtual environments

    for i, repo in enumerate(all_repos.items()):
        repo_path, nb_paths = repo
        config = {
            'index': i,
            'repo_path': repo_path,
            'nb_paths': nb_paths,
            'results_cache_path': results_cache_path,
            'err_cache_path': err_cache_path,
            'resume': resume,
            'backup_envs_path': backup_envs_path,
            'source_envs_path': source_envs_path,
            'total_repos': len(all_repos),
            'json_paths': json_paths
        }
        try:
            shellProcessNB('nb1_venv', config)
            subprocess.run('cd / && cd tmp && rm -rf pyright*/ && rm -rf pip*/ && rm -rf tmp*/ && rm tmp*', shell=True)
        except Exception as e:
            print(f"Error in processing the repository {repo_path}, Error: {e}")
            print('>>> EXITING THE PROCESSING OF THE REPOSITORY DUE TO ERROR <<<')
            continue

def executeTask(env, task_li):
    for config in task_li:
        shellProcessNB(env, config)

def split_dict(input_dict, chunk_size):
    # Convert dictionary items to a list of tuples
    items = list(input_dict.items())
    
    # Create a list of smaller dictionaries with specified chunk size
    return [dict(items[i:i + chunk_size]) for i in range(0, len(items), chunk_size)]

def processNBFolderParallel(all_repo_dir_path, json_paths, results_cache_path, err_cache_path, resume):
    subprocess.run('cd / && cd tmp && rm -rf pyright*/ && rm -rf pip*/ && rm -rf tmp*/ && rm tmp*', shell=True)

    all_repos, all_nbs = getAllReposWithNBLists(all_repo_dir_path, results_cache_path, err_cache_path)

    print(f"TOTAL {len(all_repos)} REPOS & {len(all_nbs)} NOTEBOOKS NOT EVALUATED YET")
    envs = [f'nb{i}_venv' for i in range(1, 33)]
    print(f'envs: {envs}')

    backup_envs_path = "path_to_your_backup_envs" # Change this to the path where you backup the virtual environments
    source_envs_path = "path_to_your_source_envs" # Change this to the path where you create virtual environments

    list_of_all_repos = split_dict(all_repos, chunk_size=len(envs) * 3)
    for repo_list in list_of_all_repos:
        all_repos_with_assign_ids = [
            {
                'index': i,
                'total_repos': len(repo_list),
                'repo_path': repo_path,
                'nb_paths': nb_paths,
                'results_cache_path': results_cache_path,
                'err_cache_path': err_cache_path,
                'resume': resume,
                'backup_envs_path': backup_envs_path,
                'source_envs_path': source_envs_path,
                'json_paths': json_paths
            } for i, (repo_path, nb_paths) in enumerate(repo_list.items())
        ]
        li_of_li_tasks = divide_list_into_parts(all_repos_with_assign_ids, len(envs))
        assert len(li_of_li_tasks) == len(envs)
        results = Parallel(backend='multiprocessing', n_jobs=len(envs))(delayed(executeTask)(env, task_l) for env, task_l in zip(envs, li_of_li_tasks))
        subprocess.run('cd / && cd tmp && rm -rf pyright*/ && rm -rf pip*/ && rm -rf tmp*/ && rm tmp*', shell=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Read all .ipynb files in a directory.')
    parser.add_argument('--all_repo_dir_path', type=str, required=True, help='Path to the text file containing the notebooks')
    parser.add_argument('--json_paths', type=str, required=True, help='Path to the json files storing repo information for process_repo.py')
    parser.add_argument('--results_cache_path', type=str, required=True, help='Path to the results cache [DiskCache]')
    parser.add_argument('--err_cache_path', type=str, required=True, help='Path to the error cache [DiskCache]')
    parser.add_argument('--resume', type=int,  help='Check the cache before processing the notebook if 1, else process all the notebooks', default=0)
    args = parser.parse_args()
   
    # Use this line if you want to run the process sequentially
    processNBFolderSequential(all_repo_dir_path=all_repo_dir_path, json_paths=json_paths,results_cache_path=parallel_cache_path,err_cache_path=err_cache_path, resume=resume) 

    # Uncomment the following line if you want to run the process in parallel   
    # processNBFolderParallel(all_repo_dir_path=all_repo_dir_path, json_paths=json_paths, results_cache_path=parallel_cache_path, err_cache_path=err_cache_path, resume=resume)
