import os
import json
import uuid
import random
import time
from pathlib import Path
from typing import Dict, Any, Optional

from faker import Faker
from locust import HttpUser, task, between, events

# -------- Konfiguracja Środowiska i Logów --------
LOG_DIR = Path(os.getenv("LOG_DIR", "/logs")).resolve()
CLIENT_JSONL = LOG_DIR / os.getenv("LOCUST_CLIENT_JSONL", "locust_client_log.jsonl")

# -------- Konfiguracja Czasowa (Domyślna) --------
# Klasy będą mogły to nadpisywać, aby symulować np. bota vs człowieka
WAIT_MIN = float(os.getenv("TIME_BETWEEN_REQUESTS_MIN", "0.5"))
WAIT_MAX = float(os.getenv("TIME_BETWEEN_REQUESTS_MAX", "2.0"))

# -------- Parametry Aplikacji --------
RATES_N = int(os.getenv("RATES_N", "3"))

# -------- Konfiguracja "Market Behavior Complexity" (Nowość) --------
# Zmienne sterujące realizmem symulacji (szum, sesje, błędy)

# 1. Zarządzanie długością sesji (aby uniknąć nieskończonych logów jednego usera)
SESSION_MIN_TASKS = int(os.getenv("SESSION_MIN_TASKS", "20"))
SESSION_MAX_TASKS = int(os.getenv("SESSION_MAX_TASKS", "150"))

# 2. Prawdopodobieństwo nagłego przerwania sesji (np. zamknięcie karty w przeglądarce)
SUDDEN_LOGOUT_PROB = float(os.getenv("SUDDEN_LOGOUT_PROB", "0.03")) # 3% szans na akcję

# 3. Szum - błędy ludzkie (np. missclick, próba kupna bez analizy itp.)
HUMAN_ERROR_PROB = float(os.getenv("HUMAN_ERROR_PROB", "0.05")) # 5% szans


# -------- Aktywacja Klas --------
raw = os.getenv("LOCUST_CLASSES", "")
if raw:
    raw = raw.replace(":", ",")
    SELECTED_CLASSES = {c.strip() for c in raw.split(",") if c.strip()}
else:
    SELECTED_CLASSES = set()

def _enable(cls_name: str) -> bool:
    return (not SELECTED_CLASSES) or (cls_name in SELECTED_CLASSES)

fake = Faker()


# -------- Helper do zapisu logów --------
def append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


# -------- Listener Zdarzeń --------
@events.request.add_listener
def _log_request(request_type, name, response_time, response_length, response, context, exception, **kwargs):
    """
    Zapisuje to, co widzi klient Locusta (diagnostyka i porównania z backendem).
    """
    try:
        req_id = None
        status_code = None
        
        if response is not None:
            req_id = response.headers.get("X-Request-ID")
            status_code = response.status_code
        elif exception:
            # Locust czasem przypisuje wyjątek, nie dając response
            status_code = 0 

        row = {
            "timestamp": None, 
            "client": "locust",
            "request_type": request_type,
            "name": name,
            "response_time_ms": response_time,
            "response_size": response_length,
            "status": status_code,
            "request_id": req_id,
            "exception": str(exception) if exception else None,
            "context": context or {},
        }
        append_jsonl(CLIENT_JSONL, row)
    except Exception:
        pass

# ======================================================================
# --------- Klasa bazowa użytkownika (BaseUser) ---------
# ======================================================================

class BaseUser(HttpUser):
    """
    Abstrakcyjna klasa bazowa dla wszystkich profili.
    Zarządza:
    - Rejestracją (raz na cykl życia wątku Locusta)
    - Autentykacją i resetowaniem sesji (zmienny X-Session-ID)
    - Licznikiem wykonanych akcji (TTL sesji)
    - Wspólnymi nagłówkami dla AI (X-Scenario-Id, X-Request-Class)
    """
    abstract = True
    wait_time = between(WAIT_MIN, WAIT_MAX)

    # Stan użytkownika
    token: Optional[str] = None
    session_id: str
    username: Optional[str] = None
    password: Optional[str] = None
    email: Optional[str] = None
    company_ids: list = []

    # Liczniki sesji
    task_counter: int = 0
    max_tasks: int = 0

    # Metadane
    request_class: str = "BaseUser"
    scenario_id: str = "default"

    def on_start(self):
        """Inicjalizacja środowiska i pierwsza rejestracja."""
        self.scenario_id = os.getenv("SCENARIO_ID", "default")
        
        # Generujemy dane i konto TYLKO RAZ dla danego "agenta" Locusta
        if not self.username:
            self.username = f"{fake.user_name()}_{uuid.uuid4().hex[:8]}"
            self.password = fake.password(length=12)
            self.email = f"{self.username}@example.test"
            self._sign_up()
            
        # Otwieramy pierwszą sesję roboczą
        self._reset_session(is_sudden=False)


    def _sign_up(self):
        """Fizyczne utworzenie konta w bazie Django."""
        self.client.post(
            "/api/signUp/",
            json={
                "username": self.username,
                "password": self.password,
                "email": self.email,
                "name": fake.first_name(),
                "surname": fake.last_name(),
            },
            name="AUTH: signUp",
            headers={"Content-Type": "application/json"}
        )


    def _reset_session(self, is_sudden: bool = False):
        """
        Główny silnik podziału danych dla modelu AI.
        Zmienia identyfikator sesji i symuluje ponowne zalogowanie (nowy cykl).
        """
        if is_sudden:
            # Symulacja "zerwania połączenia" – usunięcie tokenu i chwila pauzy
            self.token = None
            time.sleep(random.uniform(1.0, 5.0))

        self.session_id = str(uuid.uuid4())
        self.task_counter = 0
        self.max_tasks = random.randint(SESSION_MIN_TASKS, SESSION_MAX_TASKS)
        
        # Ponowne zalogowanie z nowym X-Session-ID
        resp = self.client.post(
            "/api/signIn/",
            json={"username": self.username, "password": self.password},
            name="AUTH: signIn (re-login)" if is_sudden else "AUTH: signIn",
            headers={"Content-Type": "application/json", "X-Session-ID": self.session_id}
        )
        
        try:
            self.token = resp.json().get("token") if resp else None
        except Exception:
            self.token = None

        # Pobranie listy ID firm (cache'owane lokalnie, by nie robić GET za każdym razem)
        if not self.company_ids:
            resp = self._get("/api/companies/", name="COMPANY: list (bootstrap)", count_task=False)
            if resp and resp.status_code == 200:
                data = resp.json()
                companies = data.get("results", data) if isinstance(data, dict) else data
                self.company_ids = [c["id"] for c in companies if "id" in c]
            if not self.company_ids:
                self.company_ids = [1]


    def _check_ttl(self):
        """Podbija licznik akcji. Jeśli przekroczono limit, kończy sesję."""
        self.task_counter += 1
        if self.task_counter >= self.max_tasks:
            self._reset_session(is_sudden=False)


    @task(1)
    def sudden_logout_task(self):
        """
        Dziedziczony task. Wybiera się bardzo rzadko, a nawet jeśli się wybierze, 
        ma tylko kilka procent szans (SUDDEN_LOGOUT_PROB) na faktyczne ubicie sesji.
        Dzięki temu model AI nauczy się "uciętych" wektorów.
        """
        if random.random() < SUDDEN_LOGOUT_PROB:
            self._reset_session(is_sudden=True)


    # ======================================================================
    # --------- Helpery HTTP (z wbudowanym sprawdzaniem TTL) ---------
    # ======================================================================

    def _headers(self, auth: bool = True) -> Dict[str, str]:
        """Buduje nagłówki wymagane przez Middleware i AI."""
        h = {
            "Content-Type": "application/json",
            "X-Session-ID": self.session_id,
            "X-Scenario-Id": self.scenario_id,
            "X-Request-Class": self.request_class,
        }
        if auth and self.token:
            h["Authorization"] = f"Token {self.token}"
        return h

    def _get(self, url: str, name: str, auth: bool = True, params: Optional[Dict[str, Any]] = None, count_task: bool = True):
        if count_task: self._check_ttl()
        return self.client.get(
            url,
            headers=self._headers(auth),
            name=name,
            params=params or {},
            context={"userClass": self.request_class, "scenarioId": self.scenario_id},
        )
        
    def _post(self, url: str, json: Dict[str, Any], name: str, auth: bool = True, count_task: bool = True):
        if count_task: self._check_ttl()
        return self.client.post(
            url,
            headers=self._headers(auth),
            name=name,
            json=json,
            context={"userClass": self.request_class, "scenarioId": self.scenario_id},
        )
        
    def _put(self, url: str, json: Dict[str, Any], name: str, auth: bool = True, count_task: bool = True):
        if count_task: self._check_ttl()
        return self.client.put(
            url,
            headers=self._headers(auth),
            name=name,
            json=json,
            context={"userClass": self.request_class, "scenarioId": self.scenario_id},
        )
        
    def _delete(self, url: str, name: str, auth: bool = True, count_task: bool = True):
        if count_task: self._check_ttl()
        return self.client.delete(
            url,
            headers=self._headers(auth),
            name=name,
            context={"userClass": self.request_class, "scenarioId": self.scenario_id},
        )
    

# ======================================================================
# --------- Klasa 1: WindowShopper (Dawny ReadOnly, ale "brudny") ------
# ======================================================================

class WindowShopper(BaseUser):
    """
    Spędza dużo czasu na czytaniu, symuluje zakupy (calculate), 
    ale NIGDY nie wysyła POST /api/buyoffers/ (nigdy nie finalizuje transakcji).
    """
    request_class = "WindowShopper"
    
    # Człowiek - czyta powoli. Nadpisujemy domyślne szybkie czasy.
    wait_time = between(1.5, 4.0)

    @task(4)
    def read_rates(self):
        self._get("/api/companies/rates/", name="COMPANY: rates", params={"n": RATES_N})

    @task(3)
    def check_portfolio(self):
        self._get("/api/user/stocks/", name="USER: stocks")
        
    @task(2)
    def portfolio_analysis(self):
        # Udaje, że dogłębnie analizuje swój portfel (używane też przez CarefulTrader)
        self._get("/api/user/portfolio-analysis/", name="USER: portfolio-analysis")

    @task(3)
    def simulate_buy(self):
        """Kluczowa zmyłka: Używa POST w kontekście zakupowym, ale to tylko symulacja."""
        if not self.company_ids:
            return
        company_id = random.choice(self.company_ids)
        amount = random.randint(10, 500)
        self._post(
            "/api/buyoffers/calculate/",
            json={"company": company_id, "amount": amount},
            name="BUY: calculate"
        )

    @task(1)
    def add_to_watchlist(self):
        """Kolejna zmyłka: Zapis do bazy (POST), który utrudnia klasyfikację po metodzie HTTP."""
        if not self.company_ids:
            return
        company_id = random.choice(self.company_ids)
        self._post(
            "/api/user/watchlist/",
            json={"company": company_id},
            name="USER: watchlist POST"
        )

    @task(1)
    def change_settings(self):
        """Wprowadza całkowity szum systemowy."""
        self._post(
            "/api/user/settings/", 
            json={"theme": random.choice(["dark", "light", "system"])}, 
            name="USER: settings POST"
        )



# ======================================================================
# --------- Klasa 2: ImpulsiveTrader (Panika i błędy) ------------------
# ======================================================================

class ImpulsiveTrader(BaseUser):
    """
    Działa bardzo szybko. Od razu przechodzi do kupowania, ignorując analizę.
    Często popełnia błędy (brak środków) i chaotycznie zmienia zdanie (edycja/anulowanie).
    """
    request_class = "ImpulsiveTrader"
    
    # Bardzo szybki czas reakcji (panika lub bot)
    wait_time = between(0.1, 0.6)

    @task(5)
    def impulsive_buy(self):
        """Kupuje bez sprawdzania kalkulatora i bez patrzenia na wykresy."""
        if not self.company_ids:
            return
            
        company_id = random.choice(self.company_ids)
        
        # CELOWE WSTRZYKIWANIE BŁĘDÓW: 
        # Czasem strzela ogromnymi kwotami, żeby backend odrzucił to błędem 400 (Brak środków)
        is_mistake = random.random() < HUMAN_ERROR_PROB * 3  # Impulsywny myli się 3x częściej
        amount = random.randint(1000, 5000) if is_mistake else random.randint(1, 10)

        self._post(
            "/api/buyoffers/",
            json={"company": company_id, "startAmount": amount, "amount": amount},
            name="BUY: create"
        )
        
        # Natychmiast po "klliknięciu" nerwowo sprawdza, czy przeszło
        self._get("/api/user/trade-history/", name="USER: trade-history")

    @task(2)
    def chaotic_edit(self):
        """Edytuje swoje oferty całkowicie w ciemno, bez sprawdzania rynku."""
        resp = self._get("/api/buyoffers/", name="BUY: list (for edit)", count_task=False)
        if resp and resp.status_code == 200:
            offers = resp.json()
            if offers:
                offer = random.choice(offers)
                pk = offer.get("id") or offer.get("pk")
                if pk:
                    new_amount = random.randint(1, 20)
                    # Użycie PUT, które zaimplementowaliśmy w backendzie
                    self._put(
                        f"/api/buyoffers/{pk}/",
                        json={"amount": new_amount},
                        name="BUY: update"
                    )

    @task(1)
    def chaotic_cancel(self):
        """Anuluje ofertę krótko po tym, jak ją złożył (zmienił zdanie)."""
        resp = self._get("/api/buyoffers/", name="BUY: list (for cancel)", count_task=False)
        if resp and resp.status_code == 200:
            offers = resp.json()
            if offers:
                offer = random.choice(offers)
                pk = offer.get("id") or offer.get("pk")
                if pk:
                    self._delete(f"/api/buyoffers/{pk}/", name="BUY: cancel")



# ======================================================================
# --------- Klasa 3: CarefulTrader (Analityk) --------------------------
# ======================================================================

class CarefulTrader(BaseUser):
    """
    Analityk. Wykonuje logiczne ciągi akcji. ZERO błędów niedostatecznych środków.
    Zanim cokolwiek kupi, sprawdza kursy, analizę portfela i kalkulator.
    """
    request_class = "CarefulTrader"
    
    # Powolny i rozważny
    wait_time = between(2.0, 6.0)

    @task(3)
    def careful_buy_sequence(self):
        """Żelazna sekwencja z przerwami na 'myślenie'."""
        if not self.company_ids:
            return

        # 1. Sprawdza rynek i portfel
        self._get("/api/companies/rates/", name="COMPANY: rates", params={"n": RATES_N})
        self._get("/api/user/portfolio-analysis/", name="USER: portfolio-analysis")
        
        # 2. Sprawdza swoje fundusze (żeby NIE POPEŁNIĆ BŁĘDU)
        resp = self._get("/api/user/funds/", name="USER: funds")
        funds = 0
        if resp and resp.status_code == 200:
            funds = resp.json().get("money", 0)

        company_id = random.choice(self.company_ids)
        amount = random.randint(1, 5)

        # 3. Kalkuluje (Mock)
        self._post(
            "/api/buyoffers/calculate/",
            json={"company": company_id, "amount": amount},
            name="BUY: calculate"
        )

        # 4. PAUZA - analizuje wynik kalkulatora
        time.sleep(random.uniform(2.0, 5.0))

        # 5. Bezpieczny zakup - kupuje tylko jeśli ma 100% pewności, że go stać
        # Uproszczenie symulacji: zakładamy, że bezpieczny limit to 500
        if funds > 500:
            self._post(
                "/api/buyoffers/",
                json={"company": company_id, "startAmount": amount, "amount": amount},
                name="BUY: create"
            )
            # Sprawdza czy przeszło (logika analityka)
            self._get("/api/user/trade-history/", name="USER: trade-history")

    @task(1)
    def intelligent_edit(self):
        """Edytuje ofertę na podstawie sytuacji na rynku."""
        self._get("/api/companies/rates/", name="COMPANY: rates (for edit)")
        
        resp = self._get("/api/buyoffers/", name="BUY: list (for edit)", count_task=False)
        if resp and resp.status_code == 200:
            offers = resp.json()
            if offers:
                offer = random.choice(offers)
                pk = offer.get("id") or offer.get("pk")
                if pk:
                    # Po namyśle koryguje ofertę o +1 lub -1
                    current_amount = offer.get("amount", 2)
                    new_amount = max(1, current_amount + random.choice([-1, 1]))
                    self._put(
                        f"/api/buyoffers/{pk}/",
                        json={"amount": new_amount},
                        name="BUY: update (intelligent)"
                    )



# ======================================================================
# --------- Klasa 4: IndecisiveTrader (Niezdecydowany / Bot) -----------
# ======================================================================

class IndecisiveTrader(BaseUser):
    """
    Spamuje rynek ofertami i natychmiast je anuluje.
    Kluczowa jest mikroskopijna różnica czasu (delta_t) między POST a DELETE.
    """
    request_class = "IndecisiveTrader"
    
    # Działa stosunkowo szybko
    wait_time = between(0.5, 1.5)

    @task(1)
    def buy_and_cancel_loop(self):
        if not self.company_ids:
            return
            
        company_id = random.choice(self.company_ids)
        
        # WSTRZYKIWANIE BŁĘDU: 20% szans, że przestrzeli z gotówką, 
        # utrudniając AI odróżnienie go od ImpulsiveTradera
        is_mistake = random.random() < 0.2
        amount = random.randint(5000, 10000) if is_mistake else random.randint(1, 3)

        resp = self._post(
            "/api/buyoffers/",
            json={"company": company_id, "startAmount": amount, "amount": amount},
            name="BUY: create"
        )

        # Jeśli jakimś cudem utworzył poprawną ofertę, NATYCHMIAST ją anuluje
        if resp and resp.status_code == 201:
            # Bardzo krótka pauza (ułamek sekundy) - sygnatura bota/niezdecydowanego
            time.sleep(random.uniform(0.1, 0.4))
            
            offer_data = resp.json()
            pk = offer_data.get("id") or offer_data.get("pk")
            if pk:
                self._delete(f"/api/buyoffers/{pk}/", name="BUY: cancel (fast)")




# ======================================================================
# --------- Klasa 5: StrategicHolder (The Sniper) ----------------------
# ======================================================================

class StrategicHolder(BaseUser):
    """
    90% czasu czyta fundamenty. Robi długie przerwy na analizę 'w głowie'.
    Otwiera pozycję tylko wtedy, gdy 'widzi zysk' (50% szans w naszej symulacji).
    Brak użycia endpontów pomocniczych (/calculate/).
    """
    request_class = "StrategicHolder"
    
    # Bardzo powolny, inwestor długoterminowy
    wait_time = between(5.0, 15.0)

    @task(1)
    def sniper_logic(self):
        if not self.company_ids:
            return

        company_id = random.choice(self.company_ids)

        # 1. Sprawdza swój portfel
        self._get("/api/user/stocks/", name="USER: stocks")

        # 2. Sprawdza fundamenty rynkowe (Brak GET /rates!)
        self._get(f"/api/companies/{company_id}/news/", name="COMPANY: news")
        self._get("/api/market/sentiment/", name="MARKET: sentiment")

        # 3. Pierwsza długa cisza (analiza fundamentów poza systemem)
        time.sleep(random.uniform(4.0, 8.0))

        # 4. Skanuje rynek
        self._get("/api/buyoffers/", name="BUY: list (scan market)")
        
        # 5. Druga cisza (analiza OrderBooka 'w głowie')
        time.sleep(random.uniform(3.0, 6.0))

        # 6. Snajperski strzał WARUNKOWY (Tylko jeśli "widzi zysk")
        # Symulujemy to po prostu rzutem monetą (50% szans)
        sees_profit = random.random() > 0.5

        if sees_profit:
            # Oddaje jeden, mocny, przemyślany strzał zdejmujący płynność
            amount = random.randint(50, 200)
            self._post(
                "/api/buyoffers/",
                json={"company": company_id, "startAmount": amount, "amount": amount},
                name="BUY: create (sniper shot)"
            )
            # Potem natychmiast sprawdza historię i kończy
            self._get("/api/user/trade-history/", name="USER: trade-history")
        else:
            # Jeśli nie ma zysku - ODPUSZCZA. (To stworzy Negative Sample dla AI).
            # Odłożenie analizowanej spółki do ulubionych, żeby nie tracić czasu.
            self._post(
                "/api/user/watchlist/",
                json={"company": company_id},
                name="USER: watchlist POST"
            )



# ======================================================================
# --------- Funds Injector & Aktywacja Klas ----------------------------
# ======================================================================

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
WindowShopper.weight    = 4 if _enable("WindowShopper") else 0
ImpulsiveTrader.weight  = 3 if _enable("ImpulsiveTrader") else 0
CarefulTrader.weight    = 3 if _enable("CarefulTrader") else 0
IndecisiveTrader.weight = 2 if _enable("IndecisiveTrader") else 0
StrategicHolder.weight  = 1 if _enable("StrategicHolder") else 0
FundsInjectorUser.weight= 1 if _enable("FundsInjectorUser") else 0