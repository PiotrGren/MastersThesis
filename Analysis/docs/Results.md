# Podsumowanie Wyników Badań: Klasyfikacja Behawioralna Użytkowników Giełdowych

## 1. Charakterystyka wyników modelu bazowego **BiLSTM Fusion**
Model bazowy oparty na dwukierunkowej sieci LSTM (**BiLSTM**) uzyskał wysoką skuteczność klasyfikacji, osiągając wskaźnik Macro F1-Score na poziomie **90,78%** oraz dokładność (Accuracy) wynoszącą **91,12%**.

Analiza macierzy pomyłek wykazała specyficzną asymetrię błędów – model niemal bezbłędnie identyfikuje klasę `WindowShopper` (*Recall = 99,01%*), jednakże większość pomyłek pozostałych profili (szczególnie `StrategicHolder`) polega na błędnym przypisaniu ich do profilu pasywnego.

Wynika to bezpośrednio z wprowadzonego do symulacji szumu w postaci nagłych wylogowań, które przerywają sesję przed wystąpieniem zdarzeń transakcyjnych, czyniąc je semantycznie nieodróżnialnymi od sesji podglądaczy.

## 2. Charakterystyka wyników modelu **LOGTransformer Fusion**
Model oparty na architekturze **Transformer** z mechanizmem Multi-Head Self-Attention, trenowany na tym samym zbiorze danych, uzyskał niemal identyczną wydajność, osiągając Macro F1-Score na poziomie **90,78%**.

Podobnie jak w przypadku BiLSTM, model wykazał tę samą tendencję do mylenia uciętych sesji aktywnych inwestorów z klasą `WindowShopper`.

Zastosowanie globalnego mechanizmu atencji nie pozwoliło na redukcję tego specyficznego błędu, co potwierdza, że informacja potrzebna do separacji tych przypadków nie jest zawarta w samej strukturze logów HTTP przy wystąpieniu nagłego przerwania sesji.

## 3. Analiza porównawcza architektur
Zestawienie wyników obu modeli ujawnia rzadko spotykaną w badaniach symulacyjnych pełną zbieżność metryk i topologii błędów.

Fakt, że dwie fundamentalnie różne architektury — rekurencyjna (BiLSTM) i atencyjna (Transformer) — osiągnęły ten sam pułap skuteczności, jest dowodem na osiągnięcie granicy **błędu nieredukowalnego** (ang. **Bayes Error Rate**) dla przyjętego zbioru cech.

Modele z sukcesem wyekstrahowały maksimum dostępnych sygnałów behawioralnych z fuzji tokenów i czasów, a pozostały margines błędu wynika wyłącznie z inherentnego szumu środowiskowego (*niepewność aleatoryczna*), co dowodzi dojrzałości zaproponowanej inżynierii cech.

## 4. Wnioski z realizacji projektu
Badania potwierdziły, że podejście typu **Dual-Input Fusion** (łączące sekwencje akcji z log-normalizowanymi parametrami czasowymi) jest wysoce skuteczną metodą modelowania zachowań w aplikacjach webowych.

System wykazał całkowitą odporność na mylenie ze sobą różnych klas aktywnych traderów (np. zero pomyłek między profilami impulsywnymi a ostrożnymi), co świadczy o precyzyjnym mapowaniu intencji użytkownika.

Osiągnięta skuteczność na poziomie **91%** w środowisku zaszumionym jest wynikiem znacznie bardziej wartościowym naukowo niż wyższe wyniki w warunkach sterylnych, gdyż wyznacza granice możliwości detekcji opartej wyłącznie na logach systemowych.

## 5. Teza pracy i podsumowanie obronne
**Teza:** *"Wykorzystanie wielomodalnej fuzji wczesnej (integrującej sekwencje zdarzeń dyskretnych z ciągłymi opóźnieniami czasowymi) stanowi skuteczną metodę ekstrakcji wzorców behawioralnych z logów systemowych, pozwalając na poprawną klasyfikację profilu użytkownika w środowisku o wysokim natężeniu szumu oraz nakładaniu się klas."*

**Podsumowanie obronne:** Projekt udowadnia, że nowoczesne architektury głębokie są w stanie skutecznie separować złożone profile użytkowników webowych przy użyciu minimalnego zestawu danych z logów infrastrukturalnych. Praca broni się merytorycznie poprzez wykazanie, że błędy klasyfikacji nie wynikają z wad modeli, lecz z obiektywnych granic informacyjnych zdefiniowanych przez chaos rzeczywistych interakcji sieciowych (np. utrata połączenia). Zbieżność wyników BiLSTM i Transformera stanowi naukowy dowód na optymalność zaproponowanego mechanizmu fuzji danych.