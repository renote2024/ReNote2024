import ast
import builtins

class ASTNodeVisitor(ast.NodeVisitor):
    builtins_names = set(dir(builtins))

    def __init__(self):
        self.scopes = [{}]  # Stack of scopes
        self.current_scope = self.scopes[-1]
        self.def_list = {0: []}  # Initialize global scope (0)
        self.use_list = {0: []}  # Initialize global scope (0)
        self.scope_id = 0
        self.scope_stack = [0]  # Stack to keep track of nested scopes

    def visit_node(self, node):
        method = f'visit_{node.__class__.__name__}'
        visitor = getattr(self, method, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node):
        for child in ast.iter_child_nodes(node):
            self.visit_node(child)

    def visit_Import(self, node):
        for alias in node.names:
            self._add_def(alias.asname or alias.name)

    def visit_ImportFrom(self, node):
        for alias in node.names:
            self._add_def(alias.asname or alias.name)

    def visit_FunctionDef(self, node):
        self._add_def(node.name)
        self._enter_new_scope()
        for arg in node.args.args:
            self._add_def(arg.arg)
        if node.args.vararg:
            self._add_def(node.args.vararg.arg)
        if node.args.kwarg:
            self._add_def(node.args.kwarg.arg)

        # Visit the function body to capture uses
        for stmt in node.body:
            self.visit_node(stmt)

        self._exit_scope()

    def visit_AnnAssign(self, node):
        if isinstance(node.target, ast.Name):
            self._add_def(node.target.id)

        # Visit the annotation and value (if present)
        self.visit_node(node.annotation)
        if node.value:
            self.visit_node(node.value)

    def visit_If(self, node):
        # Visit the test condition
        self.visit_node(node.test)

        # Visit the body of the if statement
        for stmt in node.body:
            self.visit_node(stmt)

        # Visit the else block if it exists
        for stmt in node.orelse:
            self.visit_node(stmt)

    def visit_Lambda(self, node):
        self._enter_new_scope()
        for arg in node.args.args:
            self._add_def(arg.arg)
        self.visit_node(node.body)
        self._exit_scope()

    def visit_ClassDef(self, node):
        self._add_def(node.name)
        self._enter_new_scope()
        for stmt in node.body:
            self.visit_node(stmt)
        self._exit_scope()

    def visit_Global(self, node):
        for name in node.names:
            self.scopes[0][name] = 'global'
            self._propagate_global(name)

    def visit_Nonlocal(self, node):
        for name in node.names:
            self._propagate_nonlocal(name)

    def visit_Try(self, node):
        # Try blocks can introduce new variables in except clauses
        self._enter_new_scope()
        for stmt in node.body:
            self.visit_node(stmt)
        for handler in node.handlers:
            if handler.name:
                self._add_def(handler.name)
            for stmt in handler.body:
                self.visit_node(stmt)
        for stmt in node.orelse:
            self.visit_node(stmt)
        for stmt in node.finalbody:
            self.visit_node(stmt)
        self._exit_scope()

    def visit_With(self, node):
        # With statements can introduce new variables
        self._enter_new_scope()
        for item in node.items:
            if item.optional_vars:
                self.visit_node(item.optional_vars)
        for stmt in node.body:
            self.visit_node(stmt)
        self._exit_scope()

    def visit_comprehension(self, node):
        # List/Set/Dict comprehensions and generator expressions introduce new variables
        self._enter_new_scope()
        self.visit_node(node.target)
        self.visit_node(node.iter)
        for if_clause in node.ifs:
            self.visit_node(if_clause)
        self._exit_scope()

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Store):
            self._add_def(node.id)
        elif isinstance(node.ctx, ast.Load):
            if node.id not in self.builtins_names:
                self._add_use(node.id)
                
    def visit_For(self, node):
        self.visit_node(node.target)
        self.visit_node(node.iter)
        self._enter_new_scope()
        for stmt in node.body + node.orelse:
            self.visit_node(stmt)
        self._exit_scope()

    def visit_While(self, node):
        self.visit_node(node.test)
        self._enter_new_scope()
        for stmt in node.body + node.orelse:
            self.visit_node(stmt)
        self._exit_scope()

    def _enter_new_scope(self):
        self.scope_id += 1
        self.scopes.append({})
        self.current_scope = self.scopes[-1]
        self.scope_stack.append(self.scope_id)
        self.def_list[self.scope_id] = []
        self.use_list[self.scope_id] = []

    def _exit_scope(self):
        self.scopes.pop()
        self.current_scope = self.scopes[-1]
        self.scope_stack.pop()

    def _add_def(self, name):
        self.current_scope[name] = 'defined'
        current_scope_id = self.scope_stack[-1]
        if current_scope_id not in self.def_list:
            self.def_list[current_scope_id] = []
        if name not in self.def_list[current_scope_id]:
            self.def_list[current_scope_id].append(name)

    def _add_use(self, name):
        current_scope_id = self.scope_stack[-1]
        if current_scope_id not in self.use_list:
            self.use_list[current_scope_id] = []
        if name not in self.use_list[current_scope_id]:
            self.use_list[current_scope_id].append(name)

    def _propagate_global(self, name):
        for scope in self.scopes[1:]:
            if name in scope:
                del scope[name]

    def _propagate_nonlocal(self, name):
        for scope in reversed(self.scopes[1:-1]):
            if name in scope:
                scope[name] = 'nonlocal'
                break

    def analyze(self, node):
        self.visit_node(node)
        return self.def_list, self.use_list
