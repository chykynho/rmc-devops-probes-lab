# Laboratório de liveness e readiness

José Francisco Alves dos Santos · RMC AI Labs

Uma API HTTP local atende três rotas: `/live`, `/ready` e `/work`. Duas dependências HTTP substitutas representam, de forma explicitamente simulada, serviços necessários de PostgreSQL e Redis. Elas não implementam os protocolos nem executam esses bancos.

O experimento inicia os servidores, interrompe cada dependência, mede as respostas e restaura o serviço. A interrupção fecha o servidor local: a API observa uma falha real de comunicação HTTP, em vez de receber um número de status preparado no notebook. A rota `/work` exige as mesmas dependências que a readiness. O identificador da API permite conferir quando houve um reinício.

## Preparação no WSL2 com VS Code

Extraia o pacote e abra a pasta `devops_probes_lab` no VS Code conectado ao WSL2 Ubuntu. Execute os comandos no terminal dessa pasta, um por linha:

```bash
conda create -n devops-probes python=3.12 -y
conda activate devops-probes
python -m pip install .
python -m ipykernel install --user --name devops-probes --display-name "Python 3.12 (devops-probes)"
python --version
python -c "import sys; import rmc_probes_lab; print(sys.executable); print('Pacote importado com sucesso')"
```

As dependências estão exclusivamente no pyproject.toml. A lógica da simulação usa a biblioteca padrão Python. ipykernel prepara a execução no VS Code.

Abra `notebooks/Laboratorio_Liveness_Readiness_Quedas.ipynb`. Selecione **Select Kernel → Python Environments → Python 3.12 (devops-probes)**. Confira Python 3.12 na primeira célula e execute todas as células em ordem. Não confunda saídas salvas com a sua nova execução. Ao terminar, salve o notebook atualizado.

Para repetir, execute todas as células novamente. A função do experimento fecha os servidores locais mesmo quando uma verificação falha. As portas são escolhidas pelo sistema operacional; não há porta fixa nem acesso a serviços externos.

## Resultado a conferir

| Etapa | Liveness | Readiness | Operação |
|---|---:|---:|---:|
| Saudável | 200 | 200 | 200 |
| PostgreSQL simulado parado | 200 | 503 | 503 |
| API reiniciada com dependência parada | 200 | 503 | 503 |
| PostgreSQL simulado recuperado | 200 | 200 | 200 |
| Redis simulado parado | 200 | 503 | 503 |
| Tudo recuperado | 200 | 200 | 200 |

O reinício manual muda a instância da API. A queda e a recuperação de cada dependência mantêm a instância. Isso demonstra o contrato HTTP e a insuficiência do reinício para recuperar uma dependência que continua parada.

## Arquivos gerados

Em `artifacts/`: `resultados.csv`, `evidencias.json` e `resumo.html`. Os arquivos são substituídos pela próxima execução. Faça uma cópia quando quiser preservar uma execução específica. O JSON registra hashes do código e do notebook sem saídas, versão Python e horário UTC. A pasta `examples/execucao_referencia/` preserva a execução entregue.

## Limites e relação com Kubernetes

Esta aplicação didática é independente do CRM privado. Não usa FastAPI nem reutiliza o código do laboratório histórico. Os códigos HTTP reproduzem o contrato descrito no checkpoint técnico.

Este experimento não executa Kubernetes, PostgreSQL ou Redis reais. Não comprova a remoção de endpoints de um Service, o estado Ready de um Pod nem o reinício pelo kubelet. Esses comportamentos do carrossel são fundamentados na documentação oficial e no registro histórico. Para validá-los por execução, é necessário um laboratório separado com cluster local e bancos reais, ainda pendente. `http.server` é usado apenas como servidor didático local.

Documentação oficial consultada:
- https://kubernetes.io/docs/concepts/workloads/pods/probes/
- https://docs.python.org/3.12/library/http.server.html
- https://docs.python.org/3.12/library/urllib.request.html
