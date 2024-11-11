import os
import re
import yaml
import chardet

# List of Conda-specific packages that won't work in a venv environment
CONDA_SPECIFIC_PACKAGES = [
    'mkl', 'blas', 'intel-openmp', 'vc', 'vs2015_runtime', 'icc_rt'
]

def is_conda_specific_package(package_line):
    """Check if a package is Conda-specific and should be ignored."""
    for conda_pkg in CONDA_SPECIFIC_PACKAGES:
        if package_line.startswith(conda_pkg):
            # print(f"Warning: Ignoring Conda-specific package: {package_line}")
            return True
    return False

def convert_conda_to_venv_line(package_line):
    """Convert Conda format to venv/pip format."""
    match = re.match(r'^([a-zA-Z0-9_\-]+)=([0-9\.]+)', package_line)
    if match:
        package, version = match.groups()
        return f"{package}=={version}"
    else:
        if not package_line.startswith("#"):
            return package_line
        else:
            # print(f"Warning: Could not convert package line: {package_line}")
            return None

def is_conda_env_file(file_path):
    """Check if the file is a Conda environment file."""
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as infile:
        for line in infile:
            line = line.strip()
            if line.startswith("# platform:") or ("=" in line and not "==" in line):
                return True
    return False

def convert_conda_to_venv_file(conda_file):
    """Convert a Conda requirements.txt file to a venv-compatible requirements.txt."""
    venv_lines = []
    with open(conda_file, "rb") as rawdata:
        result = chardet.detect(rawdata.read(10000))
        encoding = result["encoding"]

    # Use detected encoding
    with open(conda_file, "r", encoding=encoding) as infile:
        for line in infile:
            line = line.strip()
            if not line or is_conda_specific_package(line):
                continue
            venv_line = convert_conda_to_venv_line(line)
            if venv_line:
                venv_lines.append(venv_line)
    return venv_lines

def convert_yaml_to_txt(yaml_file):
    """Convert a YAML requirements file to a requirements.txt format."""
    with open(yaml_file, 'r') as infile:
        env_data = yaml.safe_load(infile)

    packages = []
    if 'dependencies' in env_data:
        for dep in env_data['dependencies']:
            if isinstance(dep, str):
                package_parts = dep.split('=')
                if len(package_parts) > 1:
                    packages.append(f"{package_parts[0]}=={package_parts[1]}")
                else:
                    packages.append(dep)
            elif isinstance(dep, dict):
                if 'pip' in dep:
                    packages.extend(dep['pip'])
    
    return packages

def extract_packages_from_file(file_path):
    """Extract packages from various file formats."""
    ext = os.path.splitext(file_path)[1].lower()
    packages = set()

    with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
        if ext in ['.txt', '.in', '.ci', '.tx']:
            for line in file:
                line = line.strip()
                if line and not line.startswith('#'):
                    packages.add(line)
        elif ext == '.sh':
            for line in file:
                if line.startswith('pip install'):
                    packages.update(line.split('pip install ')[1].strip().split())
        elif ext == '.md':
            for line in file:
                if line.startswith('- ') or line.startswith('```'):
                    package_line = line.strip().strip('-').strip('```').strip()
                    if package_line:
                        packages.add(package_line)
        elif ext in ['.py', '.go']:
            for line in file:
                if ext == '.py':
                    if line.startswith('import ') or line.startswith('from '):
                        packages.update(re.findall(r'import (\w+)|from (\w+) import', line))
                elif ext == '.go':
                    if 'import ' in line:
                        packages.update(re.findall(r'import\s*\(\s*(.*?)\s*\)', line, re.DOTALL))

    return list(packages)

def findRequirementsFile(repo_path):
    """Find the requirements file in the given repository."""

    # First, look for requirements.txt
    for dirpath, _, filenames in os.walk(repo_path):
        if 'requirements.txt' in filenames:
            return os.path.join(dirpath, 'requirements.txt')

    # If requirements.txt is not found, look for other formats
    other_files = ['requirements.yml', 'requirements.yaml']
    other_extensions = ['.in', '.ci', '.tx', '.sh', '.md', '.py', '.go']

    for dirpath, _, filenames in os.walk(repo_path):
        for filename in other_files:
            if filename in filenames:
                return os.path.join(dirpath, filename)

        for ext in other_extensions:
            filename = f"requirements{ext}"
            if filename in filenames:
                return os.path.join(dirpath, filename)

    # If no requirements file is found, return None
    return None

def convertRequirementFile(requirements_file):
    """Convert requirements file to venv format."""
    # Determine the file format and convert to venv format
    file_ext = os.path.splitext(requirements_file)[1].lower()
    output_file = os.path.join(os.path.dirname(requirements_file), 'requirements_venv.txt')

    if file_ext == '.txt':
        if is_conda_env_file(requirements_file):
            # print("Converting Conda environment to venv format...")
            packages = convert_conda_to_venv_file(requirements_file)
        else:
            # print("File is already in txt format")
            packages = extract_packages_from_file(requirements_file)
    elif file_ext in ['.yml', '.yaml']:
        # print("Converting YAML to txt format...")
        packages = convert_yaml_to_txt(requirements_file)
    else:
        # print(f"Converting {file_ext} format to txt...")
        packages = extract_packages_from_file(requirements_file)

    # Write packages to the output file
    with open(output_file, 'w', encoding='utf-8') as outfile:
        for package in packages:
            if package and not is_conda_specific_package(package):
                outfile.write(f"{package}\n")

    # print(f"Converted requirements saved to: {output_file}")
    return os.path.abspath(output_file)
