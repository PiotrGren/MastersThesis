# Dokumentacja Metodologii: Data Processing Pipeline & Feature Engineering (Milestone 2)

## 1. Architektura Przepływu Danych (Data Flow Diagram - Deskryptor)
Proces inżynierii cech (Feature Engineering) został zaprojektowany tak, aby przekształcić surowe, heterogeniczne logi systemowe w zunifikowany, wielomodalny format macierzowy akceptowalny przez sieci neuronowe. 

**Przepływ sekwencyjny:**
1. **Ingestion:** Wczytanie surowych logów `request_log.jsonl`.
2. **Cleansing & Filtering:** Usunięcie operacji debugowych (np. webhooki airdropów) oraz sesji o nieznanej klasie bazowej.
3. **Semantic Tokenization:** Transformacja zdarzeń dyskretnych do bogatego słownika opartego na statusach HTTP.
4. **Temporal Extraction:** Obliczenie interwałów czasowych pomiędzy zdarzeniami w ramach pojedynczej sesji ($\Delta t$) oraz normalizacja logarytmiczna opóźnień infrastrukturalnych.
5. **Universal `<CLS>` Injection:** Wzbogacenie każdej sekwencji o token agregacyjny na pozycji $0$, zapewniające kompatybilność zbioru danych zarówno dla modelu BiLSTM, jak i Transformer.
6. **Tensorization & Split:** Konwersja do natywnych struktur `torch.Tensor` i deterministyczny podział na zbiory uczący, walidacyjny i testowy w proporcji 80/10/10.

## 2. Formalna Definicja Ekstrakcji Cech (Feature Extraction)

### 2.1 Cechy Dyskretne (Semantic Tokens)
Zamiast tradycyjnego podejścia opartego na samych metodach HTTP, wprowadzono tokeny semantyczne oddające skuteczność akcji. Zdefiniujmy zdarzenie w logach jako strukturę wielowymiarową. Odwzorowanie zdarzenia na dyskretny identyfikator $T_i \in \mathcal{V}$ (gdzie $\mathcal{V}$ to przestrzeń słownika) realizowane jest za pomocą funkcji konkatenacji:

$$T_i = \text{Concat}(\text{METHOD}_i, \text{GROUP}_i, \text{STATUS}_i)$$

*Przykład:* Rozwiązanie to drastycznie redukuje szum informacyjny, separując udane transakcje (`POST_BUY_201`) od operacji przerwanych ze względu na błąd walidacji, np. brak środków (`POST_BUY_400`).

### 2.2 Cechy Ciągłe (Temporal Features)
Zachowanie czasowe (Temporal Dynamics) użytkownika opisywane jest przez wektor czterowymiarowy. Różnice czasowe (np. mikrosekundy dla bazy danych vs sekundy dla "myślenia" człowieka) powodują problem numeryczny dla sieci neuronowych. Zastosowano transformację logarytmiczną stabilizującą wariancję (Log1p Normalization):

Niech $t_i$ będzie wektorem cech ciągłych w $i$-tym kroku czasowym:

$$t_i = \begin{bmatrix}
\log(1 + \text{latency\_ms}_i) \\
\log(1 + \text{db\_time\_ms}_i) \\
\log(1 + \text{app\_time\_ms}_i) \\
\log(1 + \Delta t_i)
\end{bmatrix}$$

Gdzie $\Delta t_i$ jest różnicą czasu pomiędzy obecnym a poprzednim zdarzeniem:
$$\Delta t_i = \text{timestamp}_i - \text{timestamp}_{i-1} \quad \text{dla} \quad i > 0$$
Dla $i=0$ (pierwsze zdarzenie w sesji), $\Delta t_0 = 0$.

### 2.3 Struktura Uniwersalnej Sekwencji (The Sequence Schema)
W celu umożliwienia bezstronnej analizy porównawczej architektur, wygenerowany Tensor Wejściowy posiada hybrydową strukturę zgodną z paradygmatem modeli BERT. 
Każda sesja $S$ reprezentowana jest jako ciąg krotek (tokenów i wektorów czasowych) o długości $N+1$:

$$S = \left( (T_{cls}, t_{cls}), (T_1, t_1), (T_2, t_2), \dots, (T_N, t_N) \right)$$

Gdzie wektor stanu klasyfikacyjnego jest stały i nie wnosi cech czasowych do systemu:
$$T_{cls} = \text{Vocab}(\text{"<CLS>"}), \quad t_{cls} = [0.0, 0.0, 0.0, 0.0]^T$$