import os
import json
import uuid
import random
from pathlib import Path
from typing import Dict, Any, Optional

from faker import Faker
from locust import HttpUser, task, between, events

# -------- Konfiguracja --------
LOG_DIR = Path(os.getenv("LOG_DIR", "/logs")).resolve()
CLIENT_JSONL = LOG_DIR / os.getenv("LOCUST_CLIENT_JSONL", "locust_client_log.jsonl")

# wait-time (sekundy)
WAIT_MIN = float(os.getenv("TIME_BETWEEN_REQUESTS_MIN", "0.5"))
WAIT_MAX = float(os.getenv("TIME_BETWEEN_REQUESTS_MAX", "1.5"))

# ile ostatnich kursów dla endpointu rates
RATES_N = int(os.getenv("RATES_N", "3"))

SELECTED_CLASSES = set(os.getenv("LOCUST_CLASSES", "").split(":")) if os.getenv("LOCUST_CLASSES") else set()

def _enable(cls_name: str) -> bool:
    return (not SELECTED_CLASSES) or (cls_name in SELECTED_CLASSES)

fake = Faker()


def append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        # nie blokuj testu obciążeniowego
        pass


# ----- Listener: zapisuj surowe metryki klienta do JSONL (korelacja z X-Request-ID) -----
@events.request.add_listener
def _log_request(request_type, name, response_time, response_length, response, context, exception, **kwargs):
    """
    Zapisujemy to, co widzi klient Locusta (dla diagnostyki i porównań z backendem).
    Główne źródło prawdy to backendowe JSONL — to jest pomocnicze.
    """
    try:
        req_id = None
        status = None
        if response is not None:
            # DRF/Django – nasz middleware dokłada X-Request-ID
            req_id = response.headers.get("X-Request-ID")
            status = response.status_code

        row = {
            "timestamp": None,  # celowo puste — czas weźmiemy z backendowych logów (UTC)
            "client": "locust",
            "request_type": request_type,      # GET/POST/...
            "name": name,                      # 'nazwa' z wywołania self.client.*(..., name="...")
            "response_time_ms": response_time, # co widzi klient
            "response_size": response_length,
            "status": status,
            "request_id": req_id,
            "exception": str(exception) if exception else None,
            "context": context or {},
        }
        append_jsonl(CLIENT_JSONL, row)
    except Exception:
        pass


# --------- Klasa bazowa użytkownika ---------
class BaseUser(HttpUser):
    """
    - Rejestracja + logowanie w on_start()
    - Stały X-Session-ID per user
    - Authorization: Token <token> dla wszystkich wywołań po signIn
    - Dodatkowe nagłówki: X-Scenario-Id, X-Request-Class
    """
    abstract = True
    wait_time = between(WAIT_MIN, WAIT_MAX)

    token: Optional[str] = None
    session_id: str
    username: str
    password: str
    email: str

    # można nadpisać w podklasach
    request_class: str = "BaseUser"
    scenario_id: str = "default"

    def on_start(self):
        # identyfikatory i dane nowego usera
        self.session_id = str(uuid.uuid4())
        self.username = f"{fake.user_name()}_{uuid.uuid4().hex[:8]}"
        self.password = fake.password(length=12)
        self.email = f"{self.username}@example.test"
        
        self.scenario_id = os.getenv("SCENARIO_ID", "default")

        # 1) SignUp
        self._post(
            "/api/signUp/",
            json={
                "username": self.username,
                "password": self.password,
                "email": self.email,
                "name": fake.first_name(),
                "surname": fake.last_name(),
                # opcjonalnie startowe salda – zależnie od Twoich walidacji
                "money": float(random.randint(1000, 8500)),
                "moneyAfterTransactions": 0.0,
                "role": "user",
            },
            name="AUTH: signUp",
            auth=False,
        )
        # 2) SignIn
        resp = self._post(
            "/api/signIn/",
            json={"username": self.username, "password": self.password},
            name="AUTH: signIn",
            auth=False,
        )
        try:
            self.token = resp.json().get("token") if resp is not None else None
        except Exception:
            self.token = None
            
        # 3) Create company
        company_name = fake.company()
        comp_resp = self._post(
            "/api/companies/",
            json={"name": company_name},
            name="COMPANY: create"
        )
        
        self.company_id = None
        if comp_resp is not None and comp_resp.status_code == 201:
            list_resp = self._get("/api/companies/", name="COMPANY: list (bootstrap)")
            if list_resp is not None and list_resp.status_code == 200:
                try:
                    companies = list_resp.json()
                    for c in companies:
                        if c.get("name") == company_name:
                            self.company_id = c.get("id")
                            break
                except Exception:
                    pass
        if not self.company_id:
            self.company_id = 1
        

    # --------- helpery HTTP ---------
    def _headers(self, auth: bool = True) -> Dict[str, str]:
        h = {
            "Content-Type": "application/json",
            "X-Session-ID": self.session_id,
            "X-Scenario-Id": self.scenario_id,
            "X-Request-Class": self.request_class,
        }
        if auth and self.token:
            h["Authorization"] = f"Token {self.token}"
        return h

    def _get(self, url: str, name: str, auth: bool = True, params: Optional[Dict[str, Any]] = None):
        return self.client.get(url, headers=self._headers(auth), name=name, params=params or {}, context={"userClass": self.request_class})

    def _post(self, url: str, json: Dict[str, Any], name: str, auth: bool = True):
        return self.client.post(url, headers=self._headers(auth), name=name, json=json, context={"userClass": self.request_class})

    def _delete(self, url: str, name: str, auth: bool = True):
        return self.client.delete(url, headers=self._headers(auth), name=name, context={"userClass": self.request_class})


# --------- Profile 1: Read-only (przeglądarka) ---------
class ReadOnlyUser(BaseUser):
    request_class = "ReadOnlyUser"

    @task(2)
    def list_companies(self):
        self._get("/api/companies/", name="COMPANY: list")

    @task(1)
    def read_rates(self):
        self._get(f"/api/companies/rates/", name="COMPANY: rates", params={"n": RATES_N})


# --------- Profile 2: Active buyer ---------
class ActiveBuyer(BaseUser):
    request_class = "ActiveBuyer"

    @task(3)
    def create_buy_offer(self):
        #company_id = random.randint(1, 10)
        company_id = getattr(self, "company_id", 1)
        #max_price = round(random.uniform(10, 50), 2)
        amount = random.randint(1, 5)

        self._post(
            "/api/buyoffers/",
            json={
                "company": company_id,
                "startAmount": amount,
                "amount": amount,
            },
            name="BUY: create",
        )

    @task(1)
    def list_buy_offers(self):
        self._get("/api/buyoffers/", name="BUY: list")


# --------- Profile 3: Active seller ---------
class ActiveSeller(BaseUser):
    request_class = "ActiveSeller"

    @task(3)
    def create_sell_offer(self):
        #company_id = random.randint(1, 10)
        company_id = getattr(self, "company_id", 1)
        #min_price = round(random.uniform(10, 50), 2)
        amount = random.randint(1, 5)

        self._post(
            "/api/selloffers/",
            json={
                "company": company_id,
                "startAmount": amount,
                "amount": amount,
            },
            name="SELL: create",
        )

    @task(1)
    def list_sell_offers(self):
        self._get("/api/selloffers/", name="SELL: list")
        
        

# Wagi klas – 0 = wyłącz
BaseUser.weight   = 0
ReadOnlyUser.weight  = 1 if _enable("ReadOnlyUser")  else 0
ActiveBuyer.weight   = 1 if _enable("ActiveBuyer")   else 0
ActiveSeller.weight  = 1 if _enable("ActiveSeller")  else 0