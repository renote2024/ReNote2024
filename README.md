
# Are the Majority of Public Computational Notebooks Pathologically Non-Executable?

### Authors

* **Tien Nguyen**: Ph.D. Candidate at Virginia Tech (<tiennguyen@vt.edu>)
* **Waris Gill**: Ph.D. Candidate at Virginia Tech (<waris@vt.edu>)
* **Muhammad Ali Gulzar**: Assistant Professor at Virginia Tech (<gulzar@vt.edu>)

**Link to paper:** <https://arxiv.org/abs/2502.04184>

**Description:** A robust Python-based analyzer for analyzing, restoring, and executing Jupyter notebooks at scale. This tool handles common execution errors by automatically fixing missing dependencies, file paths, and variable definition issues.


## Prerequisites

- Python 3.12
- Virtual environment management capabilities
- Sufficient disk space for caching and virtual environments

## Pre-execution Preparation
To replicate the experiment, you will need a number of repositories cloned in your local machine and a CSV file containing the information of all repositories and their notebooks (require fields: project_path (path to the repository in your working directory) and ipynb_files (list of notebook file paths in that repository). You can do this by iterating through all repositories and retrieving the path of all notebook files for each repository.
We have provided the URL links to all repositories analyzed in our experiment in the CSV file `dataset_results.csv` (marked as the `url` column of the file).

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

  **Note:** The program can be executed in 2 modes (sequential or parallel). Thus, before running the script above, adjust the code to your preferred mode, simply by uncommenting the line you want to execute and commenting out the line you do not want to execute.

2. If you want to view the results in CSV:
```bash
# In project main's directory
python convert_cache_to_csv.py --results_cache_path <path/to/results/cache/dir> --csv <path/to/your/csv/file>
```

### CSV File `data_results.csv` Content Overview

| **Column Name**               | **Description**                                                                                              |
|--------------------------------|--------------------------------------------------------------------------------------------------------------|
| **Total Code Cells**           | Total number of code cells in the notebook.                                                                 |
| **Initial_Status**             | Notebook's executability status before restoration (`executable`, `NameError`, etc.).|
| **Initial_max_execute_cells**  | Maximum number of cells executed successfully before restoration.                                           |
| **Final_Status**               | Executability status after restoration.                                                                     |
| **Final_max_execute_cells**    | Maximum number of cells executed successfully after restoration.                                            |
| **Increased_execution_cells**  | Additional cells executed post-restoration (`Final - Initial`).                                             |
| **Increased_execution_percentage** | Percentage improvement in execution success.                                                              |
| **all_unique_errors_during_execution** | List of unique error types encountered during execution.                                                |
| **total_module_not_found**     | Count of `ModuleNotFoundError` occurrences.                                                                 |
| **total_file_not_found**       | Count of `FileNotFoundError` occurrences.                                                                   |
| **total_name_error**           | Count of `NameError` occurrences.                                                                           |
| **FileCreationError (Manual)** | Notes on manually identified input file creation errors.                                                          |
| **nb_path**                    | Local file path of the analyzed notebook.                                                                  |
| **ast_status**                 | Static analysis result for undefined variables, functions, classes, etc. (`no_undefined` if none).                          |
| **star**                       | Popularity score of the GitHub repository (based on stars).                                                |
| **repo_path**                  | Local directory path of the repository.                                                                    |
| **url**                        | GitHub URL of the repository.                                                                              |
