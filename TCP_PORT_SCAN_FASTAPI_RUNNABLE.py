"""NiceCoding-compatible FastAPI TCP port scanner.
Run only against systems you own or are authorized to test.
"""
import socket
import threading
import time
from fastapi import FastAPI, Query, HTTPException
import uvicorn

app = FastAPI(title="NiceCoding TCP Port Scanner")


def ip_address(host: str):
    try:
        return socket.gethostbyname(host)
    except socket.gaierror:
        return None


def scan_port(ip: str, port: int):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.7)
            if sock.connect_ex((ip, port)) == 0:
                try:
                    service = socket.getservbyport(port, "tcp")
                except OSError:
                    service = "unknown"
                return {"port": port, "state": "open", "service": service}
    except OSError:
        pass
    return None


@app.get("/")
def home():
    return {"status": "running", "docs": "/docs", "endpoint": "/portScanning/"}


@app.get("/health")
def health():
    return {"status": "OK"}


@app.get("/portScanning/")
def port_scanning(
    host: str = Query(..., description="Authorized lab hostname or IP"),
    start_port: int = Query(1, ge=1, le=65535),
    end_port: int = Query(1024, ge=1, le=65535),
):
    if end_port < start_port:
        raise HTTPException(status_code=400, detail="end_port must be >= start_port")
    if end_port - start_port > 2048:
        raise HTTPException(status_code=400, detail="Scan range limited to 2049 ports per request")
    resolved = ip_address(host)
    if not resolved:
        raise HTTPException(status_code=400, detail="Host or IP could not be resolved")

    ports = range(start_port, end_port + 1)
    results = []
    # Small bounded worker pool avoids creating thousands of threads.
    workers = min(64, len(ports))
    lock = threading.Lock()
    def worker(port_list):
        local = []
        for port in port_list:
            result = scan_port(resolved, port)
            if result:
                local.append(result)
        with lock:
            results.extend(local)
    port_list = list(ports)
    chunks = [port_list[i::workers] for i in range(workers)] if workers else []
    threads = [threading.Thread(target=worker, args=(chunk,), daemon=True) for chunk in chunks]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    results.sort(key=lambda item: item["port"])
    return {"host": host, "ip_address": resolved, "scanned": len(port_list), "open_ports": results}


def _start_server():
    config = uvicorn.Config(
        app, host="127.0.0.1", port=8767,
        log_config=None, access_log=False, lifespan="off"
    )
    uvicorn.Server(config).run()


def _port_ready():
    try:
        with socket.create_connection(("127.0.0.1", 8767), timeout=0.25):
            return True
    except OSError:
        return False


if __name__ == "__main__":
    print("NiceCoding FastAPI TCP Port Scanner", flush=True)
    print("Starting local API server...", flush=True)
    threading.Thread(target=_start_server, daemon=True).start()
    for _ in range(40):
        if _port_ready():
            print("SERVER: RUNNING", flush=True)
            print("Home: http://127.0.0.1:8767/", flush=True)
            print("API docs: http://127.0.0.1:8767/docs", flush=True)
            print("Health: http://127.0.0.1:8767/health", flush=True)
            print("Scan: /portScanning/?host=127.0.0.1&start_port=1&end_port=100", flush=True)
            break
        time.sleep(0.25)
    else:
        print("SERVER: FAILED TO START; check port 8767 and app logs.", flush=True)
