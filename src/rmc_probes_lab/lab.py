"""HTTP real em loopback; duas dependências substitutas explicitamente simuladas."""
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.request import Request, build_opener, ProxyHandler
from urllib.error import HTTPError, URLError
from uuid import uuid4

# As chamadas locais não passam por proxies de rede configurados no ambiente.
OPENER = build_opener(ProxyHandler({}))

def request(url):
    try:
        with OPENER.open(Request(url), timeout=1) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)
    except (URLError, TimeoutError, OSError) as error:
        return None, {"erro": type(error).__name__}

def handler_for(dispatch):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            status, payload = dispatch(self.path)
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *args):
            pass
    return Handler

class LocalServer:
    def __init__(self, dispatch):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(dispatch))
        self.server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = Thread(target=self.server.serve_forever, kwargs={"poll_interval":0.02}, daemon=True)
        self.thread.start()
        self.closed = False
    def close(self):
        if not self.closed:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=2)
            self.closed = True
        assert not self.thread.is_alive(), "Servidor local não encerrou."

class ProbeLab:
    """Controla servidores próprios sem localizar nem interromper serviços externos."""
    def __init__(self):
        self.dependencies = {}
        self.urls = {}
        self.rows = []
        self.api = None
        self.generation = 0
        try:
            for name in ("postgresql_simulado", "redis_simulado"):
                self.restore(name)
            self.start_api()
        except BaseException:
            self.close()
            raise
    def restore(self, name):
        self.stop(name)
        def dispatch(path):
            if path == "/health":
                return 200, {"servico": name, "tipo": "substituto HTTP didático"}
            return 404, {"erro": "rota desconhecida"}
        server = LocalServer(dispatch)
        self.dependencies[name] = server
        self.urls[name] = server.url + "/health"
    def stop(self, name):
        server = self.dependencies.pop(name, None)
        if server:
            server.close()
        # Mantém a URL encerrada: a API observa uma falha de comunicação real.
    def start_api(self):
        self.generation += 1
        self.instance = str(uuid4())
        instance = self.instance
        def dispatch(path):
            if path == "/live":
                return 200, {"status":"alive", "instancia": instance}
            if path in ("/ready", "/work"):
                checks = {name: request(url)[0] == 200 for name, url in self.urls.items()}
                healthy = len(checks) == 2 and all(checks.values())
                return (200 if healthy else 503), {
                    "status": "ready" if healthy else "unavailable",
                    "dependencias": checks, "instancia": instance,
                    "rota": path,
                }
            return 404, {"erro":"rota desconhecida"}
        self.api = LocalServer(dispatch)
    def restart_api(self):
        self.api.close()
        self.start_api()
    def measure(self, scenario, expected, failed=None):
        live, live_body = request(self.api.url + "/live")
        ready, ready_body = request(self.api.url + "/ready")
        work, _ = request(self.api.url + "/work")
        assert live == 200, (scenario, live)
        assert ready == expected and work == expected, (scenario, ready, work)
        assert live_body["instancia"] == self.instance == ready_body["instancia"]
        if failed:
            assert ready_body["dependencias"][failed] is False
            other = ({"postgresql_simulado", "redis_simulado"} - {failed}).pop()
            assert ready_body["dependencias"][other] is True
        row = {"cenario":scenario, "liveness":live, "readiness":ready,
               "operacao":work, "api_ativa":self.api.thread.is_alive(),
               "geracao_api":self.generation, "instancia":self.instance,
               "dependencias":ready_body["dependencias"],
               "utc":datetime.now(timezone.utc).isoformat()}
        assert row["api_ativa"]
        self.rows.append(row)
        print(f"{scenario}: live={live}, ready={ready}, work={work}, API ativa={row['api_ativa']}, geração={self.generation}")
        return row
    def close(self):
        if self.api:
            self.api.close()
        for name in list(self.dependencies):
            self.stop(name)
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.close()

def experiment():
    with ProbeLab() as lab:
        initial = lab.measure("01 Saudável", 200)
        lab.stop("postgresql_simulado")
        failed = lab.measure("02 PostgreSQL simulado parado", 503, "postgresql_simulado")
        assert initial["instancia"] == failed["instancia"], "A queda não deve reiniciar a API."
        lab.restart_api()
        restarted = lab.measure("03 API reiniciada com dependência parada",503,"postgresql_simulado")
        assert restarted["instancia"] != failed["instancia"]
        lab.restore("postgresql_simulado")
        restored = lab.measure("04 PostgreSQL simulado recuperado",200)
        assert restored["instancia"] == restarted["instancia"]
        lab.stop("redis_simulado")
        redis_failed = lab.measure("05 Redis simulado parado",503,"redis_simulado")
        assert redis_failed["instancia"] == restored["instancia"]
        lab.restore("redis_simulado")
        final = lab.measure("06 Todas as dependências recuperadas",200)
        assert final["instancia"] == redis_failed["instancia"]
        return lab.rows
