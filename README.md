# Jupyter Notebook Analysis

A robust Python-based analyzer for analyzing, restoring, and executing Jupyter notebooks at scale. This tool handles common execution errors by automatically fixing missing dependencies, file paths, and variable definition issues.

## Prerequisites

- Python 3.12
- Virtual environment management capabilities
- Sufficient disk space for caching and virtual environments

## Installation

1. Clone the repository:
```bash
git clone https://github.com/renote2024/ReNote2024.git
cd ReNote2024
```

2. Set up virtual environments for repository analysis in `create_envs.py`:
- Edit the number of virtual environments you want to create (if you want to run in parallel, or 1 if you want to run sequentially).
- Edit the paths for virtual environments

```python
backup_envs_path = "path_to_your_backup_envs"
source_envs_path = "path_to_your_source_envs"
```
- Run
```bash
python create_envs.py
```

3. Install the required dependencies:
```bash
pip install requirements.txt
```

## Run the Program
1. Execute analysis:
```bash
cd project_main/main_code/
python main.py --all_repo_dir_path <path/to/all/repos/dir> --json_paths <path/to/a/json/dir> --results_cache_path <path/to/results/cache/dir> --err_cache_path <path/to/error/cache/dir> --resume <0 or 1>
```
- <path/to/all/repos/dir>: directory containing all .csv files that have information on repositories and notebooks (require fields: project_path (path to the repository in your working directory) and ipynb_files (list of notebook files in that repository)
- <path/to/a/json/dir>: a directory containing temporary JSON files supporting analysis
- <path/to/results/cache/dir>: path to a directory to store results
- <path/to/error/cache/dir>: path to a directory to store error notebooks
- resume: 1 when you want to run all notebooks and check if notebooks have already been evaluated, and 0 otherwise.

2. If you want to view the results in CSV:
```bash
# In project main's directory
python convert_cache_to_csv.py --results_cache_path <path/to/results/cache/dir> --csv <path/to/your/csv/file>
```
