import re
import sys

# --- ETAPA 1: ANALISADOR LÉXICO (LEXER) ---

class Token:
    def __init__(self, type, value):
        self.type = type
        self.value = value

    def __repr__(self):
        return f'Token({self.type}, {repr(self.value)})'

class Lexer:
    def __init__(self, text):
        self.text = text
        self.pos = 0
        self.tokens = []
        self.token_specs = [
            # A ordem é importante, palavras reservadas antes de IDs.
            ('NUMERO_REAL',      r'\d+\.\d+'),
            ('NUMERO_INTEIRO',   r'\d+'),
            ('PALAVRA_RESERVADA',r'(leia|escreva)'),
            ('ID',               r'[a-zA-Z_][a-zA-Z0-9_]*'),
            ('ATRIBUICAO',       r':='),
            ('OPERADOR_SOMA',    r'\+'),
            ('OPERADOR_SUB',     r'-'),
            ('OPERADOR_MULT',    r'\*'),
            ('OPERADOR_DIV',     r'/'),
            ('ABRE_PARENTESES',  r'\('),
            ('FECHA_PARENTESES', r'\)'),
            ('FIM_COMANDO',      r';'),
            ('ESPACO',           r'[ \t\r\n]+'),
            ('ERRO',             r'.'), # Qualquer outro caractere é tratad como um erro
        ]
        self.token_regex = '|'.join(f'(?P<{pair[0]}>{pair[1]})' for pair in self.token_specs)

    def tokenize(self):
        for mo in re.finditer(self.token_regex, self.text):
            kind = mo.lastgroup
            value = mo.group()
            if kind == 'ESPACO':
                continue
            elif kind == 'ERRO':
                raise RuntimeError(f'Caractere inesperado: {value}')
            yield Token(kind, value)

# --- ETAPA 2: ANALISADOR SINTÁTICO (PARSER) E AST ---

# Nós da Árvore Sintática Abstrata (AST)
class AST: pass

class BinOp(AST):
    def __init__(self, left, op, right):
        self.left, self.op, self.right = left, op, right

class Num(AST):
    def __init__(self, token):
        self.token = token
        self.value = token.value

class Var(AST):
    def __init__(self, token):
        self.token = token
        self.value = token.value

class Assign(AST):
    def __init__(self, left, op, right):
        self.left, self.op, self.right = left, op, right

class Read(AST):
    def __init__(self, var_node):
        self.var_node = var_node
        
class Write(AST):
    def __init__(self, expr):
        self.expr = expr

class Program(AST):
    def __init__(self):
        self.children = []

class Parser:
    def __init__(self, tokens):
        self.tokens = list(tokens)
        self.pos = 0

    def current_token(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def advance(self):
        self.pos += 1

    def eat(self, token_type):
        if self.current_token().type == token_type:
            self.advance()
        else:
            raise RuntimeError(f'Erro de sintaxe!!! : esperado {token_type}, encontrado {self.current_token().type}')

    def parse(self):
        program_node = Program()
        while self.current_token() is not None:
            program_node.children.append(self.parse_command())
        return program_node
    
    def parse_command(self):
        token = self.current_token()
        if token.type == 'PALAVRA_RESERVADA' and token.value == 'leia':
            self.eat('PALAVRA_RESERVADA')
            var_node = Var(self.current_token())
            self.eat('ID')
            self.eat('FIM_COMANDO')
            return Read(var_node)
        elif token.type == 'PALAVRA_RESERVADA' and token.value == 'escreva':
            self.eat('PALAVRA_RESERVADA')
            expr_node = self.parse_expression()
            self.eat('FIM_COMANDO')
            return Write(expr_node)
        elif token.type == 'ID':
            return self.parse_assignment()
        else:
            raise RuntimeError("Comando inválido!!!")

    def parse_assignment(self):
        left = Var(self.current_token())
        self.eat('ID')
        op = self.current_token()
        self.eat('ATRIBUICAO')
        right = self.parse_expression()
        self.eat('FIM_COMANDO')
        return Assign(left, op, right)

    def parse_factor(self):
        token = self.current_token()
        if token.type in ('NUMERO_INTEIRO', 'NUMERO_REAL'):
            self.advance()
            return Num(token)
        elif token.type == 'ABRE_PARENTESES':
            self.eat('ABRE_PARENTESES')
            node = self.parse_expression()
            self.eat('FECHA_PARENTESES')
            return node
        elif token.type == 'ID':
            self.advance()
            return Var(token)
        else:
            raise RuntimeError(f"Erro de sintaxe no fator: token inválido {token}")

    def parse_term(self):
        node = self.parse_factor()
        while self.current_token() and self.current_token().type in ('OPERADOR_MULT', 'OPERADOR_DIV'):
            op = self.current_token()
            self.advance()
            node = BinOp(left=node, op=op, right=self.parse_factor())
        return node

    def parse_expression(self):
        node = self.parse_term()
        while self.current_token() and self.current_token().type in ('OPERADOR_SOMA', 'OPERADOR_SUB'):
            op = self.current_token()
            self.advance()
            node = BinOp(left=node, op=op, right=self.parse_term())
        return node


# --- ETAPA 3: GERADOR DE CÓDIGO ---

class CodeGenerator:
    def __init__(self, parser):
        self.ast = parser.parse()
        self.symbol_table = set()

    def generate(self):
        # Percorre a árvore uma vez para encontrar todas as variáveis
        self.collect_variables(self.ast)
        
        # Gera o código C
        code = "#include <stdio.h>\n\n"
        code += "int main() {\n"
        
        # Declara todas as variáveis como float
        if self.symbol_table:
            code += "    float " + ", ".join(sorted(list(self.symbol_table))) + ";\n"
        
        # Gera o código para cada comando no programa
        for node in self.ast.children:
            code += self.visit(node)
            
        code += "    return 0;\n"
        code += "}\n"
        return code

    def collect_variables(self, node):
        if isinstance(node, Assign):
            self.symbol_table.add(node.left.value)
            self.collect_variables(node.right)
        elif isinstance(node, Read):
            self.symbol_table.add(node.var_node.value)
        elif isinstance(node, BinOp):
            self.collect_variables(node.left)
            self.collect_variables(node.right)
        elif isinstance(node, Write):
            self.collect_variables(node.expr)
        elif isinstance(node, Program):
            for child in node.children:
                self.collect_variables(child)
    
    def visit(self, node):
        method_name = f'visit_{type(node).__name__}'
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node):
        raise Exception(f'Nenhum método visit_{type(node).__name__} encontrado')

    def visit_Program(self, node):
        # Já tratado no método generate
        pass

    def visit_Assign(self, node):
        var_name = node.left.value
        return f"    {var_name} = {self.visit(node.right)};\n"
        
    def visit_Read(self, node):
        var_name = node.var_node.value
        return f'    scanf("%f", &{var_name});\n'

    def visit_Write(self, node):
        return f'    printf("%f\\n", {self.visit(node.expr)});\n'

    def visit_BinOp(self, node):
        return f'({self.visit(node.left)} {node.op.value} {self.visit(node.right)})'

    def visit_Num(self, node):
        return node.value

    def visit_Var(self, node):
        return node.value

# --- ETAPA 4: FUNÇÃO PRINCIPAL ---

def main():
    if len(sys.argv) != 2:
        print("Uso: python compilador.py <arquivo_de_entrada>")
        sys.exit(1)

    input_file = sys.argv[1]
    try:
        with open(input_file, 'r') as f:
            source_code = f.read()

        lexer = Lexer(source_code)
        tokens = lexer.tokenize()
        
        parser = Parser(tokens)
        
        generator = CodeGenerator(parser)
        c_code = generator.generate()
        
        print(c_code)

    except (RuntimeError, IndexError) as e:
        print(f"ERRO: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(f"ERRO: Arquivo '{input_file}' não encontrado.", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()