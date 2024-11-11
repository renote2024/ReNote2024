import nbformat
import ast
import papermill as pm
import os
import subprocess
import sys
import json
from ast_visit import ASTNodeVisitor


def get_notebook_language(notebook_path):
    if os.path.getsize(notebook_path) == 0:
        print(f"Notebook file {notebook_path} is empty.")
        return None
    
    with open(notebook_path, 'r', encoding='utf-8') as f:
        try:
            notebook = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Failed to decode JSON from {notebook_path}: {e}")
            return None
    
    # Extract kernel info and language info
    kernelspec = notebook.get('metadata', {}).get('kernelspec', {})
    # print(notebook.get('metadata', {}))
    language_info = notebook.get('metadata', {}).get('language_info', {})
    
    # Check for language in kernelspec or language_info
    kernel_name = kernelspec.get('name', 'unknown')
    language_name = language_info.get('name', 'unknown')
    version = language_info.get('version', 'unknown')
    
    return language_name, version, kernel_name
    
def readNoteBook(nb_path):   
    nb = ReadNB(nb_path)
    nb_content = nb.readNB()
    # print(nb_content)

    # 1. If we cannot read the notebook file, we will move it to the error directory
    if nb_content is None:
        print(f"Cannot read the notebook file {nb_path}")
        return nb, "Cannot read"
    
    # 2. Check if the notebook has code cells
    code_cells = nb.readCodeCells()
    if len(code_cells) == 0:
        print(f"No code cells in the notebook {nb_path}")
        return nb, "No code cells"

    # 3. Check the language of the notebook. If not Python, we will move it to the error directory
    check_language = get_notebook_language(nb_path)
    if check_language is None:
        return nb, "Cannot read"
    language_name, version, kernel_name = check_language

    version = str(version)
    if version == "unknown" and not 'python3' in kernel_name.lower():
        print(f"Language is not Python 3 ({language_name} {version}) in the notebook {nb_path}")
        return nb, "Non-Python"
    elif not version.startswith('3'):
        print(f"Language is not Python 3 ({language_name} {version}) in the notebook {nb_path}")
        return nb, "Non-Python"
    elif not 'python' in language_name.lower():
        print(f"Language is not Python 3 ({language_name} {version}) in the notebook {nb_path}")
        return nb, "Non-Python"

    # 4. Check if the code cells are valid python code
    for cell in nb_content['cells']:
        if cell['cell_type'] == 'code':
            if cell["source"] is not None:
                cell_content = ''.join(cell['source'].split())
                if cell_content:
                    source_code = getCellSourceCode(cell)
                    try:
                        ast.parse(source_code)
                    except Exception as e:
                        print(f"AST Parsing Error during readNB in the notebook {nb_path}")
                        return nb, "AST Parsing Error"
 
    return nb, "Success"

def addMissingModule(missing_module):
    r =  subprocess.run([f"pip install {missing_module}"], capture_output=True, shell=True)
    if r.returncode == 0:
        print(f"===> Successfully installed {missing_module}")
        return 0
    else:
        print(f"===> Error installing {missing_module}: {r.stderr}")
        return r.returncode

############################################################################################################   

def getCellSourceCode(cell):
    source = ""
    lines = cell['source'].splitlines()
    for line in lines:
        if not line.startswith(("!", "%", "#", "$", "-")):
            source += line + "\n"
    return source.rstrip()

class StaticAST:
    def __init__(self, nb_path):
        self.nb_path = nb_path
        # Store detailed variable usage information
        self.variable_uses = {}  # Format: {cell_number: {variable_name: [scope_ids]}}
        self.variable_defs = {}  # Format: {cell_number: {variable_name: [scope_ids]}}

    def _getNotebookCells(self, notebook_path):
        """
        Read the notebook file and return the code cells
        :param notebook_path: path to the notebook file
        :return: list of code cells
        """
        try:
            with open(notebook_path, 'r', encoding='utf-8') as f:
                notebook = nbformat.read(f, as_version=4)
                cells = notebook['cells']
            return cells
        except Exception as e:
            print(f"CAN'T OPEN NOTEBOOK: {notebook_path}")
            return None

    def _analyzeNotebookCell(self, cell_source, global_scope, cell_number):
        """
        Analyze a single cell in the notebook to build the variable use and def maps.
        :param cell_source: the source code of the cell
        :param global_scope: the global scope dictionary
        :param cell_number: the cell number in the notebook
        :return: tuple of def_list, use_list, global_scope
        """
        try:
            tree = ast.parse(cell_source)
        except Exception as e:
            print(f"Error parsing cell {cell_number} in the notebook {self.nb_path}")
            return None
            
        visitor = ASTNodeVisitor()
        visitor.scopes = [global_scope, {}]
        def_list, use_list = visitor.analyze(tree)
        
        # Update global scope with cell's definitions
        global_scope.update(visitor.scopes[-1])
        
        # Store detailed variable usage information
        self.variable_uses[cell_number] = {}
        self.variable_defs[cell_number] = {}
        
        # Process definitions - def_list is already {scope_id: [variables]} format
        for scope_id, vars_defined in def_list.items():
            for var in vars_defined:
                if var not in self.variable_defs[cell_number]:
                    self.variable_defs[cell_number][var] = []
                self.variable_defs[cell_number][var].append(scope_id)
                
        # Process uses - use_list is already {scope_id: [variables]} format
        for scope_id, vars_used in use_list.items():
            for var in vars_used:
                if var not in self.variable_uses[cell_number]:
                    self.variable_uses[cell_number][var] = []
                self.variable_uses[cell_number][var].append(scope_id)

        return def_list, use_list, global_scope

    def _is_accessible_scope(self, def_scope, use_scope):
        """
        Determine if a definition in def_scope is accessible from use_scope.
        Returns True if the definition is accessible, False otherwise.
        :param def_scope: tuple of (cell_number, scope_id) for the definition
        :param use_scope: tuple of (cell_number, scope_id) for the use
        :return: bool
        """
        def_cell, def_scope_id = def_scope
        use_cell, use_scope_id = use_scope
        
        # Different cells - only global scope definitions are accessible
        if def_cell != use_cell:
            return def_scope_id == 0
            
        # Same cell - check scope hierarchy
        return def_scope_id <= use_scope_id

    def _find_variable_use_scopes(self, variable, cell_number):
        """
        Find all scopes where a variable is used in a specific cell.
        Returns list of scope IDs.
        :param variable: the variable to find
        :param cell_number: the cell number where the variable is used
        :return: list of scope IDs
        """
        if cell_number in self.variable_uses:
            return self.variable_uses[cell_number].get(variable, [])
        return []

    def analyze_notebook(self):
        """
        Analyze the entire notebook to build the variable use and def maps.
        Should be called before finding variable definitions.
        :return: bool
        """
        global_scope = {}
        cells = self._getNotebookCells(self.nb_path)
        if cells is None:
            return False
            
        valid_cell_count = 0
        for cell in cells:
            if cell['cell_type'] == 'code':
                if cell["source"] is None:
                    continue
                    
                cell_content = ''.join(cell['source'].split())
                if cell_content:
                    valid_cell_count += 1
                    source_code = getCellSourceCode(cell)
                    result = self._analyzeNotebookCell(source_code, global_scope, valid_cell_count)
                    
                    if result is None:
                        return False
        return True

    def findOneVariableDefinition(self, target_variable, use_cell):
        """
        Find the definition of a variable used in a cell, considering all scopes where it's used.
        
        Args:
            target_variable: the variable to find
            use_cell: the cell number where the variable is used
            
        Returns:
            tuple: (status, cell_number) where status is one of:
                - "defined_after" if the variable is defined after the use in an accessible scope
                - "undefined" if the variable is never defined in an accessible scope
        """
        if not self.analyze_notebook():  # Make sure we analyze the notebook first
            return None

        # Get all scopes where the variable is used in the specified cell
        use_scopes = self._find_variable_use_scopes(target_variable, use_cell)
        
        if not use_scopes:
            print(f"Warning: No uses found for variable '{target_variable}' in cell {use_cell}")
            return "undefined", -1
            
        # Check each use scope
        later_defs = []
        for use_scope_id in use_scopes:
            use_location = (use_cell, use_scope_id)
            
            # Check all cells for definitions
            for def_cell in self.variable_defs:
                if target_variable in self.variable_defs[def_cell]:
                    for def_scope_id in self.variable_defs[def_cell][target_variable]:
                        def_location = (def_cell, def_scope_id)
                        
                        # If definition is after use and in accessible scope
                        if def_cell > use_cell and self._is_accessible_scope(def_location, use_location):
                            later_defs.append((def_cell, def_scope_id))
        
        if later_defs:
            # Return the earliest accessible definition after use
            earliest_def = min(later_defs, key=lambda x: (x[0], x[1]))
            return "defined_after", earliest_def[0]
            
        return "undefined", -1


############################################################################################################

class ReadNB:
    def __init__(self, nb_path):
        self.nb_path = nb_path
        self.nb_content = None

    def readNB(self):
        """
        Read a notebook file and return the code cells
        :param nb_path: path to the notebook file
        :return: list of code cells
        """
        try:
            with open(self.nb_path, 'r', encoding='utf-8') as f:
                self.nb_content = nbformat.read(f, as_version=4)
                return self.nb_content
        except Exception as e:
            print(f"CAN'T OPEN NOTEBOOK: {e}")
            return None

    def readCodeCells(self):
        """
        Read the code cells in the notebook
        :return: list of code cells
        """
        code_cells = []
        for cell in self.nb_content['cells']:
            if 'cell_type' in cell:
                if cell['cell_type'] == 'code':
                    if not self._is_empty(cell):
                        code_cells.append(cell)

        return code_cells
    
    def _is_empty(self, cell):
        """
        Check if a cell is empty
        :param cell: the cell object
        :return: bool
        """
        if cell["source"] is None:
            return True
        else:
            source_code = ''
            if isinstance(cell['source'], (list, tuple, set)):
                source_code = ''.join(cell['source']).strip().replace(" ", "")
            elif isinstance(cell['source'], str):
                source_code = cell['source'].strip().replace(" ", "")
            
            return source_code == '' # return True if the cell is empty

############################################################################################################

class ReOrderCellsTempNBForDefinedAfter:
    def __init__(self, nb_path, defined_index, undefined_index):
        nb = ReadNB(nb_path)
        self.nb_path = nb_path
        self.defined_index = defined_index - 1
        self.undefined_index = undefined_index - 1

    def swapCells(self, notebook, cell1_index, cell2_index):
        """
        Swap two cells in a notebook
        :param notebook: the notebook object
        :param cell1_index: the index of the first cell
        :param cell2_index: the index of the second cell
        :return: the modified notebook object
        """
        if cell1_index == 0:
            cell_to_move = notebook.cells.pop(cell2_index)
            notebook.cells.insert(0, cell_to_move)
        else:
            cell1_pred = cell1_index - 1
            notebook.cells[cell1_pred], notebook.cells[cell2_index] = notebook.cells[cell2_index], notebook.cells[cell1_pred]

        return notebook

    def getReorderedNBPath(self):
        """
        Reorder the cells in the notebook to move the defined cell after the undefined cell
        :return: the path to the new notebook file
        """
        content = nbformat.read(self.nb_path, as_version=4)
        new_content = self.swapCells(content, self.undefined_index, self.defined_index)

        nb_name = os.path.basename(self.nb_path)
        output_nb_name = nb_name.replace(".ipynb", "_reordered_temp.ipynb")
        new_notebook_path = os.path.join(os.path.dirname(self.nb_path), output_nb_name)

        with open(new_notebook_path, "w", encoding="utf-8") as f:
            nbformat.write(new_content, f)
        return new_notebook_path
