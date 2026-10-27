"""Aritmética e interpretação segura de expressões."""
import ast
import math
import operator

OPS = dict(somar=operator.add, subtrair=operator.sub, multiplicar=operator.mul, dividir=operator.truediv)
NODES = {ast.Add: 'somar', ast.Sub: 'subtrair', ast.Mult: 'multiplicar', ast.Div: 'dividir'}

def number(x):
    if type(x) not in (int, float) or not math.isfinite(x):
        raise ValueError('Use números finitos.')
    return x

def calculate(method, params):
    if not isinstance(params, dict):
        raise ValueError('Parâmetros devem ser um objeto.')
    if method == 'expressao':
        if set(params) != {'expressao'}:
            raise ValueError('Informe expressao.')
        return expression(params['expressao'], calculate)
    if method not in OPS:
        raise LookupError('Método inexistente.')
    if set(params) != {'a', 'b'}:
        raise ValueError('Informe a e b.')
    try:
        return number(OPS[method](number(params['a']), number(params['b'])))
    except ZeroDivisionError:
        raise ValueError('Divisão por zero.') from None

def expression(text, invoke):
    if not isinstance(text, str) or not text.strip() or len(text) > 500:
        raise ValueError('Use expressão entre 1 e 500 caracteres.')
    try:
        tree = ast.parse(text.strip(), mode='eval').body
    except (SyntaxError, RecursionError):
        raise ValueError('Expressão inválida.') from None
    if len(list(ast.walk(tree))) > 150:
        raise ValueError('Expressão muito complexa.')
    def validate(n):
        if isinstance(n, ast.Constant):
            number(n.value)
        elif isinstance(n, ast.BinOp) and type(n.op) in NODES:
            validate(n.left)
            validate(n.right)
        elif isinstance(n, ast.UnaryOp) and type(n.op) in (ast.UAdd, ast.USub):
            validate(n.operand)
        else:
            raise ValueError('Use números, parênteses e + - * /.')
    validate(tree)  # Valida toda a árvore antes de chamar a rede.
    def visit(n):
        if isinstance(n, ast.Constant):
            return n.value
        if isinstance(n, ast.UnaryOp):
            v = visit(n.operand)
            return invoke('subtrair', dict(a=0, b=v)) if isinstance(n.op, ast.USub) else v
        return invoke(NODES[type(n.op)], dict(a=visit(n.left), b=visit(n.right)))
    return visit(tree)

