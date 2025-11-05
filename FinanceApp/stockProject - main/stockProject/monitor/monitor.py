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

