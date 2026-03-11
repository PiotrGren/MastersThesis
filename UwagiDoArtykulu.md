# Uwagi do artykułu roboczego: "WUCMF Web User Classification Multilayer Frameworks Using BiLSTM and TCN"

Poniżej są uwagi, o które Pan prosił. Podzieliłem je na dwie główne części:
 - pierwsza dotyczy samej istoty danych i trenowania modeli (bazując na moich ostatnich doświadczeniach z rozbudową tego projektu) - to to wszystko co już Panu mówiłem, odnośnie wybrakowania danych itd. itd. po prostu to spisuję, na wszelki wypadek
 - druga to inne uwagi odnośnie samego artykułu - nie znam się jakoś bardzo na pisaniu artykułów naukowych i nie wiem czy dokładnie o to Panu chodziło, ale napisałem tyle ile mogłem

## 1. Uwagi techinczne (Dane wejściowe, modele i trening)

W pierwotnych danych jak już wspominałem istnieją istotne braki, które bezpośrednio wpłynęły na wyniki modeli opisanych w artykule. Wynik rzędu 98-99% dokładności dla modeli BiLSTM i TCN był imponujący, ale wiadomo, że raczej wynika on z ograniczeń ówczesnego środowiska testowego.

* **Problem trywialności danych (Brak "Class Overlap"):** W tamtym etapie projektu skrypt w środowisku Locust był wysoce zdeterminowany. Klasy użytkowników były od siebie całkowicie odseparowane funkcjonalnie – np. `ActiveUser` korzystał z endpointów mutujących (`POST`/`PUT`), a `ReadOnlyUser` wyłącznie z zapytań `GET`. Model sieci neuronowej zamiast uczyć się złożonych, długoterminowych zależności czasowych, bardzo szybko znajdował "ścieżkę na skróty" (np. *jeśli w sekwencji występuje metoda POST, to na 100% jest to ActiveUser*).
* **Śledzenie sesji (Session & User ID):** Pierwotne logi nie posiadały żadnego śledzenia `user_id` ani `session_id`. Sam proces dzielenia danych wejściowych nie odbywał się za pomocą żadnego z tych ID, a przez grupowanie klas użytkowników i cięcie występujących sekwencji po posortowaniu ich czasowo. Nie odzwierciedlało to w ogóle zachowania pojedynczego człowieka, a zachowania konkretnej klasy, co znacznie upraszczało wejście. Poza tym to złe podejście samo w sobie.
* **Moja propozycja dla artykułu (Sekcja "Limitations"):**
  Oczywiście te wyniki są poprawne matematycznie na tamtym zbiorze danych i udowadniają, że architektury sekwencyjne działają na logach IT. Sugerowałbym jednak dodanie w artykule sekcji **"Limitations and Future Work"**. Można w niej otwarcie przyznać, że obecne 99% to wynik działania na wyizolowanych, wysoce zdeterminowanych profilach (Proof of Concept). Będzie to bardziej rzetelne, zgodne z prawdą. Dodałbym, że docelowymi krokami teraz jest po pierwsze przebudowanie loggera, do śledzenia też user_id i session_id (co już zrealizowałem), a następnie wprowadzenie tzw. szumu, nakładających się klas (gdzie każdy profil używa tych samych metod API - też zrealizowane ale można poprawić) oraz iniekcji błędów, co naturalnie obniży skuteczność do wartości bardziej realistycznych, ale znacznie zyska na użyteczności biznesowej. Oczywiście nie odzwierciedli to nawet blisko, systemów takich prawdziwych real-life, produkcyjnych bo to tylko symulacja, ale zawsze to lepsze niż to co było w momencie powstania artykułu.

## 2. Inne uwagi do samego artukułu

Jako student niewiele się znam na pisaniu samych artykułów, ale chyba zauważyłem kilka miejsc, które warto byłoby doprecyzować, aby artykuł był pełniejszy.

* **Brak szczegółów dotyczących hiperparametrów (Reproducibility):**
  W sekcji opisującej trening modeli brakuje precyzyjnej "metryczki" eksperymentu. Jako osoba, która chciałaby odtworzyć ten projekt, potrzebowałbym wiedzieć:
  * Jakiego optymalizatora użyto (np. Adam, SGD)? Jaka była wartość parametru *Learning Rate*? Wiem, że jest to podane w artukule raz czy dwa, ale może warto dodać jakąś tabelkę podsumowującą hiperparametry?
  * Jaki był rozmiar paczki danych (*Batch Size*) oraz po ilu epokach modele osiągnęły optymalne wyniki (kiedy nastąpiła zbieżność/convergence)? Rozmiar batch size chyba nie był podany w artykule, chyba że coś mi umknęło. Tak samo ze zbieżnością.
  * Warto dodać też jedno zdanie o wykorzystanym sprzęcie (np. model trenowano przy użyciu akceleracji GPU i może na jakiej karcie, chociaż patrząc na moją kartę to nie wiem czy nie umniejszałoby to artukułowi :) ).
* **Inżynieria Cech (Feature Engineering):**
  W artykule wspomniano o wykorzystaniu danych czasowych (np. czas odpowiedzi), ale brakuje informacji o ich transformacji. Wiem, że surowe warotści mogą psuć wagi modelu. Nie pamiętam już teraz jakie tam były przeprowadzone transofrmacje i czy były, ale mogę do tego wrócić i się temu przyjrzeć.
* **Rozszerzenie interpretacji wyników:**
  Wykresy i tabele z wynikami są czytelne, jednak sam tekst wokół nich wydaje się dość powierzchowny. Zamiast samego stwierdzenia faktu ("model BiLSTM uzyskał lepsze wyniki niż bazowe metody ML"), dobrze byłoby dodać krótką analizę *dlaczego* tak się stało. Można wspomnieć, że zdolność sieci BiLSTM i TCN do "zapamiętywania" historycznego kontekstu akcji przewyższa płaskie modele statystyczne, które widzą tylko pojedyncze logi w oderwaniu od siebie.
* **Kontekst we Wstępie (State of the Art):**
  We wstępie bardzo dobrze zarysowany jest problem klasyfikacji zachowań na podstawie logów. Wydaje mi się, że może warto byłoby dodać krótki akapit o tym, jak obecnie rynek radzi sobie z podobnymi wyzwaniami. Chyba mogłoby to pokazać dlaczego BiLSTM czy TCN jest innowacyjnym podejściem, ale też trzeba by było zrobić research czy ktoś już tego nie próbował, a jak tak to na jaką skalę.

Mam nadzieję, że powyższe uwagi okażą się przydatne.