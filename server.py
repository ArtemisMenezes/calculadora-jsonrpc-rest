"""Servidor local REST e JSON-RPC 2.0."""
import argparse  # Configura porta.
import json  # Codifica mensagens.
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer  # Fornece transporte HTTP.
from core import calculate, OPS  # Reutiliza aritmética.

def rpc(req):  # Processa chamada ou notificação.
    if not isinstance(req, dict) or req.get('jsonrpc') != '2.0' or not isinstance(req.get('method'), str) or ('id' in req and req['id'] is not None and type(req['id']) not in (str, int, float)):  # Valida envelope.
        return dict(jsonrpc='2.0', id=None, error=dict(code=-32600, message='Invalid Request'))  # Retorna erro padrão.
    reply = dict(jsonrpc='2.0', id=req.get('id'))  # Preserva identificador.
    try:  # Trata método e argumentos.
        method = req['method']  # Obtém método.
        if method not in (*OPS, 'expressao'):  # Restringe métodos públicos.
            raise LookupError('Method not found')  # Sinaliza método ausente.
        params = req.get('params', {})  # Lê argumentos.
        if isinstance(params, list):  # Aceita argumentos posicionais.
            names = ['expressao'] if method == 'expressao' else ['a', 'b']  # Define assinatura.
            if len(params) != len(names):  # Valida aridade.
                raise ValueError('Quantidade de parâmetros inválida.')  # Rejeita chamada inválida.
            params = dict(zip(names, params))  # Nomeia argumentos.
        reply['result'] = calculate(method, params)  # Executa cálculo.
    except LookupError as exc:  # Trata método desconhecido.
        reply['error'] = dict(code=-32601, message=str(exc))  # Define erro RPC.
    except (ValueError, TypeError, OverflowError, RecursionError) as exc:  # Trata parâmetros inválidos.
        reply['error'] = dict(code=-32602, message=str(exc))  # Responde sem derrubar servidor.
    return reply if 'id' in req else None  # Omite resposta a notificações.

def reject_constant(value):  # Impede extensões JSON NaN e Infinity.
    raise ValueError('JSON não finito.')  # Rejeita valor inválido.

class Handler(BaseHTTPRequestHandler):  # Atende HTTP.
    def send(self, status, data):  # Centraliza respostas.
        body = b'' if data is None else json.dumps(data, allow_nan=False).encode()  # Gera JSON estrito.
        self.send_response(status)  # Envia status.
        self.send_header('Content-Type', 'application/json; charset=utf-8')  # Informa formato.
        self.send_header('Content-Length', str(len(body)))  # Delimita corpo.
        self.end_headers()  # Encerra cabeçalhos.
        self.wfile.write(body)  # Transmite resposta.

    def do_POST(self):  # Recebe cálculos por POST.
        is_rpc = self.path == '/rpc'  # Seleciona protocolo.
        try:  # Valida conteúdo recebido.
            size = int(self.headers.get('Content-Length', '0'))  # Lê tamanho.
            if not 0 < size <= 16384:  # Limita corpo.
                self.send(413, dict(error='Corpo vazio ou grande demais.'))  # Informa limite.
                return  # Interrompe processamento.
            if self.headers.get_content_type() != 'application/json':  # Exige JSON.
                self.send(415, dict(error='Use application/json.'))  # Rejeita formato.
                return  # Evita interpretar conteúdo incompatível.
            payload = json.loads(self.rfile.read(size), parse_constant=reject_constant)  # Decodifica corpo.
        except (ValueError, UnicodeError):  # Trata mensagem malformada.
            self.send(200 if is_rpc else 400, dict(jsonrpc='2.0', id=None, error=dict(code=-32700, message='Parse error')) if is_rpc else dict(error='JSON inválido.'))  # Usa erro do protocolo.
            return  # Encerra chamada.
        if is_rpc:  # Processa chamada simples ou lote.
            result = [r for item in payload if (r := rpc(item)) is not None] if isinstance(payload, list) and payload else rpc(payload)  # Exclui notificações.
            self.send(204 if result is None or result == [] else 200, None if result == [] else result)  # Notificações não recebem corpo.
            return  # Finaliza RPC.
        if not self.path.startswith('/api/') or self.path[5:] not in (*OPS, 'expressao'):  # Valida recurso REST.
            self.send(404, dict(error='Rota inexistente.'))  # Retorna recurso ausente.
            return  # Não calcula rota inválida.
        try:  # Executa operação REST.
            self.send(200, dict(result=calculate(self.path[5:], payload)))  # Retorna resultado.
        except (ValueError, TypeError, OverflowError, RecursionError) as exc:  # Trata erro permanente.
            self.send(422, dict(error=str(exc)))  # Cliente não deve repetir.

if __name__ == '__main__':  # Inicializa somente na execução direta.
    parser = argparse.ArgumentParser()  # Define opções.
    parser.add_argument('--port', type=int, default=8000)  # Permite alterar porta.
    args = parser.parse_args()  # Lê opções.
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)  # Escuta localmente.
    print(f'Servidor em http://127.0.0.1:{server.server_port}')  # Mostra endereço.
    try:  # Aguarda interrupção.
        server.serve_forever()  # Atende chamadas.
    except KeyboardInterrupt:  # Trata Ctrl+C.
        pass  # Evita traceback.
    finally:  # Libera recursos.
        server.server_close()  # Fecha socket.

