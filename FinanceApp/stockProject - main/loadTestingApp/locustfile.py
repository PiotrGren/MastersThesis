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
WAIT_MIN = float(os.getenv("TIME_BETWEEN_REQUESTS_MIN", "0.05"))
WAIT_MAX = float(os.getenv("TIME_BETWEEN_REQUESTS_MAX", "0.2"))

# ile ostatnich kursów dla endpointu rates
RATES_N = int(os.getenv("RATES_N", "3"))

raw = os.getenv("LOCUST_CLASSES", "")
if raw:
    # akceptuj oba formaty, na wszelki wypadek
    raw = raw.replace(":", ",")
    SELECTED_CLASSES = {c.strip() for c in raw.split(",") if c.strip()}
else:
    SELECTED_CLASSES = set()

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
            
        # 3) Airdrop DEBUG
        if self.token and self.__class__.__name__ != "ReadOnlyUser":
            self._post(
                "/api/debug/airdrop/",
                json={},
                name="DEBUG: airdrop",
                auth=True
            )
            
        # 4) Create company
        resp = self._get("/api/companies/", name="COMPANY: list (bootstrap)")
        if resp and resp.status_code == 200:
            companies = resp.json()
            if isinstance(companies, dict):
                companies = companies.get("results", [])
                
            self.company_ids = [c["id"] for c in companies if "id" in c]
            if not self.company_ids:
                self.company_ids = [1]
        else:
            self.company_ids = [1]
        

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
        return self.client.get(
            url,
            headers=self._headers(auth),
            name=name,
            params=params or {},
            context={"userClass": self.request_class, "scenarioId": self.scenario_id},
        )
        
    def _post(self, url: str, json: Dict[str, Any], name: str, auth: bool = True):
        return self.client.post(
            url,
            headers=self._headers(auth),
            name=name,
            json=json,
            context={"userClass": self.request_class, "scenarioId": self.scenario_id},
        )
        
    def _delete(self, url: str, name: str, auth: bool = True):
        return self.client.delete(
            url,
            headers=self._headers(auth),
            name=name,
            context={"userClass": self.request_class, "scenarioId": self.scenario_id},
        )
        


"""class PortfolioMixin:
    def init_portfolio(self):
        # company_id -> amount
        self.portfolio = {}

    def add_stock(self, company_id: int, amount: int):
        self.portfolio[company_id] = self.portfolio.get(company_id, 0) + amount

    def remove_stock(self, company_id: int, amount: int):
        if company_id not in self.portfolio:
            return
        self.portfolio[company_id] -= amount
        if self.portfolio[company_id] <= 0:
            del self.portfolio[company_id]

    def has_stocks(self) -> bool:
        return bool(self.portfolio)

    def random_owned_company(self) -> int | None:
        if not self.portfolio:
            return None
        return random.choice(list(self.portfolio.keys()))
"""


# --------- Profile 1: Read-only (przeglądarka) ---------
class ReadOnlyUser(BaseUser):
    request_class = "ReadOnlyUser"

    @task(3)
    def list_companies(self):
        self._get("/api/companies/", name="COMPANY: list")

    @task(2)
    def read_rates(self):
        self._get("/api/companies/rates/", name="COMPANY: rates", params={"n": RATES_N})

    @task(2)
    def list_buy_offers(self):
        self._get("/api/buyoffers/", name="BUY: list")

    @task(2)
    def list_sell_offers(self):
        self._get("/api/selloffers/", name="SELL: list")

    @task(1)
    def user_stocks(self):
        self._get("/api/user/stocks/", name="USER: stocks")

    @task(1)
    def user_info(self):
        self._get("/api/user/info/", name="USER: info")
    
    """OLD
    @task(2)
    def list_companies(self):
        self._get("/api/companies/", name="COMPANY: list")

    @task(1)
    def read_rates(self):
        self._get(f"/api/companies/rates/", name="COMPANY: rates", params={"n": RATES_N})
    """

# --------- Profile 2: Active user ---------
class ActiveUser(BaseUser):
    request_class = "ActiveUser"

    def on_start(self):
        super().on_start()
        
    def get_owned_stocks(self):
        r = self.client.get(
            "/api/user/stocks/",
            name="USER: stocks",
            headers=self._headers(),
            context={"userClass": self.request_class, "scenarioId": self.scenario_id},
        )
        if r.status_code != 200:
            return []

        data = r.json()
        stocks = data if isinstance(data, list) else data.get("results", [])

        return [
            s for s in stocks
            if s.get("amount", 0) > 0 and s.get("company") is not None
        ]



    @task(3)
    def create_buy_offer(self):
        if not self.company_ids:
            return
        
        company_id = random.choice(self.company_ids)
        amount = random.randint(1, 5)

        self._post(
            "/api/buyoffers/",
            json={"company": company_id, "startAmount": amount, "amount": amount},
            name="BUY: create",
        )


    @task(2)
    def create_sell_offer(self):
        owned = self.get_owned_stocks()

        # NIE MASZ AKCJI → NIE SPRZEDAJESZ
        if not owned:
            return

        stock = random.choice(owned)
        company_id = (
            stock["company"]
            if isinstance(stock["company"], int)
            else stock["company"]["id"]
        )

        max_amt = int(stock["amount"])
        if max_amt <= 0:
            return

        amount = random.randint(1, max_amt)

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
    def cancel_buy_offer(self):
        resp = self._get("/api/buyoffers/", name="BUY: list (for cancel)")
        if resp and resp.status_code == 200:
            offers = resp.json()
            if offers:
                offer = random.choice(offers)
                pk = offer.get("id") or offer.get("pk")
                if not pk:
                    return
                self._delete(f"/api/buyoffers/{pk}/", name="BUY: cancel")

    @task(1)
    def user_info(self):
        self._get("/api/user/info/", name="USER: info")



    """OLD
    class ActiveUser(BaseUser):
    request_class = "ActiveUser"

    @task(2)
    def list_companies(self):
        self._get("/api/companies/", name="COMPANY: list")

    @task(2)
    def create_buy_offer(self):
        company_id = getattr(self, "company_id", 1)
        amount = random.randint(1, 5)
        self._post(
            "/api/buyoffers/",
            json={"company": company_id, "startAmount": amount, "amount": amount},
            name="BUY: create",
        )

    @task(2)
    def create_sell_offer(self):
        company_id = getattr(self, "company_id", 1)
        amount = random.randint(1, 5)
        self._post(
            "/api/selloffers/",
            json={"company": company_id, "startAmount": amount, "amount": amount},
            name="SELL: create",
        )

    @task(1)
    def user_stocks(self):
        self._get("/api/user/stocks/", name="USER: stocks")

    @task(1)
    def user_funds(self):
        self._get("/api/user/funds/", name="USER: funds")
        
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
    """


# --------- Profile 3: Active seller ---------
class ActiveUserWithMarketAnalize(BaseUser):
    request_class = "ActiveUserWithMarketAnalize"

    limit_buy_in_task = 2
    limit_sell_in_task = 3

    def on_start(self):
        super().on_start()
        #self.init_portfolio()
        
    def get_owned_stocks(self):
        r = self.client.get(
            "/api/user/stocks/",
            name="USER: stocks",
            headers=self._headers(),
            context={"userClass": self.request_class, "scenarioId": self.scenario_id},
        )
        if r.status_code != 200:
            return []

        data = r.json()
        stocks = data if isinstance(data, list) else data.get("results", [])

        return [
            s for s in stocks
            if s.get("amount", 0) > 0 and s.get("company") is not None
        ]


    @task(3)
    def market_rates(self):
        self._get(
            "/api/companies/rates/",
            name="COMPANY: rates (analyze)",
            params={"n": RATES_N},
        )

    @task(2)
    def money_check(self):
        self._get("/api/users/money-check/", name="USER: money-check")

    @task(2)
    def do_trading_burst(self):
        # --- BUY ---
        if self.company_ids:
            for _ in range(random.randint(0, self.limit_buy_in_task)):
                company_id = random.choice(self.company_ids)
                amount = random.randint(1, 5)

                resp = self._post(
                    "/api/buyoffers/",
                    json={"company": company_id, "startAmount": amount, "amount": amount},
                    name="BUY: create (analyze)",
                )


        # --- SELL ---
        limit = random.randint(0, self.limit_sell_in_task)
        for _ in range(limit):
            owned = self.get_owned_stocks()
            if not owned:
                break

            stock = random.choice(owned)
            company_id = (
                stock["company"]
                if isinstance(stock["company"], int)
                else stock["company"]["id"]
            )

            max_amt = int(stock["amount"])
            if max_amt <= 0:
                continue

            amount = random.randint(1, max_amt)

            self._post(
                "/api/selloffers/",
                json={
                    "company": company_id,
                    "startAmount": amount,
                    "amount": amount,
                },
                name="SELL: create (analyze)",
            )


    """OLD ActiveSeller
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
    """

class FundsInjectorUser(BaseUser):
    request_class = "FundsInjector"

    @task(1)
    def inject_funds(self):
        self._post(
            "/api/user/funds/",
            json={"money": random.randint(500, 2000)},
            name="USER: funds PUT"
        )

        
        

# Wagi klas – 0 = wyłącz
BaseUser.weight   = 0
ReadOnlyUser.weight  = 4 if _enable("ReadOnlyUser")  else 0
ActiveUser.weight   = 2 if _enable("ActiveUser")   else 0
ActiveUserWithMarketAnalize.weight  = 1 if _enable("ActiveUserWithMarketAnalize")  else 0
FundsInjectorUser.weight = 1 if _enable("FundsInjectorUser") else 0