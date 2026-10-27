# Calculadora Distribuída com JSON-RPC e HTTP-REST

Projeto de uma calculadora remota que utiliza **JSON-RPC 2.0** e **HTTP-REST** para a comunicação entre cliente e servidor. O sistema realiza as quatro operações básicas e calcula expressões com parênteses, permitindo escolher se a expressão será interpretada no **cliente** ou no **servidor**.

Desenvolvido para a atividade **AT03 — Invocação Remota e Comunicação Indireta**, da disciplina de Sistemas Distribuídos.

### Componentes

| Componente | Arquivo | Função |
|---|---|---|
| **Servidor** | `server.py` | Recebe requisições HTTP, atende os dois protocolos e retorna resultados ou mensagens de erro. |
| **Cliente** | `client.py` | Oferece interface textual, permite escolher o protocolo e implementa Retry no HTTP-REST. |
| **Calculadora** | `core.py` | Implementa as operações e interpreta expressões com validação por árvore sintática (AST), sem utilizar `eval`. |
| **Testes** | `test_calculadora.py` | Verifica operações, expressões, mensagens JSON-RPC e comportamento do Retry. |

### Operações disponíveis

| Operação | Método remoto | Exemplo | Resultado |
|---|---|---|---|
| Soma | `somar` | `10 + 5` | `15` |
| Subtração | `subtrair` | `10 - 5` | `5` |
| Multiplicação | `multiplicar` | `10 * 5` | `50` |
| Divisão | `dividir` | `10 / 5` | `2` |
| Expressão completa | `expressao` | `(10 + 15) * 4` | `100` |

São aceitos parênteses, precedência de operadores, sinais unários e números decimais com ponto.

---

## Pré-requisitos

- **Python 3.10 ou superior**
- Dois terminais: um para o servidor e outro para o cliente

O projeto utiliza somente a **biblioteca padrão do Python**. Não é necessário instalar pacotes com `pip`.

Baixe o repositório ou faça um clone e abra os terminais na pasta que contém `server.py` e `client.py`. Em sistemas nos quais o comando do Python é `python3`, substitua `python` por `python3` nos exemplos.

---

## Como executar

### 1. Iniciar o servidor

No primeiro terminal:

```bash
python server.py
```

O servidor ficará disponível em **http://127.0.0.1:8000** e atenderá os dois protocolos.

### 2. Iniciar um cliente

No segundo terminal, escolha uma das opções.

**HTTP-REST:**

```bash
python client.py --protocol rest
```

**JSON-RPC:**

```bash
python client.py --protocol rpc
```

### 3. Realizar um cálculo

Digite uma operação ou expressão e escolha onde ela será interpretada:

```text
Expressão: (10 + 15) * 4
Interpretar no cliente ou servidor? [cliente/servidor]: cliente
Resultado: 100
```

Digite `sair` para encerrar o cliente. Para encerrar o servidor, pressione **Ctrl+C**.

### Modos de cálculo

| Modo | Funcionamento | Chamadas para `(10 + 15) * 4` |
|---|---|---|
| **cliente** | O cliente interpreta a expressão e chama o servidor para cada operação básica. | `somar(10, 15)` e depois `multiplicar(25, 4)`. |
| **servidor** | O cliente envia a expressão completa; o servidor interpreta e calcula. | Uma chamada a `expressao`. |

Nos dois modos, as operações aritméticas são executadas no servidor.

### Opções de execução

| Programa | Argumento | Padrão | Descrição |
|---|---|---|---|
| Servidor | `--port` | `8000` | Porta de escuta. |
| Cliente | `--protocol` | `rest` | Protocolo: `rest` ou `rpc`. |
| Cliente | `--url` | `http://127.0.0.1:8000` | Endereço do servidor. |
| Cliente | `--attempts` | `4` | Total máximo de tentativas no REST, incluindo a inicial. |
| Cliente | `--timeout` | `3` | Timeout de cada tentativa, em segundos. |

Exemplo com outra porta:

```bash
# Terminal 1
python server.py --port 8001

# Terminal 2
python client.py --protocol rest --url http://127.0.0.1:8001 --attempts 4 --timeout 3
```

---

## Comunicação HTTP-REST

Todas as operações utilizam **POST** com o cabeçalho `Content-Type: application/json`.

| Rota | Corpo da requisição |
|---|---|
| `/api/somar` | `{"a":10,"b":5}` |
| `/api/subtrair` | `{"a":10,"b":5}` |
| `/api/multiplicar` | `{"a":10,"b":5}` |
| `/api/dividir` | `{"a":10,"b":5}` |
| `/api/expressao` | `{"expressao":"(10+15)*4"}` |

Exemplo de resposta para a soma:

```json
{"result": 15}
```

### Política de Retry

O cliente REST utiliza **Exponential Backoff com jitter**: após uma falha transitória, aguarda um intervalo crescente antes de tentar novamente. O jitter acrescenta uma pequena variação aleatória à espera.

Na configuração padrão:

| Tentativa | Espera antes do envio |
|---|---|
| 1ª | Sem espera |
| 2ª | 0,5 s + até 0,1 s de jitter |
| 3ª | 1 s + até 0,1 s de jitter |
| 4ª | 2 s + até 0,1 s de jitter |

A fórmula é `min(8, 0.5 * 2 ** n) + jitter`, com `n` começando em zero. O timeout padrão é de **3 segundos por tentativa**.

O cliente repete falhas de conexão, timeouts e respostas HTTP **408, 429, 500, 502, 503 e 504**. Erros de entrada, como divisão por zero, não são repetidos. A política usa seus próprios intervalos e não interpreta o cabeçalho `Retry-After`.

Como os cálculos não alteram estado, repetir uma requisição não produz efeitos adicionais. O Retry é aplicado apenas ao cliente REST.

---

## Comunicação JSON-RPC

As chamadas são enviadas por **POST** para `/rpc`, com `Content-Type: application/json`.

Exemplo de requisição:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "dividir",
  "params": {"a": 10, "b": 5}
}
```

Resposta:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": 2.0
}
```

Os métodos disponíveis são `somar`, `subtrair`, `multiplicar`, `dividir` e `expressao`. O servidor aceita parâmetros nomeados ou posicionais, chamadas em lote e notificações. Notificações válidas não recebem uma mensagem de resposta; o transporte retorna HTTP 204 sem corpo.

### Tratamento de erros

| Situação | HTTP-REST | JSON-RPC |
|---|---|---|
| JSON malformado | HTTP 400 | Código `-32700` |
| Envelope JSON-RPC inválido | Não se aplica | Código `-32600` |
| Rota ou método inexistente | HTTP 404 | Código `-32601` |
| Parâmetros inválidos ou divisão por zero | HTTP 422 | Código `-32602` |

Erros JSON-RPC são enviados no campo `error` com HTTP 200. No REST, o servidor também retorna HTTP 413 para corpo vazio ou acima de 16 KiB e HTTP 415 para formato incompatível.

---

## Testes

Na pasta do projeto, execute:

```bash
python -m unittest discover -v
```

A suíte contém **cinco testes**, que verificam:

- As quatro operações nos dois protocolos.
- Expressões interpretadas no cliente e no servidor.
- Decomposição em chamadas remotas e rejeição de expressões inválidas.
- Divisão por zero e entradas não permitidas.
- Envelopes JSON-RPC, parâmetros posicionais, lotes e notificações.
- Recuperação após falhas HTTP 503, limite de tentativas em 503/429 e ausência de Retry em HTTP 422.

Os testes de comunicação utilizam servidores HTTP locais em portas temporárias. No teste de Retry, a espera é substituída pelo registro dos intervalos para verificar a política sem atrasar a execução.

---

## O que esperar na execução

1. O **servidor** informa o endereço de escuta e registra as requisições recebidas.
2. O **cliente** solicita uma expressão e o modo de interpretação.
3. Um cálculo válido exibe `Resultado: ...`.
4. Uma entrada como `1 / 0` exibe uma mensagem de erro e permite continuar.
5. Em falhas transitórias no REST, o cliente mostra mensagens como `Retry 2/4: aguardando ...`.

Para demonstrar o Retry manualmente, execute o cliente com o servidor desligado, solicite um cálculo e inicie o servidor durante as esperas.


## Contexto acadêmico

Esta implementação cobre as partes de **JSON-RPC e HTTP-REST** da atividade de Sistemas distribuídos. Ambos os protocolos foram implementados em Python, conforme a liberdade de escolha de linguagem prevista no enunciado.

As linhas de código dos arquivos de comunicação estão comentadas para explicar a montagem das requisições, o tratamento das respostas e o funcionamento do Retry.

O servidor é destinado a demonstrações locais: escuta em `127.0.0.1` e utiliza HTTP sem TLS.

