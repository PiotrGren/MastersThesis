# Dokumentacja Architektury: LogTransformerFusion (Milestone 3)

## 1. Topologia Architektury i Fuzja Reprezentacji
Model `LogTransformerFusion` jest autorską adaptacją architektury Transformer (Vaswani et al., 2017) do celów klasyfikacji wielomodalnych ciągów logów systemowych. W przeciwieństwie do sieci rekurencyjnych (BiLSTM), Transformer przetwarza całą sekwencję jednocześnie, co wymaga wstrzyknięcia informacji o porządku zdarzeń oraz sprowadzenia różnych modalności do wspólnej przestrzeni wymiarowej $d_{model}$.

Zdefiniujmy wejście dla pojedynczej sesji użytkownika o długości $T$. Na wejściu znajdują się dwa tensory:
* Macierz zdarzeń dyskretnych $E \in \mathbb{N}^{T}$ 
* Tensor opóźnień czasowych $t \in \mathbb{R}^{T \times K}$ (gdzie $K=4$ stanowi wektor znormalizowanych cech czasowych).

Wybór architektury opartej wyłącznie na bloku **Enkodera** (*ang. Encoder-only*), inspirowanej modelami z rodziny **BERT**, podyktowany jest naturą zadania badawczego. Klasyfikacja profilu użytkownika na podstawie zamkniętej sesji nie wymaga autoregresyjnego generowania nowych tokenów (do czego zoptymalizowane są modele* Decoder-only*, np. GPT), ani sekwencyjnego tłumaczenia danych (wymagającego struktury *Encoder-Decoder*, np. T5). Architektura **Encoder-only** pozwala na głębokie modelowanie kontekstu dwukierunkowego (ang. bidirectional context). Dzięki temu mechanizm uwagi może w jednym przejściu analizować relacje między zdarzeniami występującymi zarówno na początku, jak i na końcu sesji, co jest kluczowe do wychwycenia spójnych wzorców behawioralnych.

Operacja Fuzji Wczesnej (Early Fusion) realizowana jest poprzez addytywne łączenie trzech komponentów:
1. **Event Embeddings:** Dyskretne tokeny są rzutowane za pomocą macierzy wag do przestrzeni $\mathbb{R}^{d_{model}}$.
2. **Temporal Projection:** Ciągłe wektory czasowe przechodzą przez nieliniowy rzutnik (Multilayer Perceptron z aktywacją GELU), mapujący je z wymiaru $K$ do $d_{model}$.
3. **Learnable Positional Encodings:** W celu kompensacji braku rekurencji, model uczy się własnych wektorów pozycyjnych $P \in \mathbb{R}^{T \times d_{model}}$.

Reprezentacja wejściowa $X^{(0)}$ przekazywana do pierwszej warstwy enkodera wyraża się wzorem:

$$X^{(0)} = \text{LayerNorm}(\text{Embed}(E) + \text{MLP}_{time}(t) + P)$$

## 2. Mechanizm Multi-Head Self-Attention i Maskowanie
Głównym mechanizmem wydobywania zależności behawioralnych (np. odstępu czasu między dodaniem do ulubionych a paniką związaną z brakiem środków) są bloki Enkodera. W docelowej konfiguracji modelu zastosowano stos składający się z $N=4$ połączonych szeregowo warstw Enkodera, bazujących na Multi-Head Attention (MHA). Taka głębokość sieci (liczba powtórzeń bloku) została dobrana empirycznie – zapewnia ona wystarczającą pojemność reprezentacyjną do modelowania złożonych, nieliniowych zależności czasowo-sekwencyjnych, minimalizując jednocześnie ryzyko przeuczenia (*ang. overfitting*) na symulowanym zbiorze danych oraz redukując narzut obliczeniowy.

Dla każdej z głów atencyjnych wyliczane są macierze zapytań (Query), kluczy (Key) oraz wartości (Value):
$$Q = XW_Q, \quad K = XW_K, \quad V = XW_V$$

Mechanizm uwagi z uwzględnieniem maskowania paddingu (pomijanie sztucznych zer wyrównujących sesje w paczce) definiowany jest jako:
$$\text{Attention}(Q, K, V) = \text{softmax}\left(\frac{QK^T}{\sqrt{d_k}} + M\right)V$$

Gdzie $M$ jest macierzą maski, w której pozycje odpowiadające zdarzeniom typu `<PAD>` przyjmują wartość $-\infty$, co skutkuje wyzerowaniem ich wagi po nałożeniu funkcji softmax.

## 3. Klasyfikacja Behawioralna (The Classification Token)
Wzorując się na paradygmacie modeli BERT (Devlin et al., 2018), do rozwiązania problemu spłaszczenia dwuwymiarowej macierzy $[T, d_{model}]$ wykorzystano sztuczny token klasyfikacyjny `<CLS>`. 

Token ten jest wstrzykiwany na pierwszej pozycji każdej sekwencji (indeks 0). Ponieważ mechanizm MHA pozwala każdemu tokenowi wymieniać się informacją z każdym innym, reprezentacja `<CLS>` na wyjściu z ostatniej, $N$-tej warstwy Enkodera ($X^{(N)}_{0}$) staje się zagregowanym wektorem cech całej sesji:

$$h_{cls} = X^{(N)}_{0} \in \mathbb{R}^{d_{model}}$$

Ostateczny rozkład prawdopodobieństwa przynależności użytkownika do jednej z $C$ klas wyliczany jest przez głowicę decyzyjną (Classification Head):

$$\hat{y} = \text{softmax}(W_2 \cdot \text{GELU}(W_1 \cdot h_{cls} + b_1) + b_2)$$

Dzięki takiemu podejściu wyeliminowano konieczność stosowania operacji statystycznych (np. Mean Pooling), pozwalając mechanizmowi atencji na dynamiczne ważenie zdarzeń na przestrzeni całej sesji giełdowej.

## 4. Metodyka Uczenia Modelu i Optymalizacja
Proces uczenia zaprojektowanej architektury wymagał starannego doboru hiperparametrów optymalizacyjnych, ze względu na dużą wrażliwość modeli opartych na mechanizmie atencji (Transformers) na początkowe fazy treningu.

Do minimalizacji funkcji błędu entropii krzyżowej (Cross-Entropy Loss) wykorzystano optymalizator **AdamW** (Loshchilov & Hutter, 2017), który dekapsuluje mechanizm zaniku wag (Weight Decay), poprawiając zdolności generalizacyjne modelu lepiej niż standardowy optymalizator Adam. Parametr Weight Decay ustalono na poziomie $\lambda = 0.01$.

### Harmonogram Szybkości Uczenia (Learning Rate Scheduling)
Ze względu na specyfikę modeli Transformer, zastosowano hybrydową strategię sterowania współczynnikiem uczenia (Learning Rate, LR):
1. **Faza Rozgrzewki (Linear Warmup):** Przez początkowe 500 iteracji LR wzrastał liniowo od ułamkowej wartości bazowej do ustalonego pułapu $5 \times 10^{-4}$. Zapobiega to gwałtownym aktualizacjom wag w początkowej fazie uczenia (tzw. zjawisko *Early Divergence*).
2. **Faza Zaniku Skokowego (Multi-Step Decay):** Po osiągnięciu szczytowej wartości, współczynnik LR był redukowany o rzędy wielkości ($\gamma = 0.1$) w wyznaczonych punktach kontrolnych (tzw. kamieniach milowych), umożliwiając precyzyjną zbieżność modelu w minimach lokalnych.

Dodatkowo, wprowadzono mechanizm obcinania gradientów (Gradient Clipping) na poziomie $1.0$, chroniący sieć przed problemem eksplodujących gradientów.

## 5. Metryki Ewaluacyjne
Zważywszy na charakterystyczne dla systemów webowych zjawisko niezbalansowania klas użytkowników (ang. *class imbalance*), zrezygnowano z polegania wyłącznie na metryce dokładności (Accuracy). Głównym kryterium ewaluacyjnym wyboru modelu zoptymalizowanego był wskaźnik **Macro F1-Score**. 

Jest to średnia harmoniczna precyzji (Precision) i czułości (Recall), wyliczana niezależnie dla każdej klasy decyzyjnej, a następnie uśredniana bez nakładania wag na liczność reprezentacji. Równanie określające wartość $F1_{macro}$ prezentuje się następująco:

$$F1_{macro} = \frac{1}{C} \sum_{i=1}^{C} 2 \cdot \frac{\text{Precision}_i \cdot \text{Recall}_i}{\text{Precision}_i + \text{Recall}_i}$$

Gdzie $C$ oznacza liczbę modelowanych profili behawioralnych. Podejście to gwarantuje, że skuteczność wykrywania profilu rzadkiego (np. analityka strategicznego) jest z naukowego punktu widzenia traktowana na równi z poprawną klasyfikacją dominującego profilu pasywnego (WindowShopper).