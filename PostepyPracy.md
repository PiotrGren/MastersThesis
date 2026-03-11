# Plan Rozbudowy Środowiska Symulacyjnego: "Market Behavior Complexity"

**Cel:** Wprowadzenie **niejednoznaczności** klas (Class Overlap) oraz **złożoności sekwencyjnej** w celu wyeliminowania trywialnej klasyfikacji (100% accuracy) i wymuszenia na modelu BiLSTM nauki głębokich zależności czasowych.

---

## 1. Rozbudowa Backend (API & Baza Danych)

Aby stworzyć "szarą strefę" zachowań (np. aktywność typu `POST`, która nie jest handlem), system wymaga nowych punktów styku.

### 1.1 Nowe Modele Danych
* **`MarketNews`**: Tabela z wiadomościami rynkowymi powiązanymi z firmami.
    * *Cel:* Umożliwienie użytkownikom strategicznym "czytania" newsów przed decyzją (wydłużenie czasu analizy, zmiana wzorca `GET`).
* **`UserWatchlist`**: Tabela łącząca Użytkownika z Firmą (Relacja M2M).
    * *Cel:* Generowanie ruchu `POST` (zapis do bazy), który nie jest transakcją finansową (mylenie modelu).

### 1.2 Nowe Endpointy API
| Metoda | Endpoint | Opis Funkcjonalny | Cel dla Modelu (AI) |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/buyoffers/calculate/` | Symulacja kosztów (cena + prowizja). Nie tworzy oferty. | Wprowadza `POST` w kontekście zakupowym, który nie kończy się zakupem (mylenie *Active* z *ReadOnly*). |
| `PUT` | `api/buyffers/{id}/` | Aktualizacja ceny/ilości istniejącej oferty kupna. | Sygnalizuje zmianę strategii. Dla `Careful`: optymalizacja portfela. Dla `Impulsive`: niezdecydowanie. |
| `PUT` | `api/sellffers/{id}/` | Aktualizacja ceny/ilości istniejącej oferty sprzedaży. | Jw. Uczy model odróżniać "nową transakcję" od "korekty". |
| `GET` | `/api/user/portfolio-analysis/` | Mock: Zwraca sugestie rebalancingu (np. "Masz za dużo gotówki"). | Silny sygnał dla `CarefulTrader`. Jeśli wystąpi przed PUT/POST, oznacza przemyślaną decyzję, a nie impuls. |
| `POST` | `/api/user/watchlist/` | Dodanie spółki do obserwowanych. | Generuje aktywność "zapisującą" (Write), utrudniając prostą klasyfikację po metodzie HTTP. |
| `GET` | `/api/companies/{id}/news/` | Pobranie newsów dla konkretnej spółki. | Sygnał analizy fundamentalnej (różny od technicznego `/rates`). |
| `POST` | `/api/user/settings/` | Zmiana ustawień konta (np. email, powiadomienia). | Szum - losowe żądania `POST` nieistotne dla handlu. |
| `GET` | `/api/market/sentiment/` | Pobranie ogólnego sentymentu rynku. | Sygnał dla inwestorów strategicznych. |

---

## 2. Profile Behawioralne (Klasy Użytkowników)

Model będzie trenowany na 5 głównych klasach, które zostały zaprojektowane tak, aby ich wektory zachowań częściowo się pokrywały.

### A. `WindowShopper` (Ewolucja ReadOnly)
* **Profil:** "Oglądacz", marzyciel. Sprawdza ceny, symuluje zakupy, ale boi się ryzyka.
* **Zachowanie:**
    * Intensywne użycie `GET /rates` oraz `GET /user/stocks`, `GET /api/companies/`, `GET /api/buyoffers/`, `GET /api/selloffers/`, `GET /api/user/info/`.
    * **Kluczowe zakłócenie:** Często używa `POST /buyoffers/calculate/` (symuluje zakup).
    * Czasem dodaje firmy do obserwowanych (`POST /watchlist`).
    * Czasem zmienia ustawienia (`POST /settings`).
    * **NIGDY** nie finalizuje transakcji (`POST /buyoffers`).
* **Wyzwanie dla modelu:** Odróżnienie sekwencji kończącej się na `calculate` od takiej, która idzie dalej.

### B. `ImpulsiveTrader` (Ewolucja ActiveUser)
* **Profil:** Trader emocjonalny, szybki, nieregularny, popełniający błędy.
* **Zachowanie:**
    * Bardzo krótkie czasy reakcji (`delta_t` < 0.5s).
    * Wchodzi bezpośrednio w `POST /buyoffers` (pomija `calculate`, pomija `rates`).
    * **Wysoki wskaźnik błędów:** Często generuje `400 Bad Request` (Insufficient Funds).
    * **Chaotyczne Anulowanie:** Czasem (ok. 15%) anuluje ofertę po kilku sekundach (jakby zmienił zdanie).
    * **Edycja ofert:** Czasem (rzadko) wykonuje `PUT /offers/{id}`, ale robi to chaotycznie (bez wcześniejszego sprawdzenia rynku), co sugeruje działanie pod wpływem emocji.
* **Wyzwanie dla modelu:** Powiązanie błędów (Error Log) i krótkich czasów z tą klasą.

### C. `CarefulTrader` (Ewolucja MarketAnalize)
* **Profil:** Analityk techniczny. Metodyczny, bezpieczny, powolny.
* **Zachowanie:**
    * Sztywna sekwencja: `GET /rates` $\to$ `GET /user/funds` $\to$ `POST /calculate` $\to$ **Pauza (2-5s)** $\to$ `POST /buyoffers`.
    * **Zero Błędów:** Nigdy nie wysyła zlecenia, jeśli nie ma środków (sprawdza to po stronie klienta).
    * Reszta podobnie jak w ActiveUserWithMarketAnalyze
    * **Inteligentna Edycja:** Używa PUT /offers/{id} do korekty cen, ale zawsze poprzedza to sprawdzeniem GET /rates (reakcja na rynek) lub GET /stocks (rebalancig).
* **Wyzwanie dla modelu:** Wykrycie długich zależności czasowych (Long-Term Dependencies) i braku błędów.

### D. `IndecisiveTrader` (Nowa klasa - "Spammer")
* **Profil:** Bot lub niezdecydowany człowiek spamujący rynek.
* **Zachowanie:**
    * Pętla działania: `POST /buyoffers` $\to$ `DELETE /buyoffers/{id}`.
    * Czas między kupnem, a anulowaniem jest minimalny (ułamki sekund).
    * Rzadko dochodzi do finalizacji transakcji, ale czasem tak.
    * Czasem popełni błąd i wystawi buyoffer generując błąd `400 Bad Request` (Insufficient Funds).
* **Wyzwanie dla modelu:** Wykrycie wzorca "Buy-Cancel" w bardzo krótkim oknie czasowym (odróżnienie od *Impulsive*, który anuluje rzadziej i wolniej).

### E. `StrategicHolder` (Nowa klasa - "Long Term")
* **Profil:** Inwestor fundamentalny. Rzadka aktywność, duży wolumen, chirurgiczna precyzja.
* **Zachowanie:**
    1. Loguje się i sprawdza portfel (`GET /user/stocks`).
    2. Czyta newsy (`GET /companies/{id}/news/`) i sentyment.
    3. **Długa cisza** (analiza danych poza systemem).
    4. Skanowanie Rynku: Pobiera `GET /buyoffers` i `GET /selloffers`.
    5. Druga Cisza: Analizuje Order Book "w głowie".
    6. **Snajperski Strzał:** Dokonuje jednej dużej transakcji (POST), która jest tak dopasowana cenowo, że realizuje się natychmiast (zdejmuje ofertę z rynku). **Wymóg:** Transakcja musi zwiększać wartość portfela (zysk), jak takiej nie znajdzie to w tej turze odpuszcza (nie wystawia ofert, czeka na zmianę rynku).
* **Wyzwanie dla modelu:** Bardzo podobny do `CarefulTrader` (też analizuje), ale nie używa endpointu `/calculate/` ani `/portfolio-analysis/`. Model musi nauczyć się, że sekwencja `GET OrderBook` -> `Silence` -> `Large Trade` to sygnatura `Snajpera/Strategicznego`, w odróżnieniu od `GET` -> `Calculate` -> `Trade` (`Careful`).

---

## 3. Klasy Anomalii (Do detekcji OOD - Out of Distribution)

Te klasy posłużą do testowania zdolności modelu do wykrywania zachowań nietypowych (niepasujących do powyższych 5).

1.  **`MarketManipulator` (Spoofing):**
    * Wystawia serię ogromnych zleceń (np. 10x `POST`), a następnie anuluje je wszystkie naraz (10x `DELETE`) po kilku sekundach. Celem jest manipulacja wykresem głębokości rynku bez zawarcia transakcji.
2.  **`DataScraper` (Złodziej Danych):**
    * Nieludzka szybkość zapytań `GET`.
    * Iteruje sekwencyjnie po ID spółek (`/1/`, `/2/`, `/3/`).
    * Ignoruje endpointy użytkownika (profil, środki).
    * Brak żądań `POST`.

---

## 4. Strategia Wstrzykiwania Szumu (Noise Injection)

Aby dane nie były sterylne, w `locustfile.py` zostaną wprowadzone elementy losowe dla każdej klasy:

1.  **Human Error (5% szans):** Każdy użytkownik (nawet *CarefulTrader*) ma małą szansę na "missclick" – kliknięcie w zły endpoint lub próbę kupna bez środków.
2.  **Jitter Czasowy:** Odejście od sztywnych `wait_time`. Boty będą miały stałe czasy, a "ludzkie" klasy (WindowShopper, Impulsive) – rozkład wykładniczy opóźnień.
3.  **Network Lag:** Symulacja losowych opóźnień sieciowych (spowolnione requesty), aby model nie polegał wyłącznie na idealnym `latency`.

---

## 5. Macierz Cech Dystynktywnych

Tabela pokazuje, dlaczego model będzie musiał użyć mechanizmu uwagi (Attention) i LSTM, zamiast prostej statystyki.

| Klasa | Używa POST/PUT? | Generuje Błędy? | Anuluje Oferty? | Używa Calc/Analysis? | Cechy Czasowe (Delta T) | Sygnatura Unikalna |
| :--- | :---: | :---: | :---: | :--- | :--- | :--- |
| **WindowShopper** | TAK | Rzadko (raczej nie) | NIE | TAK (Calc) | Średnie, losowe | Używa `POST` (Calc), ale nigdy `Trade`. |
| **ImpulsiveTrader** | TAK (Trade/Edit) | **TAK (Często)** | Czasem | NIE | Bardzo małe | Ignoruje endpointy analityczne. |
| **CarefulTrader** | TAK (Trade/Edit) | **NIGDY** | Rzadko | TAK (Calc/Portfolio) | **Duże (analiza)** | Sekwencja `Rates -> Funds -> Calc -> Buy`. |
| **IndecisiveTrader**| TAK (Trade) | Czasem | **PRAWIE ZAWSZE (Szybko)** | NIE | Małe | Pętla `Buy -> Cancel`. |
| **StrategicHolder** | TAK (Large Trade) | Rzadko | NIE | NIE (liczy "w głowie") | Zmienne (czyta newsy) | Czyta `News`. Rebalancing portfela. |

---

## 6. Plan Wolumenu Danych

* **Docelowa liczba sesji:** 5 000 - 10 000 unikalnych sesji.
* **Szacowana liczba logów:** 1.5 mln - 3.0 mln wierszy w `request_log.jsonl`.
* **Długość symulacji:** ok. 2-3 godziny ciągłego obciążenia przy zmiennych parametrach `SPAWN_RATE`.



---

# Realizacja założeń i modyfikacje systemu (Aktualizacja - Marzec 2026)

W oparciu o powyższy plan rozbudowy środowiska symulacyjnego, z sukcesem zrealizowano kluczowe modyfikacje aplikacji oraz przeprowadzono nową, zaawansowaną symulację ruchu. Podjęte działania miały na celu wyeliminowanie trywialności danych oraz wymuszenie na modelu sztucznej inteligencji faktycznej analizy zależności czasowych i sekwencyjnych. 

Główne kroki podjęte w ramach tego etapu to:

## 1. Wdrożenie złożoności behawioralnej i szumu w API (Backend)
* **Rozbudowa interfejsu API:** Zgodnie z planem, wprowadzono nowe endpointy symulujące działania nietransakcyjne, takie jak kalkulator ofert (`/api/buyoffers/calculate/`) oraz system obserwowanych spółek (`/api/user/watchlist/`). Pozwoliło to na generowanie ruchu typu `POST`, który nie jest bezpośrednio powiązany z handlem.
* **Iniekcja realistycznych błędów (Negative Samples):** Zmodyfikowano logikę aplikacji tak, aby rejestrowała niepoprawne żądania (np. brak wystarczających środków na koncie). Błędy walidacyjne (status HTTP 400) są poprawnie odkładane w logach (`error_log.jsonl`) i stanowią obecnie kluczową cechę dystynktywną m.in. dla klasy impulsywnej.
* **Zarządzanie cyklem życia oferty:** Umożliwiono dynamiczne anulowanie ofert (żądania `DELETE`) wraz z automatycznym zwrotem zablokowanych środków/akcji, co dodatkowo zdywersyfikowało możliwe ścieżki użytkownika podczas pojedynczej sesji.

## 2. Nowa symulacja ruchu (Locust) i profile psychologiczne
* **Wdrożenie nowych klas użytkowników:** Pomyślnie zastąpiono bazowe archetypy pięcioma zaawansowanymi profilami: *WindowShopper, ImpulsiveTrader, CarefulTrader, IndecisiveTrader* oraz *StrategicHolder*.
* **Nakładanie się klas (Class Overlap):** W nowej symulacji każdy z profili wykonuje zapytania mutujące stan (`POST`/`DELETE`). Zlikwidowało to problem łatwej separowalności klas (gdzie sam fakt wykonania metody POST jednoznacznie identyfikował tradera). 
* **Modelowanie opóźnień (`delta_t`):** Zaimplementowano zróżnicowane czasy reakcji dla poszczególnych profili (np. błyskawiczne anulowanie ofert przez *IndecisiveTrader* w przeciwieństwie do długotrwałej analizy portfela przez *CarefulTrader*).
* Dodatkowo zintegrowano bota `FundsInjector`, generującego rynkowy szum tła, który został celowo odizolowany od procesu właściwej klasyfikacji.

## 3. Oczyszczenie potoku danych i eliminacja Data Leakage
* **Przebudowa Preprocessingu:** Zmodyfikowano skrypt przetwarzający logi na tensory (`process_data.py`), aby całkowicie odciąć model od ukrytych "ściąg". 
* Z wektorów wejściowych sieci neuronowej bezwzględnie usunięto jawne identyfikatory (takie jak `user_class`, `user_id`, `user_role`). 
* Sieć BiLSTM zmuszona jest obecnie do wnioskowania wyłącznie na podstawie "czystego" śladu cyfrowego: sekwencji anonimowych tokenów akcji (kombinacja *Metoda + Endpoint*) oraz wektora cech czasowych (całkowite opóźnienie, czas bazy danych, czas logiki aplikacji oraz odstęp od poprzedniej akcji). Zdarzenia błędu (np. `BUY_ERROR`) zostały płynnie zintegrowane jako część wejściowego wektora czasowego.


---
# Wyniki treningu i ewaluacja modelu BiLSTM Fusion

Po wygenerowaniu nowych danych przeprowadzono trening modelu BiLSTM z fuzją cech czasowych i zdarzeniowych. Skonfigurowano model z ukrytym wymiarem `HIDDEN_DIM=192`, używając optymalizatora AdamW oraz mechanizmu uwagi (Attention).

**Analiza procesu uczenia:**
Trening został przeprowadzony na przestrzeni 5000 iteracji przy użyciu mechanizmu Mini-Batch. Zgodnie z analizą logów (`log.txt`), model prezentował stabilną i prawidłową krzywą uczenia. Zjawisko stochastycznego spadku wzdłuż gradientu było widoczne. Zapisano i przetestowano najlepszą wagę modelu (`model_best.pth`), zapobiegając przeuczeniu (overfittingowi) w późniejszych etapach.

**Ewaluacja na zbiorze testowym (Wyniki):**
Ostateczne wyniki klasyfikacji na niewidzianym zbiorze testowym wyniosły:
* **Globalna dokładność (Accuracy):** 86.28%
* **Średni F1-Score (Macro Avg):** 0.8722

Szczegółowe metryki dla poszczególnych profili:
* **WindowShopper:** Precision: 99.0%, Recall: 78.7%, F1: 87.7%
* **ImpulsiveTrader:** Precision: 95.5%, Recall: 80.2%, F1: 87.1%
* **CarefulTrader:** Precision: 88.5%, Recall: 87.0%, F1: 87.7%
* **IndecisiveTrader:** Precision: 73.0%, Recall: 97.1%, F1: 83.3%
* **StrategicHolder:** Precision: 100%, Recall: 82.2%, F1: 90.2%

**Wnioski z Macierzy Pomyłek (Confusion Matrix):**
Wizualizacje wyników (w tym *Confusion Matrix* oraz wykresy słupkowe metryk) nie zostały wklejone bezpośrednio do raportu, jednak znajdują się w katalogu roboczym projektu: `Analysis/BiLSTMFusion/outputs/v1/results/`.
Analiza macierzy pomyłek i raportu klasyfikacyjnego ujawnia interesującą specyfikę działania sieci:
1. **Wysoka identyfikacja IndecisiveTrader:** Z racji silnego nakładania się (Class Overlap) poszczególnych klas korzystających z metod `POST`, model bardzo skutecznie wyłapuje użytkowników niezdecydowanych (Recall 97.1%), jednak stosunkowo często kwalifikuje "na wyrost" innych użytkowników do tej klasy (Precision 73.0%). 
2. **Precyzja profili strategicznych i oglądających:** Czyste akcje "oglądaczy" (*WindowShopper*) oraz powolnych graczy (*StrategicHolder*) zostały zidentyfikowane z niemalże perfekcyjną precyzją (99%-100%), udowadniając, że mechanizm uwagi BiLSTM poprawnie zdekodował wpływ dużych opóźnień (`delta_t`) na profil psychologiczny inwestora.


---

# Dalsze kroki i plan optymalizacji klasyfikacji

Obecne wyniki (dokładność rzędu 86%) stanowią solidny punkt odniesienia (baseline). Zaobserwowano jednak, że model stosunkowo szybko osiąga swoje maksimum możliwości (najlepszy wynik już w okolicach 500. iteracji), co sugeruje, że przy obecnym wolumenie danych sieć szybko wyczerpuje pulę dostępnych wzorców i zaczyna ulegać przeuczeniu (overfittingowi). Aby przełamać ten próg i zmusić sztuczną inteligencję do głębszej analizy, planowane jest podjęcie następujących kroków:

**1. Analiza i eliminacja pozostałych luk w danych (Data/Feature Engineering)**
Zanim zbiór danych zostanie powiększony, konieczne jest wyeliminowanie czynników, które mogą sztucznie spłycać wnioskowanie modelu:
* **Nierównowaga klas (Class Imbalance):** Raport klasyfikacyjny wykazuje, że model nadmiernie faworyzuje klasę *IndecisiveTrader* (najniższa precyzja: 73%, przy recallu 97%). Konieczne jest wyrównanie wag klas w funkcji straty (Weighted Cross-Entropy) lub dostosowanie prawdopodobieństw (spawn rates) w skrypcie Locust.
* **Rozdzielczość sesji:** Należy zweryfikować, czy długość analizowanych okien czasowych (liczba akcji na sesję) nie jest zbyt krótka. Zbyt krótkie sesje uniemożliwiają modelom rekurencyjnym rozwinięcie "pamięci" o długoterminowych zamiarach użytkownika.

**2. Skalowanie zbioru danych (Wielkoskalowa Symulacja)**
Sieci głębokie wymagają ogromnej różnorodności, aby uczyć się rzadkich przypadków brzegowych. Obecny zbiór treningowy (ok. 4600 sekwencji) zostanie zastąpiony masywną symulacją docelową. Planowane jest wygenerowanie około **400 000 unikalnych sekwencji** zachowań. Taka skala zapobiegnie przedwczesnemu zapamiętywaniu danych przez model (memorization) i wydłuży fazę właściwego uczenia (generalization), pozwalając sieci na odkrycie subtelniejszych korelacji czasowych.

**3. Zmiana architektury na model typu Transformer**
Architektura BiLSTM, choć skuteczna, posiada naturalne ograniczenia w przetwarzaniu bardzo długich zależności czasowych. Docelowym krokiem badawczym będzie implementacja i trening zupełnie nowego modelu opartego na architekturze **Transformer** (wykorzystującego mechanizm wielogłowicowej uwagi - *Multi-Head Attention*). Porównanie modelu rekurencyjnego (LSTM) z modelem atencyjnym (Transformer) na tak wygenerowanym, gigantycznym zbiorze danych giełdowych stanowić będzie główną oś badawczą pracy magisterskiej, mającą na celu maksymalizację ostatecznej skuteczności klasyfikatora.