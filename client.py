"""Clientes REST (com Retry) e JSON-RPC, com interface textual."""
import argparse  # Lê configurações.
import itertools  # Gera identificadores RPC.
import json  # Serializa mensagens.
import random  # Adiciona jitter à espera.
import socket  # Identifica timeouts.
import time  # Realiza espera entre tentativas.
from urllib.request import Request, urlopen  # Envia HTTP.
from urllib.error import HTTPError, URLError  # Distingue erros HTTP e de rede.
from core import expression, number  # Valida expressões e resultados.

class Client:  # Encapsula transporte e protocolo.
    def __init__(self, protocol='rest', url='http://127.0.0.1:8000', attempts=4, timeout=3, sleep=time.sleep):  # Configura política.
        if attempts < 1 or timeout <= 0:  # Valida limites.
            raise ValueError('Tentativas >= 1 e timeout > 0.')  # Impede configuração inválida.
        self.protocol, self.url = protocol, url.rstrip('/')  # Guarda endereço.
        self.attempts, self.timeout, self.sleep = attempts, timeout, sleep  # Guarda limites e espera injetável.
        self.ids = itertools.count(1)  # Gera IDs sequenciais.

    def call(self, method, params):  # Executa uma operação remota.
        rpc = self.protocol == 'rpc'  # Seleciona protocolo.
        ident = next(self.ids)  # Reserva identificador.
        payload = dict(jsonrpc='2.0', id=ident, method=method, params=params) if rpc else params  # Monta envelope.
        request = Request(self.url + ('/rpc' if rpc else '/api/' + method), data=json.dumps(payload, allow_nan=False).encode(), headers={'Content-Type': 'application/json'}, method='POST')  # Prepara POST.
        attempts = 1 if rpc else self.attempts  # Aplica Retry somente ao REST.
        for attempt in range(attempts):  # Limita tentativas totais.
            try:  # Envia requisição com timeout.
                with urlopen(request, timeout=self.timeout) as response:  # Fecha conexão após leitura.
                    data = json.loads(response.read())  # Decodifica resposta.
                break  # Para ao receber resposta válida.
            except HTTPError as exc:  # Trata status HTTP.
                status = exc.code  # Preserva código.
                body = exc.read().decode(errors='replace')  # Lê mensagem de erro.
                exc.close()  # Libera conexão de erro.
                if status not in (408, 429, 500, 502, 503, 504) or attempt + 1 == attempts:  # Não repete erros permanentes nem excede limite.
                    raise ValueError(f'HTTP {status}: {body}') from None  # Mostra causa ao usuário.
            except (URLError, TimeoutError, socket.timeout, ConnectionError) as exc:  # Trata falhas de rede.
                if attempt + 1 == attempts:  # Detecta esgotamento.
                    raise ValueError(f'Falha de rede após {attempts} tentativa(s): {exc}') from None  # Informa falha final.
            delay = min(8, 0.5 * 2 ** attempt) + random.uniform(0, 0.1)  # Calcula espera exponencial limitada com jitter.
            print(f'Retry {attempt + 2}/{attempts}: aguardando {delay:.2f}s')  # Torna política observável.
            self.sleep(delay)  # Aguarda antes da próxima tentativa.
        if not isinstance(data, dict):  # Exige resposta estruturada.
            raise ValueError('Resposta inválida.')  # Rejeita contrato incompatível.
        if rpc and (data.get('jsonrpc') != '2.0' or data.get('id') != ident or ('result' in data) == ('error' in data)):  # Confere envelope e correlação.
            raise ValueError('Resposta JSON-RPC inválida.')  # Impede usar resposta incorreta.
        if 'error' in data:  # Identifica erro remoto.
            raise ValueError(str(data['error']))  # Apresenta erro ao chamador.
        return number(data['result'])  # Valida resultado numérico.

    def evaluate(self, text, mode):  # Escolhe onde interpretar a expressão.
        return expression(text, self.call) if mode == 'cliente' else self.call('expressao', dict(expressao=text))  # Decompõe ou envia integralmente.

if __name__ == '__main__':  # Abre interface textual.
    parser = argparse.ArgumentParser()  # Define opções do cliente.
    parser.add_argument('--protocol', choices=['rest', 'rpc'], default='rest')  # Seleciona protocolo.
    parser.add_argument('--url', default='http://127.0.0.1:8000')  # Define servidor.
    parser.add_argument('--attempts', type=int, default=4)  # Define tentativas totais REST.
    parser.add_argument('--timeout', type=float, default=3)  # Define timeout por tentativa.
    args = parser.parse_args()  # Lê opções.
    client = Client(args.protocol, args.url, args.attempts, args.timeout)  # Constrói cliente.
    print('Digite sair para encerrar. Operadores: + - * / e parênteses.')  # Orienta uso.
    while True:  # Mantém sessão interativa.
        try:  # Trata entrada e falhas de comunicação.
            text = input('Expressão: ').strip()  # Lê operação ou expressão.
            if text.lower() == 'sair':  # Detecta encerramento.
                break  # Sai do laço.
            mode = input('Interpretar no cliente ou servidor? [cliente/servidor]: ').strip()  # Escolhe estratégia.
            if mode not in ('cliente', 'servidor'):  # Valida escolha.
                raise ValueError('Escolha cliente ou servidor.')  # Informa opção inválida.
            print('Resultado:', client.evaluate(text, mode))  # Mostra resultado.
        except (ValueError, KeyError, OSError) as exc:  # Mantém interface após erro.
            print('Erro:', exc)  # Exibe causa.
        except (EOFError, KeyboardInterrupt):  # Permite encerrar pelo teclado.
            break  # Finaliza interface.

