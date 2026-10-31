# Bir Yılın Faturasını On Hasar Yazar
Motor sigortasında frekans makinesi, kuyruk istatistiği
678 bin poliçelik açık Fransız motor portföyünde (freMTPL2, 26.406 hasar) soru nettir: primi geleneksel model mi, makine mi daha iyi kurar? Cevap ikisinin karışımında.
Frekansı Poisson GLM ile GBM karşılaştırdık: Gini 0.273'ten 0.321'e çıkıyor (D² %4.1'den %6.2'ye). Makine, poliçe riskini gelenekselden belirgin biçimde iyi ayırıyor.
Ama kuyrukta tablo değişiyor. 99. yüzdelik (16.024 €) üstü 199 hasara GPD uyduruldu: şekil ξ=0.87, güven aralığı 0.59–1.11; simülasyonların %19.8'inde ξ≥1. En büyük 10 hasar, test yılı maliyetinin %20.8'ini oluşturuyor — tek Tweedie GLM bunu göremez.
Sonuç: frekansta makine, kuyrukta EVT; saf prim Gini 0.331, öngörülen/gözlenen 0.999.
## Kaynaklar
GitHub: github.com/000MAK/cafepolice-actuarial-loss-engine
Hugging Face: huggingface.co/makactuary/fremtpl2-pricing-engine

| Bileşen | Geleneksel | Yeni | Kazanan |
|---|---|---|---|
| Frekans (Gini) | Poisson GLM 0.273 | GBM 0.321 | makine |
| Büyük hasar kuyruğu | Tweedie GLM | GPD ξ=0.87 | EVT |
| Saf prim (Gini) | 0.273 | 0.331 | karma |
