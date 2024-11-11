from nb_utils import StaticAST, addMissingModule, ReadNB, ReOrderCellsTempNBForDefinedAfter
from ExecuteNoteBook import ExecuteNoteBook
from FixFileNotFound import FixFileNotFound
from FixNameErrorLLM import FixNameErrorLLM
from FixModuleNotFound import FixModuleNotFound
from ast_visit import ASTNodeVisitor

from tqdm import tqdm
from diskcache import Index

import os
import shutil
import pandas as pd
import subprocess
import nbformat
import copy
import ast


def aggregateFileModuleNameFixingResults(all_exec_results):
    total_cell_ex_after_file_fix = 0
    total_cell_ex_after_module_fix = 0
    total_cell_ex_after_name_fix = 0

    total_module_not_found = 0
    total_file_not_found = 0
    total_name_error = 0

    last_name_error_found = None

    all_unique_errors_during_execution = list(set([d['status'] for d in all_exec_results]))
    for i in range(len(all_exec_results) - 1):
        d1 = all_exec_results[i]
        j = i
        d2 = all_exec_results[j]
        for j in range(i + 1, len(all_exec_results)):
            if d2['err_cell_num'] == d1['err_cell_num']:
                d2 = all_exec_results[j]
            else:
                break

        if d1['status'] == 'ModuleNotFoundError':
            total_cell_ex_after_module_fix += (d2['err_cell_num'] - d1['err_cell_num'])
            total_module_not_found += 1
        elif d1['status'] == 'FileNotFoundError':
            total_cell_ex_after_file_fix += (d2['err_cell_num'] - d1['err_cell_num'])
            total_file_not_found += 1
        elif d1['status'] == 'NameError':
            true_cell_count = d2['err_cell_num']
            if d1['NameError_type'] == 'undefined':
                true_cell_count = d2['err_cell_num'] - 1

            increase = true_cell_count - d1['err_cell_num']
            total_cell_ex_after_name_fix += increase
            if increase > 0:
                last_name_error_found = d1
            total_name_error += 1

    results = {
        'total_cell_ex_after_file_fix': total_cell_ex_after_file_fix,
        'total_cell_ex_after_module_fix': total_cell_ex_after_module_fix,
        'total_cell_ex_after_name_fix': total_cell_ex_after_name_fix,
        'all_unique_errors_during_execution': all_unique_errors_during_execution,
        'total_module_not_found': total_module_not_found,
        'total_file_not_found': total_file_not_found,
        'total_name_error': total_name_error,
    }

    if total_cell_ex_after_name_fix <= 0 and last_name_error_found is not None:
        results['last_name_error_found'] = last_name_error_found

    return results


def nbExecutionWithFixingMissingModuleANDInputDataANDNameError(nb_path):
    all_exec_results = []
    missing_files_paths = set()
    missing_files_paths_to_remove = set()
    name_fixed_paths = set()
    installed_modules = set()
    err_in_file_creation = None
    total_module_fixing_llm = 0
    success_module_fixing_llm = 0
    ast_status = []
    name_error_count = 0
    name_err_exec = []
    
    # Initial Execution
    exec_r = ExecuteNoteBook(nb_path).executeNotebook()
    all_exec_results.append(exec_r)

    while True:
        # Case 1: File not found, create the file, and re-run the notebook
        # if the file is already created, then break the loop
        if 'FileNotFoundError_path' in exec_r:
            missing_file_p = exec_r['FileNotFoundError_path']
            print(f'>> Fixing Missing file: {missing_file_p}')
            if missing_file_p in missing_files_paths:
                err_in_file_creation = f'Fix it. File creation problem with {missing_file_p}'
                break

            missing_files_paths.add(missing_file_p)
            f = FixFileNotFound(nb_path, exec_r)
            create_status = f.create_input_file()
            if f.missing_file_true_path is not None:
                missing_files_paths_to_remove.add(f.missing_file_true_path)
            if create_status:
                exec_r = ExecuteNoteBook(nb_path).executeNotebook()
                all_exec_results.append(exec_r)
            else:
                err_in_file_creation = f'Fix it. File creation problem with {missing_file_p}'
                print(f">> File not created. {exec_r['11']}")
                break

        # Case 2: Module not found, install the module and re-run the notebook
        # if the module is already installed OR can't be installed, then break the loop
        elif 'missing_module' in exec_r:
            module_string = exec_r['missing_module'].strip()
            m = module_string.split('.')[0]
            if m not in installed_modules:
                installed_modules.add(m)
                print(f">> ReNote: Fixing Missing module: {m}")
                result_code = addMissingModule(m)
                if result_code != 0:
                    fix_module = FixModuleNotFound(m)
                    correct_module = fix_module.fixModuleNotFound().strip().split('.')[0]
                    total_module_fixing_llm += 1
                    if correct_module is not None:
                        returncode = addMissingModule(correct_module)
                        if returncode == 0:
                            installed_modules.add(correct_module)
                            success_module_fixing_llm += 1
                        else:
                            print(f'>> ReNote: {correct_module} cannot be installed, breaking the loop')
                            break
                exec_r = ExecuteNoteBook(nb_path).executeNotebook()
                all_exec_results.append(exec_r)
            else:
                print(f'>> ReNote: {m} cannot be installed, breaking the loop')
                break

        # Case 3: NameError, fix the error
        elif 'undefined_var' in exec_r:
            
            undefined_var = exec_r['undefined_var']
            undefined_var_cell = exec_r['err_cell_num']

            if name_error_count > 0:
                prev_name_err = name_err_exec[-1]
                if prev_name_err['err_cell_num'] <= undefined_var_cell:
                    break
            # Static AST
            staticAST = StaticAST(nb_path)
            result = staticAST.findOneVariableDefinition(undefined_var, undefined_var_cell)
            print(f"========== Found NameError {undefined_var} in cell {undefined_var_cell} ==========")

            if result is None:
                break
            err_type, defined_cell = result
            exec_r['NameError_type'] = err_type

            # If the variable is undefined, then fix the NameError with LLM
            if err_type == "undefined" or defined_cell == undefined_var_cell:
                n = FixNameErrorLLM(nb_path, undefined_var, undefined_var_cell)
                nb_path = n.fixNameErrorANDGetNewNBPath()
            # If the variable is defined after the cell, then reorder the cells
            elif err_type == "defined_after":
                nb_path = ReOrderCellsTempNBForDefinedAfter(nb_path, defined_cell, undefined_var_cell).getReorderedNBPath()

            print(f"New path generated: {nb_path}")
            ast_status.append(err_type)
            name_fixed_paths.add(nb_path)

            name_err_exec.append(exec_r)
            name_error_count += 1

            # Rerun the notebook
            exec_r = ExecuteNoteBook(nb_path).executeNotebook()
            all_exec_results.append(exec_r)

        # Case 4: No error or other ERR, break the loop
        else:
            break

    # If filepath is generating a directory we should remove that directory as well
    for file_path in missing_files_paths_to_remove:
        if os.path.exists(file_path):
            if os.path.isdir(file_path):
                shutil.rmtree(file_path)
            else:
                os.remove(file_path)

    for name_fixed_path in name_fixed_paths:
        if os.path.exists(name_fixed_path):
            os.remove(name_fixed_path)

    return_ast_status = ""
    if len(ast_status) == 0:
        return_ast_status = "no_undefined"
    elif "undefined" in ast_status and "defined_after" in ast_status:
        return_ast_status = "both"
    elif "undefined" in ast_status:
        return_ast_status = "undefined"
    else:
        return_ast_status = "defined_after"


    return {
        'all_exec_results': all_exec_results,
        'err_in_file_creation': err_in_file_creation,
        'return_ast_status': return_ast_status,
        'total_module_fixing_llm': total_module_fixing_llm,
        'success_module_fixing_llm': success_module_fixing_llm,
        'installed_modules': installed_modules
    }



def checkIfNBIsAlreadyEvaluated(results_cache, nb_path):
    """
    Check if the notebook is already evaluated by checking the cache results
    """
    # print(f"Checking if the notebook {nb_name} is already evaluated")
    if nb_path in results_cache:
        return results_cache[nb_path]
    else:
        return None


def processNB(nb_path, results_cache_path, err_cache_path, resume):
    """
    Process the notebook and return the results, if the notebook is already evaluated then return the cache
    1. Read the notebook and get the code cells
    2. AST analysis: parse the code cells
    3. If AST analysis is not successful, then do the execution
    4. Fix the import error and file error
    5. Aggregate the results
    6. Return the results
    """
    nb_name = os.path.basename(nb_path)
    nb_cache = Index(results_cache_path)
    err_cache = Index(err_cache_path)

    # If resume is 1, then check if the notebook is already evaluated
    if resume > 0:
        res = checkIfNBIsAlreadyEvaluated(nb_cache, nb_name)
        res_err = checkIfNBIsAlreadyEvaluated(err_cache, nb_path)
        if res is not None or res_err is not None:
            print(f"NB {nb_path} is already evaluated, using the cache results")
            return res

    print(f"* Processing NB: {nb_path}")
    nb = ReadNB(nb_path)
    total_code_cells = nb.getTotalCodeCells()
    print(f"* Total code cells: {total_code_cells}")

    final_execution_result_dict = None
    
    result = nbExecutionWithFixingMissingModuleANDInputDataANDNameError(nb_path)
    print(f"Result : {result}")
    all_fix_errors_results = result['all_exec_results']
    file_creation_error = result['err_in_file_creation']
    ast_status = result['return_ast_status']
    total_module_fixing_llm = result['total_module_fixing_llm']
    success_module_fixing_llm = result['success_module_fixing_llm']
    installed_modules = result['installed_modules']

    agg_results = aggregateFileModuleNameFixingResults(all_fix_errors_results)

    if "last_name_error_found" in agg_results:
        last_name_err_found = copy.deepcopy(agg_results['last_name_error_found'])
        last_name_err_found['status'] = 'NameError'
    else:
        result_dict_after_all_fixes = copy.deepcopy(all_fix_errors_results[-1])
        final_execution_result_dict = result_dict_after_all_fixes

    # final_execution_result_dict['Reordering'] = False
    # print(f"* Final Execution Result: {final_execution_result_dict}")

    initial_exec_result_0 = all_fix_errors_results[0]
    paper_results = {}

    # INITIAL EXECUTION
    paper_results['Initial Total Code Cells'] = initial_exec_result_0['total_code_cells']
    paper_results['Initial_Status'] = initial_exec_result_0['status']
    if initial_exec_result_0['err_cell_num'] > 0 and initial_exec_result_0['status'] != "executable":
        paper_results['Initial_max_execute_cells'] = initial_exec_result_0['err_cell_num'] - 1
    else:
        paper_results['Initial_max_execute_cells'] = initial_exec_result_0['err_cell_num']

    # FINAL EXECUTION
    paper_results['Final Total Code Cells'] = final_execution_result_dict['total_code_cells']
    paper_results['Final_Status'] = final_execution_result_dict['status']
    if final_execution_result_dict['err_cell_num'] > 0 and final_execution_result_dict['status'] != "executable":
        paper_results['Final_max_execute_cells'] = final_execution_result_dict['err_cell_num'] - 1
    else:
        paper_results['Final_max_execute_cells'] = final_execution_result_dict['err_cell_num']

    # RESULTS ANALYSIS
    paper_results['Increased_execution_cells'] = paper_results['Final_max_execute_cells'] - paper_results[
        'Initial_max_execute_cells']

    initial_exec_percentage = (paper_results['Initial_max_execute_cells'] / paper_results[
        'Initial Total Code Cells']) * 100
    final_exec_percentage = (paper_results['Final_max_execute_cells'] / paper_results['Final Total Code Cells']) * 100
    paper_results['Increased_exection_percentage'] = final_exec_percentage - initial_exec_percentage
    paper_results = {**paper_results, **agg_results}
    paper_results['FileCreationError (Manual)'] = file_creation_error
    paper_results['nb_path'] = nb_path
    paper_results['total_module_fixing_using_llm'] = total_module_fixing_llm
    paper_results['success_module_fixing_using_llm'] = success_module_fixing_llm
    paper_results['missing_modules'] = installed_modules
    paper_results['ast_status'] = ast_status

    print(f'* For screen {paper_results}')

    nb_cache[nb_name] = paper_results
    return paper_results
