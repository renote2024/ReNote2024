import re
import os
from nb_utils import readNoteBook
import localLLM as llm
import papermill as pm

def papermillExecution(orignal_nb_path):
    """
    Execute the notebook using papermill
    :param orignal_nb_path: The path of the notebook to execute
    """
    notebook_dir = os.path.dirname(orignal_nb_path)
    try:
        pm.execute_notebook(
            input_path = orignal_nb_path,
            output_path = None,
            timeout=300, 
            kernel_name="python3",
            progress_bar=False,
            cwd=notebook_dir
        )
    except Exception as e:
        raise e


class ExecuteNoteBook:
    def __init__(self, nb_path):
        nb, status = readNoteBook(nb_path)
        assert status == "Success", f"{status} in {nb_path}"
        code_cells = nb.readCodeCells()
        self.total_code_cells = len(code_cells)
        self.original_nb_path = nb_path


    def _findErrorCellNumForNameError(self, err):
        """
        Find the cell number where the NameError occurred due to the undefined variable
        :param err: The error message
        :return: The cell number where the NameError occurred
        """
        undefined_var = str(err).split("name '")[1].split("'")[0]
        prompt = f"""Identify the cell number where the NameError occurred due to the 
                    undefined variable '{undefined_var}' in the notebook. No yapping.
                    Give just the cell number between ``` and ```.\n\n{err}"""
        response = llm.localChat(prompt)
        err_cell = response.replace("```", "").strip()
        return err_cell

    def _findErrorCellNumANDType(self, err):
        print(f"\n\n### Error: {err}\n\n")
        cell_num = 0
        err_type = ""

        # Find the error type
        match = re.search(r'\b\w*Error\b', err)
        if match:
            err_type = match.group()
            if "31m" in err_type:
                err_type = err_type.replace("31m", "")
        else:
            err_type = None
            print("no match error")

        if err_type == "NameError":
            cell_num_txt = self._findErrorCellNumForNameError(err).strip()
            try:
                cell_num = int(cell_num_txt)
                print(f"NameError cell number: {cell_num}")
            except:
                match = re.search(r'In\[(\d+)\]', cell_num_txt)
                if match:
                    cell_num = int(match.group(1))
                    print(f"NameError cell number 2: {cell_num}")
                else:
                    match = re.search(r'In \[(\d+)\]', cell_num_txt)
                    if match:
                        cell_num = int(match.group(1))
                        print(f"NameError cell number 3: {cell_num}")
                    else:
                        print("no match index in NameError")
        else:    # Find the cell number where the error occurred
            match = re.search(r'In\[(\d+)\]', err)
            if match:
                cell_num = int(match.group(1))
            else:
                match = re.search(r'In \[(\d+)\]', err)
                if match:
                    cell_num = int(match.group(1))
                else:
                    print("no match index in general")

        # we are not finding all the errors, we will fix it later
        return cell_num, err_type


    def _getErrorTypeFromLLM(self, err):
        """
        Get the error type from the error message using LLM
        :param err: The error message
        :return: The error type
        """
        prompt = f"""Identify the error name from the error report below. Format the response between ``` and ```. 
                It must be a 1-word string and nothing else. No yapping. \n\n{err}"""
        response = llm.localChat(prompt)
        err_type = response.replace("```", "").strip()
        return err_type


    def executeNotebook(self):
        """
        Execute the notebook and return the result that include
        - status: The status of the execution
        - total_code_cells: The total number of code cells in the notebook
        - err_cell_num: The cell number where the error occurred
        """
        try:
            papermillExecution(self.original_nb_path)
            return {
                'status': "executable", 
                'total_code_cells': self.total_code_cells,
                'err_cell_num': self.total_code_cells
            }
        except TimeoutError as e:
            return {
                'status': "TimeoutError", 
                'total_code_cells': self.total_code_cells,
                'err_cell_num': -1
            }
           
        except Exception as e:
            err_cell_num, err_type = self._findErrorCellNumANDType(str(e))

            # CASE 1: ModuleNotFoundError
            if "ModuleNotFoundError" and "No module named" in str(e):
                missing_module = str(e).split("No module named ")[1].replace("'", "")
                if "\n" in missing_module:
                    missing_module = missing_module.replace("\n", "")
                result_dict = {
                    'status': "ModuleNotFoundError",
                    'total_code_cells': self.total_code_cells, 
                    'err_cell_num': err_cell_num,
                    'missing_module': missing_module
                }
                return result_dict

            # CASE 2: Undetectable Error
            elif err_type is None:
                if str(e).find("No space left on device") != -1:
                    print(f'>> No space left on device, error: {str(e)}, exiting...')
                    exit(0)
                print(f'>> Fixing Unknown Error with LLM: {str(e)}')
                err = str(e)
                llm_error_type = self._getErrorTypeFromLLM(err)
                return {
                    'status': f'LLM_ERROR_Extract={llm_error_type}',
                    'total_code_cells': self.total_code_cells, 
                    'err_cell_num': err_cell_num
                }

            # CASE 3: FileNotFoundError
            elif "FileNotFoundError" in str(e) or "PATH_NOT_FOUND" in str(e) or err_type == "FileNotFoundError":
                extracted_path = None
                if "No such file or directory: " in str(e):
                    extracted_path = str(e).split("No such file or directory: ")[1].replace("'", "").strip()
                else:
                    match = re.search(r"FileNotFoundError: (.*?) not found.", str(e))
                    # Extract the matched part
                    if match:
                        extracted_path = match.group(1)
                    else:
                        match = re.search(r"FileNotFoundError: File '(.*?)' does not exist", str(e))
                        if match:
                            extracted_path = match.group(1)
                        match2 = re.search(r"FileNotFoundError: The directory '(.*?)' does not exist", str(e))
                        if match2:
                            extracted_path = match2.group(1)
                        match3 = re.search(r"AnalysisException: [PATH_NOT_FOUND] Path does not exist: file:(.*?).", str(e))
                        if match3:
                            extracted_path = match3.group(1)

                assert extracted_path is not None, "FileNotFoundError path is None"
                return {
                    'status': "FileNotFoundError",
                    'total_code_cells': self.total_code_cells, 
                    'err_cell_num': err_cell_num,
                    'FileNotFoundError_path': extracted_path
                }

            # CASE 4: NameError
            elif "NameError" in str(e) or err_type == "NameError":
                undefined_var = str(e).split("name '")[1].split("'")[0]
                return {
                    'status': "NameError", 
                    'total_code_cells': self.total_code_cells,
                    'err_cell_num': err_cell_num, 
                    'undefined_var': undefined_var
                }

            # CASE 5: Other Errors
            else:
                return {
                    'status': err_type, 
                    'total_code_cells': self.total_code_cells,
                    'err_cell_num': err_cell_num
                }
