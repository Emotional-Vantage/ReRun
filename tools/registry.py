class ToolRegistry:
    def __init__(self):
        self.tools = {}

    def register(self, name, input_model, output_model, permission, allowed_phases):
        self.tools[name] = {
            "input_model": input_model,
            "output_model": output_model,
            "permission": permission,
            "allowed_phases": allowed_phases
        }

    def get_tool(self, name):
        return self.tools.get(name)

registry = ToolRegistry()
