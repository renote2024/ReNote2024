from localLLM import localChat as llm
import re

class FixModuleNotFound:
    def __init__(self, module_name):
        self.module_name = module_name

    def _processRawResponse(self, response):
        print(f"Response: {response}")
        module = None
        try:
            for line in response.splitlines():
                if line.strip().startswith("`") and line.strip().endswith("`"):
                    module = line.strip().replace("`", "")
                    if "None" in module:
                        return None
                    else:
                        return module
        except:
            pass

        return None

    def fixModuleNotFound(self):
        prompt = f"""Fix ModuleNotFoundError for module `{self.module_name}`. Provide the exact open-source module name to install using pip, formatted as `module_name`.
                    Format the correct module name exactly between ` and ` in 1 line. If no module is found, return `None`. Do not generate a random module name. No fluff."""
        response = llm(prompt)
        correct_module = self._processRawResponse(response)
        return correct_module
