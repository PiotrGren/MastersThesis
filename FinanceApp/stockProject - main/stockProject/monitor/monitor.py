import os
import time
import json
import docker
from pathlib import Path
from datetime import datetime, timezone


# --- Opcjonalnie zapis do DB ---
DB_ENALBED = os.getenv("MONITOR_DB_ENABLED", "0") == "1"
if DB_ENALBED:
    import psycopg2
    import psycopg2.extras
    

# --- Konfirguracja z ENV ---
ENV = os.getenv("ENV", "dev")
LOG_DIR = Path(os.getenv("LOG_DIR", "/logs")).resolve()
JSONL_PATH = LOG_DIR / os.getenv("SYSTEM_METRIC_JSONL", "system_metric.jsonl")

WARMUP_SEC = int(os.getenv("MONITOR_WARMUP_SECONDS", "10"))
INTERVAL_SEC = int(os.getenv("MONITOR_INTERVAL_SECONDS", "2"))

# DB (opcjonalnie)
if DB_ENALBED:
    DB_NAME = os.getenv("DB_NAME")
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", "5432"))
    

# --- Docker Client ---
client = docker.from_env()

def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def append_jsonl(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        
def get_service_name(container) -> str:
    labels = (container.attrs or {}).get("Config", {}).get("Labels", {}) or {}
    return labels.get("com.docker.compose.service") or labels.get("org.opencontainers.image.title") or "unknown"

def calc_cpu_pct(stats: dict) -> float:
    try:
        cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - stats['precpu_stats']['cpu_usage']['total_usage']
        sys_delta = stats['spu_stats'].get('system_cpu_usage', 0) - stats['precpu_stats'].get('system_cpu_usage', 0)
        cores = len(stats['cpu_stats']['cpu_usage'].get('precpu_usage', [])) or 1
        if sys_delta > 0 and cpu_delta > 0:
            return (cpu_delta / sys_delta) * cores * 100.0
    except Exception:
        pass
    return 0.0

def calc_mem(stats: dict) -> tuple[float, float]:
    try:
        used = float(stats["memory_stats"].get("usage", 0))
        limit = float(stats["memory_stats"].get("limit", 1))
        pct = (used / limit * 100.0) if limit > 0 else 0.0
        mb = used / (1024 * 1024)
        return pct, mb
    except Exception:
        return 0.0, 0.0

def calc_net_kb(stats: dict) -> tuple[int, int]:
    try:
        nets = stats.get("networks", {}) or {}
        rx = sum(int(v.get("rx_bytes", 0)) for v in nets.values())
        tx = sum(int(v.get("tx_bytes", 0)) for v in nets.values())
        return rx // 1024, tx // 1024
    except Exception:
        return 0, 0

# --- DB helpers (opcjonalnie) ---
_conn = None
def db_connect():
    global _conn
    if not DB_ENABLED:
        return None
    if _conn is not None:
        return _conn
    _conn = psycopg2.connect(
        dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT
    )
    _conn.autocommit = True
    return _conn

def db_insert_sample(ts_iso: str, cpu_pct: float, mem_pct: float, container_name: str):
    """
    Minimalny insert zgodny z dawnym schematem (stockApp_cpu):
    - timestamp (UTC), cpuUsage (proc), memoryUsage (proc), containerId (nazwa)
    Jeśli masz nowy schemat (service/env/itd.), rozszerz INSERT o te kolumny.
    """
    if not DB_ENABLED:
        return
    try:
        conn = db_connect()
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO "stockApp_cpu" (timestamp, "cpuUsage", "memoryUsage", "containerId") VALUES (%s, %s, %s, %s)',
                (ts_iso, round(cpu_pct, 2), round(mem_pct, 2), container_name),
            )
    except Exception:
        # nie blokuj — JSONL jest źródłem prawdy
        pass

def main():
    time.sleep(WARMUP_SEC)
    while True:
        try:
            containers = client.containers.list()
            ts = now_utc_iso()
            for c in containers:
                try:
                    stats = c.stats(stream=False)
                    cpu_pct = calc_cpu_pct(stats)
                    mem_pct, mem_mb = calc_mem(stats)
                    rx_kb, tx_kb = calc_net_kb(stats)

                    record = {
                        "timestamp": ts,
                        "env": ENV,
                        "container_id": c.short_id,
                        "container_name": c.name,
                        "service_name": get_service_name(c),
                        "cpu_pct": round(cpu_pct, 2),
                        "mem_pct": round(mem_pct, 2),
                        "mem_mb": round(mem_mb, 2),
                        "net_rx_kb": rx_kb,
                        "net_tx_kb": tx_kb,
                    }

                    append_jsonl(JSONL_PATH, record)
                    db_insert_sample(ts, cpu_pct, mem_pct, c.name)

                except Exception:
                    # per-container błąd — log pomijamy, lecimy dalej
                    continue
        except Exception:
            # błąd top-level — spróbuj dalej w kolejnym ticku
            pass

        time.sleep(INTERVAL_SEC)

if __name__ == "__main__":
    main()