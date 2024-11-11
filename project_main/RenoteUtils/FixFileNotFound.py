import os 
from nbconvert import PythonExporter
from nb_utils import readNoteBook
import localLLM as llm
from pathlib import Path
from contextlib import contextmanager


class FixFileNotFound:
    def __init__(self, nb_path, exec_results):
        self.nb_path = nb_path    
        self.missing_file_path = exec_results['FileNotFoundError_path']
        self.missing_file_true_path = None
    
    def getFileName(self):
        return self.missing_file_path

    def getMissingFileTruePath(self):
        return self.missing_file_true_path
    
    @contextmanager
    def temporary_working_directory(self, path):
        """A context manager to temporarily change the working directory."""
        original_directory = os.getcwd()
        os.chdir(path)
        try:
            yield
        finally:
            os.chdir(original_directory)

    def create_temp_dir_and_file(self, missing_path):
        nb_dir = os.path.dirname(self.nb_path)
        try:
            with self.temporary_working_directory(nb_dir):
                return os.path.abspath(os.path.join(nb_dir, missing_path))
        except Exception as e:
            return None

    def write_file(self, file_name, content):
        directory = os.path.dirname(file_name)
        try:
            if directory != "":
                os.makedirs(directory, exist_ok=True)
            with open(file_name, "w", encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            print(f"Error in Writing content to file {file_name}: {e}")
            return False
        return True

    def _getNBSourceCode(self):
        exporter = PythonExporter()
        (source, _) = exporter.from_filename(self.nb_path)
        return source 
    
    def get_file_data(self, response):
        pattern = "```"
        file_content = """"""
        start = False
    
        for line in response.splitlines():
            if pattern in line:
                start = not start
                continue
            if start:
                file_content += line + "\n"
        return file_content


    def create_input_file(self):
        content = ""
        nb_source_code = self._getNBSourceCode()
        time_run = 0
        
        is_file = os.path.splitext(self.missing_file_path)[1] != ""

        self.missing_file_true_path = self.create_temp_dir_and_file(self.missing_file_path)
        if self.missing_file_true_path is None:
            print(f"> Failed to create the temp directory for {self.missing_file_path}")
            return False

        if not is_file:
            print(f">> Generating the missing directory {self.missing_file_true_path}")
            return True

        while True:
            print(f">> Generating content for input file {self.missing_file_path}")
            prompt = f"Generate a sample input file {self.missing_file_path} for the source code below. Format the response with only the needed data between ``` and ```. Just data and No fluff.\n\n{nb_source_code}"
            response = llm.localChat(prompt)
            content = self.get_file_data(response)
            print(f"-----------------------------\n{content}\n-----------------------------")
            time_run += 1
            if content.strip().replace(" ", "") != "":
                break
            if time_run == 3:
                break
                
        if self.write_file(self.missing_file_true_path, content) == True:
            print(f"> File created with LLM for {self.missing_file_path}")
            return True
        else:
            print(f"> LLM Failed to create {self.missing_file_path}")
            return False
