# Dokumentacja Architektury: LogTransformerFusion (Milestone 1)

## 1. Wzbogacenie Reprezentacji Zdarzeń (Event Semantics)
Podstawowa reprezentacja zdarzeń w logach systemowych oparta wyłącznie na metodzie HTTP oraz grupie endpointów (np. `POST BUY`) okazała się niewystarczająca do uchwycenia pełnego kontekstu behawioralnego użytkownika. 

Aby umożliwić modelowi rozróżnienie intencji i błędów poznawczych użytkowników (np. wielokrotne próby zakupu bez wystarczających środków przez klasę `ImpulsiveTrader`), struktura wejścia dyskretnego została rozszerzona o status operacji. Nowy token $T_i$ definiowany jest jako:
$T_i = \text{Concat}(\text{HTTP\_METHOD}, \text{ENDPOINT\_GROUP}, \text{HTTP\_STATUS})$

Dzięki temu zdarzenia sukcesu (np. `POST BUY 201`) są mapowane w przestrzeni osadzeń (embeddings) w zupełnie innym miejscu niż błędy walidacji (np. `POST BUY 400`), co stanowi kluczową cechę dyskryminującą dla klasyfikatora.

## 2. Architektura Fuzji Danych (Dual-Input Fusion)
Proponowany model LogTransformerFusion opiera się na równoległym przetwarzaniu dwóch modalności w każdym kroku czasowym $i$:
1. **Zdarzenie dyskretne ($e_i$)** – identyfikator tokena ze słownika.
2. **Wektor cech ciągłych ($t_i$)** – znormalizowane czasy operacji i opóźnienia: $[\text{latency}, \text{db\_time}, \text{app\_time}, \Delta t]$.

Fuzja na poziomie osadzeń (Early Fusion) odbywa się poprzez nałożenie nieliniowej transformacji na wektor czasu i zsumowanie go z osadzeniem zdarzenia oraz kodowaniem pozycyjnym:

$x_i = \text{Embed}_{event}(e_i) + \text{MLP}_{time}(t_i) + P_i$

Gdzie:
* $x_i$ – ostateczny wektor wejściowy do modelu Transformer dla $i$-tego zdarzenia.
* $\text{Embed}_{event}$ – macierz osadzeń zdarzeń o wymiarze $d_{model}$.
* $\text{MLP}_{time}$ – wielowarstwowa sieć perceptronowa (Multi-Layer Perceptron) mapująca wektor ciągły $t_i \in \mathbb{R}^4$ na przestrzeń $d_{model}$.
* $P_i$ – wyuczalne kodowanie pozycyjne (Positional Encoding) informujące model o miejscu zdarzenia w sekwencji.

## 3. Zastosowanie Mechanizmu Atencji i Tokena [CLS]
Zgodnie z paradygmatem modeli z rodziny BERT, na pierwszej pozycji sekwencji ($i=0$) wstrzykiwany jest sztuczny token klasyfikacyjny `[CLS]`. 

Zestaw wektorów wejściowych $X = [x_{cls}, x_1, x_2, ..., x_n]$ jest podawany do bloków Multi-Head Self-Attention. Mechanizm ten pozwala każdemu zdarzeniu w sesji modelować relacje ze wszystkimi innymi zdarzeniami, zgodnie ze wzorem:

$$\text{Attention}(Q, K, V) = \text{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)V$$

Po przejściu przez $N$ warstw enkodera Transformera, do ostatecznej klasyfikacji wyodrębniana jest wyłącznie reprezentacja wyjściowa odpowiadająca tokenowi `[CLS]`. Służy ona jako zagregowany wektor cech behawioralnych całej sesji użytkownika, który następnie przechodzi przez klasyfikator oparty o wielowarstwową sieć liniową (MLP Head) w celu predykcji rozkładu prawdopodobieństwa przynależności do klas.