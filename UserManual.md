# Instrukcja uruchomienia

### Autor: Piotr Greń

> ## Spis treści:
1. [Opis](#opis)
2. [Wymagania](#wymagania)
3. [Symulacja (zbieranie danych)](#symluacja)
    1. [Przygotowanie](#przygotowanie)
    2. [Uruchomienie](#uruchomienie-symulacji)
4. [Przygotowanie danych dla modelu](#)
5. [Model](#model)
    1. [Trening i ewaluacja](#trening-i-ewaluacja)
    2. [Testy](#test-modelu)

> ## Opis

Instrukcja tłumaczy dokładnie w jaki sposób uruchomić samodzielnie niniejszy projekt. Projekt jest wysoce zautomatyzowany i wymaga minimalnego nakładu ze strony developera/programisty/użytkownika, próbującego uruchomić go samodzielnie. Insturkcja omawia ewszystkie aspekty uruchomienia programu od wymagań, przeprowadzenia krok po kroku przez sekwencję uruchomienia i walidacji programu, aż po uzyskane wyniki oraz miejsce, w których powinny się znaleźć.


> ## Wymagania

Przede wszystkim należy sklonować repoytorium **https://github.com/PiotrGren/MastersThesis** do swojego wybranego katalogu.

```bash
git clone https://github.com/PiotrGren/MastersThesis
```

Należy upewnić się, że znajdują się tam wszystkie potrzebne pliki i katalogi. W przypadku plików, instrukcja dalej tłumaczy przy każdym kroku jakie pliki dokładnie są potrzebne do działania programu. Należy w każdym przypadku upewnić się, że nie brakuje żadnego pliku. Podstawowa struktura katalogów wygląda następująco:

```bash
<main-catalog-name>/
├── Analysis/                           # Katalog główny modeli, treningu i testowania
│   ├── BiLSTM Fusion/
│   │   ├── configs/
│   │   │   └── config_fusion.yaml      # plik konfiguracyjny do treningu modelu
│   │   ├── model/                      # w dalszej części instrukcji (w skrócie DCI)
│   │   │   └── ...
│   │   ├── outputs/                    # z początku pusty katalog
│   │   │   └── ...
│   │   ├── scripts/                    # DCI
│   │   │   └── ...                     
│   │   ├── test_net.py
│   │   └── train_net.py
│   ├── data/                           # z początku pusty katalog
│   │   └── ...
│   ├── docs/                           # (opcjonalnie) katalog z dokumentacją [DRAFT]
│   │   └── ...
│   ├── logs/                           # z początku pusty katalog
│   └── process_data.py
├── FinanceApp/                         # Katalog główny aplikacji symulacyjnej
│   └── stockProject - main             # WYMAGANY
│       ├── loadTestingApp/             # DCI
│       │   └── ...
│       └── stockProject/
│           ├── Dockerfile
│           ├── docker-compose.generated.yml
│           ├── docker-compose.yaml
│           ├── generate_docker-compose.sh
│           ├── get_logs.sh
│           ├── gunicorn.ctl
│           ├── manage.py
│           ├── .env                    # Plik ze zmiennymi środowiskowymi
│           ├── monitor/
│           │   ├── Dockerfile
│           │   ├── monitor.py
│           │   └── requirements.txt
│           ├── requirements.txt
│           ├── start_test.sh
│           ├── static/
│           │   └── ...
│           ├── stockApp/
│           │   ├── __init__.py
│           │   ├── admin.py
│           │   ├── apps.py
│           │   ├── management/                         # Komendy inicjalizacyjne
│           │   │   └── ...
│           │   ├── middleware/                         # Middleware do zbierania logów aplikacji
│           │   │   └── request_logging.py
│           │   ├── migrations/                         # Migracje do bazy danych
│           │   │   └── ...
│           │   ├── models/                             # Modele danych
│           │   │   └── ...
│           │   ├── serializers/                        # Serializery danych
│           │   │   └── ...
│           │   ├── tasks.py
│           │   ├── tests.py
│           │   ├── urls.py
│           │   └── views/                              # Endpointy
│           │       └── ...
│           └── stockProject/                           # Katalog główny - konfiguracja
│               └── ...
├── MDocs/                                              # (opcjonalnie) dokumentacja [DRAFT]
├── InstrukcjaUruchomienia.md
└── README.md
```

#### Wymagania systemowe:
Aby uruchomić zarówno aplikację symulacyjną, jak i trening i testowanie modeli, należy zainstalować:
- Docker Engine
- docker-compose
- Python (w projekcie użyto wersji **3.13.12**)
- CUDA (*W przypadku uruchomienia projektu na środowisku z dostępnym **GPU***) - projekt można również uruchomić bez CUDA na CPU


> ## Symluacja

Przed uruchmoeniem aplikacji, należy spełnić wymagania systemowe, oraz upewnić się, że w fodlerze **FinanceApp/** znajdują się wymagane pliki.

> ### Przygotowanie

#### 1. stockProject - main/loadTestingApp/
Katalog z logiką biznesową **Locust**, czyli aplikaji obciążeniowej, która uruchamia scenariusze i przeprowadza symulację ruchu użytkowników. Katalog powinien mieć taką strukturę (**wszystkie pliki wymagane**):

```bash
loadTestingApp/
├── Dockerfile/         # Dockerowy obraz dla Locusta
├── locustfile.py       # Główny plik z logiką bizesową aplikacji obciążeniowej
├── requirements.txt    # Wymagane moduły Pythona wykorzystane w aplikacji obciążeniowej
└── start_locust.sh     # Skrypt bash wymagany do uruchamiania scenariuszy
```

#### 2. stockProject - main/stockProject
Katalog główny z aplikacją. Jest to katalog w którym zdefiniowana jest cała aplikacja backendowa, która jest aplikacją giełdy finansowej. To tu zdefiniowane są modele, serializery, endpointy, konfiguracje, obrazy dockerowe, czy skrypty do uruchamiania symulacji.

```bash
stockProject/
├── Dockerfile                              # Dockerowy obraz dla aplikacji giełdowej
├── docker-compose.yaml                     # docker-compose uruchamiający cały stack potrzebny do poprawnego działania aplikacji
├── get_logs.sh
├── gunicorn.ctl
├── manage.py
├── .env
├── monitor/
│   ├── Dockerfile
│   ├── monitor.py
│   └── requirements.txt
├── requirements.txt
├── start_test.sh                           # [WYMAGANE] Skrytp uruchmiający całą symulację
├── static/
│   └── ...
├── stockApp/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── management/                         # Komendy inicjalizacyjne
│   │   └── ...
│   ├── middleware/                         # Middleware do zbierania logów aplikacji
│   │   └── request_logging.py
│   ├── migrations/                         # Migracje do bazy danych
│   │   └── ...
│   ├── models/                             # Modele danych
│   │   └── ...
│   ├── serializers/                        # Serializery danych
│   │   └── ...
│   ├── tasks.py
│   ├── tests.py
│   ├── urls.py
│   └── views/                              # Endpointy
│       └── ...
└── stockProject/                           # Katalog główny - konfiguracja
    ├── __init__.py
    ├── asgi.py
    ├── celery.py
    ├── urls.py
    └── wsgi.py 
```

#### 3. Pliki parametrów symulacji
Aby uruchomić poprawnie symulację, należy przygotować ponadto pliki parametrów **parameters.txt**, które przekazuje się do skryptu **start_test.sh**. Należy umieścić taki plik w katalogu **FinanceApp/srockProject - main/stockProject/.**. Plik powinien mieć taką strukturę:

```csv
SCENARIO_ID,USERS,SPAWN_RATE,TIME,CLASSES,WAIT_MIN,WAIT_MAX,RATES_N
...
```

Najważniejszym parametrem jest parametr **CLASSES**, który definiuje jakie klasy użytkowników, mają być uruchmomione w trakcie symulacji. Użytkowników należy wpisywać oddzielając ich znakiem dwukropka [ **:** ] i należy wybrać ich z tej list:
- WindowShopper
- ImpulsiveTrader
- CarefulTrader
- IndecisiveTrader
- StrategicHolder

Przykładowe scenariusze:
```csv
SCENARIO_ID,USERS,SPAWN_RATE,TIME,CLASSES,WAIT_MIN,WAIT_MAX,RATES_N
pure_indecisive,50,5,15m,IndecisiveTrader,0.5,2.0,3
pure_strategic,50,5,15m,StrategicHolder,0.5,2.0,3
mix_analytical_overlap,120,10,25m,WindowShopper:CarefulTrader:StrategicHolder,0.5,2.0,3
mix_chaotic_overlap,120,10,25m,ImpulsiveTrader:IndecisiveTrader,0.5,2.0,3
```

> ### Uruchomienie symulacji
Ponieważ proces jest zautomatyzowany za pomocą skryptów `.sh`, instrukcje muszą być wykonywane w terminalu obsługującym powłokę Bash. W przypadku korzystania z systemu Windows, należy użyć jednego z poniższych rozwiązań:
* **Git Bash** (najprostsza opcja, instalowana razem z systemem Git)
* **WSL** (Windows Subsystem for Linux - np. Ubuntu)
* **Linux / macOS** (natywny terminal)

1. Przejdź do katalogu **FinanceApp/stockProject - main/stockProject/**:

```bash
cd FinanceApp/stockProject - main/stockProject/
```

2. Zbuduj stack dockerowy:

```bash
docker compose --profile load build --no-cache
```

3. Uruchom kontenery (bez locusta i monitora):

```bash
docker compose up -d db redis worker beat api
```

4. Uruchom symulację z plikiem parametrów:

```bash
bash start_test.sh parameters.txt
```

Rozpocznie się symulacja. Program sam uruchomi kontener locusta oraz monitora. Ponadto wykorzysta wbudowane skrypty aplikacji i przygotuje bazę danych (np. porzez wstrzyknięcie przykładowych firm do bazy danych). Każdy scenariusz spowoduje zamknięcie poprzedniego locusta i uruchomienie nowego na nowych parametrach. W oknie terminala będą widoczne komunikaty o działaniu symulacji oraz o ich zakończeniu (każdego ze scenariuszy).

W katalogu powinien pojawić się nowy folder **logs/** z plikami:
- **request_log.jsonl** - każdy request jakiegokolwiek endpointa przez użytkownika (główny plik logów)
- **error_log.jsonl** - logi errorów, które powstały w trakcie działania symulacji (wzbogacają dane dla modelu)
- **system_metric.jsonl** - relikt poprzedniego projektu, wykorzystywany to sprawdzenia czy w trakcie symulacji nie doszło do przeciążeń samego kontenera, co może mieć wpływ na logi (np. czasy, zakrzywienie czasów opóźnień nie spowodowanych samym zachowaniem użytkowników czy aplikacji)

Po poprawnie zakończonej symulacji wszystkich scenariuszy, program sam zakończy działanie, oraz wyłączy wszystkie kontenery (nie tylko locust czy monitor).

> ## Przygotowanie danych
Gdy symulacja się zakończy, a dane będą już zebrane należy przejść do katalogu głównego projektu:

```bash
~/Projekt/FinanceApp/stockProject - main/stockProject$ cd ../../..
~/Projekt$
```

Z tego poziomu należy przekopiować powstały katalog **logs/** bezpośrednio do katalogu **Analysis/**. Można to zrobić na dwa sposoby, w środowisku graficznym po prostu przekipiować folder, lub z poziomu terminala:

```bash
cp FinanceApp/stockProject - main/stockProject/logs Analysis/.
```

Następnie należy przejść do katalogu **Analysis/** oraz zainstalować wszystkie zależności (można wcześniej stworzyć wirtualne środowisko według uznania):

```bash
pip install -r requirements.txt
```

Gdy wszystkie zależności zostaną poprawnie zainstalowane, należy uruchomić plik, który przetworzy surowe logi na gotowe dane i sekwencje dla modelu. Są dwie opcje, pierwsza wczytuje logi z folderu **logs/** i zapisuje wyniki do folderu **data/**:

```bash
python process_data.py
```

Jeżeli mamy logi w innym folderu i chcemy zapisać dane do innego folderu, możemy uruchomić skrypt z odpowiednimi flagami:

```bash
python process_data.py --log_di ./moje_logi --output_dir ./gotowe_dane
```

Skrypt generuje dokładnie 4 pliki. Oto co w nich siedzi:
- **vocab.json** (*Słownik zdarzeń*) - plik tekstowy JSON zawierający mapowanie (słownik) wszystkich unikalnych akcji z logów na liczby całkowite.
    *Do czego służy:* Model nie umie czytać tekstu (np. "POST BUY"). Ten plik mówi mu: "POST BUY" to token nr 2, "GET USER" to token nr 3 itd. Jest to absolutnie niezbędne do późniejszego działania sieci.
- **train_data.pt** (*Zbiór treningowy*) - skompresowany plik PyTorcha zawierający 80% wszystkich poprawnych sesji.
    *Do czego służy:* To z tego pliku model uczy się na pamięć wzorców zachowań i na jego podstawie aktualizuje swoje wagi podczas treningu.
- **val_data.pt** (*Zbiór walidacyjny*) - plik zawierający kolejne 10% sesji.
    *Do czego służy:* Sieć neuronowa nie uczy się z tego pliku, ale po każdej epoce "sprawdza się" na nim, żebyśmy widzieli, czy zaczyna rozumieć problem (generalizacja), czy tylko wkuwa na blachę zbiór treningowy (overfitting). Na jego podstawie zapisywany jest najlepszy model (model_best.pth).
- **test_data.pt** (*Zbiór testowy*) - plik zawierający ostatnie 10% całkowicie odseparowanych sesji.
    *Do czego służy:* Służy do ostatecznego, obiektywnego sprawdzenia wytrenowanego już modelu. Używasz go dopiero na samym końcu w skrypcie test_net.py, aby wygenerować ostateczny raport (Classification Report) i macierz pomyłek.

> ## Model
Do tej pory przygotowaliśmy wszystkie dane potrzebne do wytrenowania i przetestowania modelu. Pozostało przygotować i uruchomić sam model. Na dzień pisania tej instrukcji istnieje jeden model nazwany **BiLSTM Fusion**. Model łączy w sobie dwa wejścia - **sekwencję endpointów użytkownika** mówiącą o zachowaniu użytkownika w trakcie danej sesji, oraz **czasy użytkownika** czyli poszczególne czasy, wykonania każdego z endpointów, a także odstępy między zapytaniami. Po więcej informacji odnośnie modelu proszę sprawdzić:
 - 👉 [Model Pipeline](./MDocs/MLModelPipeline.md)
 - 👉 [Pipeline Specifications](./Analysis/docs/pipeline_spec.md)
 - 👉 [Model Guidline [DRAFT]](./Analysis/BiLSTM%20Fusion/model/docs/guideline_model_bilstm.md)
 - 👉 [Pipeline Docs [DRAFT]](./Analysis/BiLSTM%20Fusion/model/docs/pipeline_danych_bilstm.md)

Przed uruchomieniem treningu należy sprawdzić, czy nie brakuje żadnych plików. Katalog **Analysis/** obowiązkowo powinien zwierać pliki:
```bash
Analysis/                           # Katalog główny modeli, treningu i testowania
├── BiLSTM Fusion/
│   ├── configs/
│   │   └── config_fusion.yaml      # plik konfiguracyjny do treningu modelu (więcej informacji o nim w Model Pipline)
│   ├── model/
│   │   ├── docs/
│   │   │   └── ...
│   │   ├── __init__.py
│   │   └── bilstm_fusion.py        # definicja modelu BiLSTM Fusion
│   ├── scripts/                    # skrypty niezbędne do działania modelu i pipline'u modelu
│   │   ├── __init__.py
│   │   ├── data_loader.py          # skrypt odpowiadający za przetwarzanie danych .pt
│   │   ├── solver.py               # skrypt konfigurujący optymalizator i scheduler
│   │   └── utils.py                # uniwersalne narzędzia pomocnicze (zapisy logów, checkpointów modelu czy obliczanie metryk)
│   ├── test_net.py                 # skrypt uruchamiający trening modelu
│   └── train_net.py                # skrypt uruchamiający test modelu
├── data/                           # katalog z danymi wygenerowanymi przez skryp process_data.py
│   ├── test_data.pt
│   ├── train_data.pt
│   ├── val_data.pt
│   └── vocab.json
├── docs/
│   └── ...
├── logs/                           # katalog z surowymi logami z symulacji (po przetworzeniu przez process_data.py już niepotrzebny)
│   ├── request_log.jsonl
│   └── error_log.jsonl
├── requirements.txt
└── process_data.py
```

> ### Trening i ewaluacja
Gdy wszystko jest gotowe i sprawdzone, można przejść do trenowania modelu. Trening jest w pełni zautomatyzowany i aby go uruchomić wystarczy wpisać jedno polecenie:
```bash
python train_net.py --config config_fusion.yaml --num-gpus 1
```

Skrypt ma trzy flagi:
- **--config** [WYMAGANE] - ścieżka do pliku konfiguracyjnego YAML, w którym zdefiniowane są wszystkie parametry uczenia (więc o tym pliku tutaj: 👉 [Pipeline Specifications](./Analysis/docs/pipeline_spec.md))
- **--resume** [OPCJONALNA] - flaga włączająca wznawianie treningu. W trakcie treningu są zapisywane checkpointy modelu, jeżeli przerwiemy trening, możemy go wznowić od ostatniego checkpoinut. Skrypt poszuka pliku *last_checkpoint.pth* i wznowi trening od tego momentu
- **--num-gpus** [OPCJONALNA] - pozwala zdefiniować liczbę kart graficznych na ilu ma się wykonać trening. Domyślnie wynosi **1**. Można wpisać **--num-gpus 0**, wtedy zignoruje kartę graficzną i wymusi trening na CPU

Ewaluacja wykonuje się automatycznie na danych *val_data.pt* co kilka iteracji. Co ile iteracji ma się wykonywać ewaluacja modelu jest definiowane hiperparametrem w pliku konifguracyjnym.

Po poprawnym uruchomieniu pliku powinien rozpocząć się trening, a w oknie terminala pokazać mniej więcej coś takiego:
```bash
2026-03-10 20:05:12 - Starting training with config: configs/config_fusion.yaml
2026-03-10 20:05:12 - Output dir: outputs\v1
2026-03-10 20:05:12 - Device: cuda
2026-03-10 20:05:12 - Vocab loaded. Size: 12
2026-03-10 20:05:26 - Training started. Max iter: 5000
2026-03-10 20:05:28 - Iter: 0/5000 | Loss: 2.5792 | Acc: 15.62% | LR: 0.000003 | ETA: 00:00:00
2026-03-10 20:05:30 - Iter: 25/5000 | Loss: 1.6551 | Acc: 31.25% | LR: 0.000053 | ETA: 00:11:41
2026-03-10 20:05:33 - Iter: 50/5000 | Loss: 1.2914 | Acc: 43.75% | LR: 0.000103 | ETA: 00:10:02
2026-03-10 20:05:36 - Iter: 75/5000 | Loss: 0.4912 | Acc: 90.62% | LR: 0.000153 | ETA: 00:09:59
[...]
```

**UWAGA**: Czasem w trakcie treningu mogą wystąpić problemy z treningiem na GPU. Zaleca się wtedy reinstalację torcha, bo często to jest problemem. Można to zrobić za pomocą poniższych komend:
```bash
pip uninstall torch torchvision torchaudio
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```
Po tym trening powinien przebiec prawidłowo. Trening wygeneruje szereg plików, które zostaną zapisane w katalogu zdefiniowanym hiperparametrem **OUTPUT_DIR**. W plikach znajdują się:
- **final/model_final.pth** - zapisany wytrenowany model, po przeprowadzeniu pełnego treningu
- **config.yaml** - przepisze plik konfiguracyjny, na jakim został uruchomiony trening, w celu możliwości odtworzenia próby oraz przetestowania modelu na tych samych parametrach
- **last_checkpoint.pth** - ostatni checkpoint - wykorzystywane do wznawiania treningu, jeśli został przerwany przed końcem
- **log.txt** - zapisane do pliku .txt logi, które wyświetlają się w oknie terminala w trakcie treningu
- **metrics.json** - metryki obliczane na bieżąco w trakcie treningu - cała historia
- **model_best.pth** - zapisany najlepszy uzyskany model w trakcie treningu (na podstawie ewaluacji)

> ### Test modelu
Po przeprowadzeniu treningu modelu, pozostaje przeprowadzić na nim testy, na zbiorze testowym **test_data.pt**. W tym celu używamy komendy:
```bash
python test_net.py --weights outputs/v1/model_best.pth
```

Powyższe polecenie posiada dwie flagi:
- **--weights** [WYMAGANE] - ścieżka do pliku z wyuczonymi wagami modelu, który chcemy przetestować (np. `--weights outputs/v1/model_best.pth`)
- **--config** [OPCJONALNA] - ścieżka do pliku konfiguracyjnego. Skrypt automatycznie szuka pliku **config.yaml** w tym samym folderze co wagi modelu, ręcznie trzeba wskazać tylko jak jest zapisana w innym miejscu

Skrypt testowy, przeprowadzi testy modelu, a następnie wygeneruje jego wyniki i zapisze w folderze **results/** w katalogu **OUTPUT_DIR** zdefiniowanym w pliku konfiguracyjnym. Wśród plików znajdują się:
- **classification_report.txt** - raport klasyfikacyjny z odpowiednimi metrykami dla modelu i klas
- **confusion_matrix_count.png** - macierz pomyłek modelu (liczbowa)
- **confision_matrix_norm.png** - macierz pomyłek modelu (procentowa)
- **metrics.json** - metryki modelu według klas (przydatne np. do przygotowania wykresu zestawienia)

## Dodatek
Aktualnie w trakcie rozwoju jest drugi model na podstwie architektury Transformers. Model zostanie przygotowany w taki sposób, aby można było go użyć analogicznie co modelu BiLSTM Fusion. Będzie on posiadał własne skrypty, również do treningu i testowania, lecz zamysł i sekwencja uruchomienia modelu, a nawet polecenia będą takie same, tylko w innym podfolderze projektu.


> W razie jakichkolwiek pytań jestem do dyspozycji:
>- 👉 169783@stud.prz.edu.pl
>- 👉 piotr.gren02@gmail.com
>- 👉 Teams: Piotr Greń [169783@o365.prz.edu.pl]