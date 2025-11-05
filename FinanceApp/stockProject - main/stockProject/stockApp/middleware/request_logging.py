import json
import time
import uuid
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from django.conf import settings
from django.db import connection
from django.utils.deprecation import MiddlewareMixin
from django.utils.timezone import now
from django.http import HttpRequest, HttpResponse

from stockApp.models.requestLog import RequestLog
from stockApp.models.errorLog import ErrorLog  # nasze nowe tabele


# --- konfig pomocnicza --------------------------------------------------------

LOG_DIR = Path(getattr(settings, "LOG_DIR", "/logs")).resolve()
REQUEST_JSONL = LOG_DIR / getattr(settings, "REQUEST_LOG_JSONL", "request_log.jsonl")
ERROR_JSONL = LOG_DIR / getattr(settings, "ERROR_LOG_JSONL", "error_log.jsonl")

ENV = getattr(settings, "ENV", "dev")
SERVICE_NAME = getattr(settings, "SERVICE_NAME", "api")
SERVICE_VERSION = getattr(settings, "SERVICE_VERSION", "0.0.0")

# mapowanie ścieżek -> grup akcji (tokeny do modelu)
def group_endpoint(path: str, method: str) -> str:
    p = path.lower()
    if p.startswith("/api/signin") or p.startswith("/api/signup"):
        return "AUTH"
    if p.startswith("/api/companies"):
        return "COMPANY"
    if p.startswith("/api/buyoffers"):
        return "BUY"
    if p.startswith("/api/selloffers"):
        return "SELL"
    if p.startswith("/api/user/"):
        return "USER"
    return f"{method.upper()}"

def _hash(v: str) -> str:
    return hashlib.sha256(v.encode("utf-8")).hexdigest()[:16]

def _safe_int(v: Optional[float]) -> Optional[int]:
    return None if v is None else int(round(v))


# --- middleware ----------------------------------------------------------------

class RequestLoggingMiddleware(MiddlewareMixin):
    """
    1) Nadaje/odczytuje X-Request-ID.
    2) Wymusza pomiar czasu zapytań DB w ramach żądania.
    3) Mierzy total/app/db/response_size.
    4) Zapisuje rekord do RequestLog (DB) + linię JSONL (gotowe pod trening).
    5) Przy 4xx/5xx – dopisuje ErrorLog + JSONL.
    """

    def process_request(self, request: HttpRequest) -> None:
        # 1) Request-ID + Session-ID
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        setattr(request, "request_id", req_id)  # prywatnie na czas żądania
        setattr(request, "_session_id", request.headers.get("X-Session-ID"))

        # 2) Pomiar czasu
        setattr(request, "_t_start", time.perf_counter())

        # 3) DB: licznik i wymuszenie mierzenia czasu zapytań
        setattr(request, "_q_index", len(connection.queries))
        # Django standardowo liczy czasy tylko przy DEBUG=True.
        # Wymuszamy licznik dla bieżącego żądania:
        setattr(request, "_force_debug_cursor_prev", connection.force_debug_cursor)
        connection.force_debug_cursor = True

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        try:
            # może nie być startu (np. błąd przy middlewarach wcześniej)
            t_start = getattr(request, "_t_start", None)
            if t_start is None:
                return self._return_with_header(request, response)

            # --- czasy
            t_total = time.perf_counter() - t_start  # sekundy float
            db_time = self._db_time_for_request(request)
            db_ms = db_time * 1000.0 if db_time is not None else None
            total_ms = t_total * 1000.0
            app_ms = (total_ms - db_ms) if db_ms is not None else total_ms
            app_ms = max(app_ms, 0.0)

            # --- kontekst
            user = getattr(request, "user", None)
            user_id = None
            user_role = None
            if getattr(user, "is_authenticated", False):
                # używamy public_id z CustomUser; jeśli brak – nie wpisujemy
                user_id = getattr(user, "public_id", None)
                user_role = getattr(user, "role", None)

            method = request.method.upper() # type: ignore[reportOptionalMemberAccess]
            path = request.get_full_path()

            # response size (może nie być .content przy streamingu)
            try:
                response_size = len(getattr(response, "content", b"") or b"")
            except Exception:
                response_size = None

            success = 200 <= getattr(response, "status_code", 500) < 400

            # dane klienta bez PII
            ua = request.META.get("HTTP_USER_AGENT", "")
            ip = request.META.get("REMOTE_ADDR", "")
            ua_hash = _hash(ua) if ua else None
            ip_hash = _hash(ip) if ip else None

            # --- przygotowanie rekordu
            payload: Dict[str, Any] = {
                "request_id": getattr(request, "_request_id", None),
                "session_id": getattr(request, "_session_id", None),
                "user_id": str(user_id) if user_id else None,
                "user_role": user_role,
                "timestamp": now().isoformat(),
                "api_method": method,
                "endpoint": path,
                "endpoint_group": group_endpoint(path, method),
                "http_status": getattr(response, "status_code", 0),
                "success": success,
                "latency_ms_total": round(total_ms, 2),
                "app_time_ms": round(app_ms, 2),
                "db_time_ms": round(db_ms, 2) if db_ms is not None else None,
                "queue_time_ms": None,        # jeśli dodasz X-Queue-Time — wypełnimy
                "network_time_ms": None,      # opcjonalnie (total - app - db - queue)
                "response_size": response_size,
                "user_agent_hash": ua_hash,
                "client_ip_hash": ip_hash,
                "service_name": SERVICE_NAME,
                "env": ENV,
                "service_version": SERVICE_VERSION,
                "request_context": {          # surowe parametry przydatne do debug/treningu
                    "headers_subset": {
                        "content_type": request.META.get("CONTENT_TYPE"),
                        "accept": request.META.get("HTTP_ACCEPT"),
                    },
                    "query": request.GET.dict() if hasattr(request, "GET") else {},
                },
                "error_context": None,        # niżej dla 4xx/5xx
            }

            # --- 4xx/5xx → błąd
            if not success:
                msg = None
                try:
                    # DRF Response ma .data
                    data = getattr(response, "data", None)
                    if isinstance(data, dict) and "detail" in data:
                        msg = data.get("detail")
                    elif isinstance(data, dict) and "error" in data:
                        msg = data.get("error")
                except Exception:
                    pass

                payload["error_context"] = {
                    "message": str(msg) if msg else f"HTTP {payload['http_status']}",
                }

                # zapis do ErrorLog (DB) + JSONL
                try:
                    ErrorLog.objects.create(
                        error_id=str(uuid.uuid4()),
                        timestamp=payload["timestamp"],
                        level="ERROR" if payload["http_status"] >= 500 else "WARN",
                        component="api",
                        request_id=payload["request_id"],
                        parent_request_id=None,
                        error_code=str(payload["http_status"]),
                        message=str(msg) if msg else "",
                        stack=None,
                        context={"endpoint": path, "method": method},
                        env=ENV,
                        service_version=SERVICE_VERSION,
                        container_id=payload["container_id"],
                    )
                except Exception:
                    # nie blokujemy odpowiedzi; fallback do pliku
                    pass

                self._append_jsonl(ERROR_JSONL, {
                    "error_id": str(uuid.uuid4()),
                    "timestamp": payload["timestamp"],
                    "level": "ERROR" if payload["http_status"] >= 500 else "WARN",
                    "component": "api",
                    "request_id": payload["request_id"],
                    "error_code": str(payload["http_status"]),
                    "message": payload["error_context"]["message"],
                    "env": ENV,
                    "service_version": SERVICE_VERSION,
                    "container_id": payload["container_id"],
                })

            # --- zapis RequestLog (DB)
            try:
                RequestLog.objects.create(
                    request_id=payload["request_id"],
                    session_id=payload["session_id"],
                    user_id=payload["user_id"],
                    user_role=payload["user_role"],
                    timestamp=payload["timestamp"],
                    api_method=payload["api_method"],
                    endpoint=payload["endpoint"],
                    endpoint_group=payload["endpoint_group"],
                    http_status=payload["http_status"],
                    success=payload["success"],
                    latency_ms_total=payload["latency_ms_total"],
                    app_time_ms=payload["app_time_ms"],
                    db_time_ms=payload["db_time_ms"],
                    queue_time_ms=payload["queue_time_ms"],
                    network_time_ms=payload["network_time_ms"],
                    response_size=payload["response_size"],
                    user_agent_hash=payload["user_agent_hash"],
                    client_ip_hash=payload["client_ip_hash"],
                    service_name=payload["service_name"],
                    container_id=payload["container_id"],
                    env=payload["env"],
                    service_version=payload["service_version"],
                    request_context=payload["request_context"],
                    error_context=payload["error_context"],
                )
            except Exception:
                # nie zabijamy requestu jeśli DB padnie – mamy JSONL jako źródło prawdy
                pass

            # --- zapis JSONL (źródło do trenowania)
            self._append_jsonl(REQUEST_JSONL, payload)

        finally:
            # przywróć ustawienie cursora
            try:
                prev = getattr(request, "_force_debug_cursor_prev", None)
                if prev is not None:
                    connection.force_debug_cursor = prev
            except Exception:
                pass

        return self._return_with_header(request, response)
    
    def process_exception(self, request, exc):
        # minimalny zapis nieobsłużonego wyjątku (500)
        ts = now().isoformat()
        req_id = getattr(request, "_request_id", str(uuid.uuid4()))
        try:
            ErrorLog.objects.create(
                error_id=str(uuid.uuid4()),
                timestamp=ts,
                level="ERROR",
                component="api",
                request_id=req_id,
                parent_request_id=None,
                error_code="500",
                message=str(exc),
                stack={"type": type(exc).__name__},
                context={"path": request.get_full_path(), "method": request.method},
                env=ENV,
                service_version=SERVICE_VERSION,
                container_id=None,
            )
        finally:
            # zwróć None -> Django pójdzie dalej standardową ścieżką obsługi wyjątku (500)
            return None

    # --- helpers ----------------------------------------------------------------

    def _db_time_for_request(self, request: HttpRequest) -> Optional[float]:
        """
        Suma czasu zapytań DB tylko z tego requestu.
        Wspieramy force_debug_cursor, więc działa również gdy DEBUG=False.
        """
        try:
            q_from = getattr(request, "_q_index", 0)
            q: List[Dict[str, Any]] = connection.queries[q_from:]  # type: ignore[index]
            total = 0.0
            for qi in q:
                # Django zapisuje czas jako string
                try:
                    total += float(qi.get("time", 0))
                except Exception:
                    pass
            return total
        except Exception:
            return None

    def _append_jsonl(self, path: Path, obj: Dict[str, Any]) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        except Exception:
            # ostateczny fallback – nic nie robimy, nie blokujemy requestu
            pass

    def _return_with_header(self, request, response):
        try:
            response["X-Request-ID"] = getattr(request, "_request_id", "")
        except Exception:
            pass
        return response
