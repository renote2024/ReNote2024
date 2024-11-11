import localLLM as llm
import nbformat as nbf
from nbconvert import PythonExporter
from nb_utils import readNoteBook
import os
import json
import uuid


class FixNameErrorLLM:
    def __init__(self, nb_path, undefined_var, undefined_var_cell):
        self.nb_path = nb_path
        self.undefined_var = undefined_var
        self.undefined_var_cell = undefined_var_cell

    def _processRawResponse(self, response):
        '''
        Process the raw response from the model to get the code
        :param response: The raw response from the model
        :return: The code in text
        '''

        pattern = "```"
        file_content = """"""
        start = False

        # Process the response to get the code in text
        for line in response.splitlines():
            if line.startswith("#"):
                continue
            if pattern in line:
                start = not start
                continue
            if start:
                file_content += line + "\n"
        
        return file_content

    def _getNBSourceCode(self):
        '''
        Get the source code of the notebook
        :return: The source code of the notebook
        '''

        # Read the notebook
        nb, _ = readNoteBook(self.nb_path)

        # Export the notebook to Python code
        exporter = PythonExporter()
        source, _ = exporter.from_notebook_node(nb.readNB())

        return source 

    def _generateDefinitionCode(self):
        '''
        Generate the code cell containing the definition of the undefined variable
        :return: The new code cell
        '''

        code_in_text = ''''''

        # Get the source code of the notebook
        source_code = self._getNBSourceCode()

        # Generate the prompt
        prompt = f"""Generate code cell containing a definition (not None) for undefined variable {self.undefined_var} in cell {self.undefined_var_cell} of the source code below. 
                Provide the corrected code between ``` and ```. No fluff.\n\n
                {source_code}"""
        
        # Get the response from the model
        response = llm.localChat(prompt)

        # Process the response to get the code
        code_in_text = self._processRawResponse(response)

        # Generate the new cell
        new_cell = {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": code_in_text, #.splitlines(),
            "id": str(uuid.uuid4())
        }

        return new_cell

    
    def fixNameErrorANDGetNewNBPath(self):
        '''
        Fix the NameError in the notebook and return the path of the new notebook
        '''
        # Load the notebook
        with open(self.nb_path, 'r') as f:
            notebook = json.load(f)

        # Generate the new cell containing the definition of the undefined variable
        new_cell = self._generateDefinitionCode()

        # Insert the new cell at the correct position
        notebook['cells'].insert(self.undefined_var_cell - 1, new_cell)
    
        # Save the notebook with the new cell
        output_name = os.path.basename(self.nb_path).replace(".ipynb", "_NameFixed.ipynb")
        nb_dir = os.path.dirname(self.nb_path)
        output_nb_path = os.path.join(nb_dir, output_name)

        with open(output_nb_path, "w", encoding="utf-8") as f:
            json.dump(notebook, f, indent=2)
            print(f"NameError fixed notebook saved to {output_nb_path}")

        return output_nb_path
