import subprocess
import os
from tqdm import tqdm

def create_and_setup_venv(base_path, venv_name):
    venv_path = os.path.join(base_path, venv_name)
    if not os.path.exists(venv_path):
        os.makedirs(venv_path)
    
    # Create the virtual environment
    subprocess.run(['python', '-m', 'venv', venv_path])
    
    # Activate the virtual environment
    activate_script = os.path.join(venv_path, 'bin', 'activate')
    
    # Install requirements
    requirements_file = "requirements.txt"
    if os.path.isfile(requirements_file):
        subprocess.run(f'source {activate_script} && pip install -r {requirements_file} && deactivate', shell=True)
    else:
        print(f"No requirements.txt found at {requirements_file}")

def copy_to_backup(venv_name, source_path, backup_path):
    source_env = os.path.join(source_path, venv_name)
    backup_env = os.path.join(backup_path, venv_name)
    if os.path.exists(source_env):
        subprocess.run(f"cp -r {source_env} {backup_env}", shell=True)
    else:
        print(f"Source virtual environment {source_env} does not exist.")

def main():
    source_path = "path/to/source/envs"
    backup_path = "path/to/backup/envs"
    
    if not os.path.exists(backup_path):
        os.makedirs(backup_path)
    
    num_envs = 32 # Change this to the number of virtual environments you want to create
    for i in  tqdm(range(1, num_envs + 1)):
        venv_name = f'nb{i}_venv'
        create_and_setup_venv(source_path, venv_name)
        copy_to_backup(venv_name, source_path, backup_path)

if __name__ == "__main__":
    main()
