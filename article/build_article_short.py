"""Build the 1.5-page Café Poliçe version from the same outputs (numbers come from metrics.json / evt_uncertainty.json)."""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt

from build_article import BYLINE, E, GITHUB, HF, NAVY, ORANGE, ROOT, TITLE, bottom_border, c, f, gpd, pp, s, tr

SUBTITLE = "Açık veriyle trafik sigortası fiyatlama: frekans, şiddet ve kuyruk riski"
SPOT = (f"{tr(c['policies'])} poliçelik açık bir trafik portföyünde frekansı, şiddeti ve büyük hasarları ayrı ayrı modelledim. "
        "Makine öğrenmesi riski daha iyi sıraladı; ama asıl ders, yılın faturasını birkaç büyük hasarın yazmasıydı.")

SECTIONS = [
    ("Veri", [
        f"Veri, CASdatasets koleksiyonundan freMTPL2: Fransız bir sigortacının trafik portföyü, OpenML'de CC0 lisanslı. "
        f"Temizlik sonrası {tr(c['policies'])} poliçe, {tr(c['total_exposure'])} poliçe-yılı ve {tr(c['claims'])} hasar kaldı; yıllık frekans yüzde {tr(c['portfolio_frequency']*100, 1)}. "
        f"Hasar sayısı olup tutarı olmayan {tr(c['claims_without_amount'])} poliçeyi hasarsız kabul ettim; bu tek karar bile saf primi değiştiriyor.",
    ]),
    ("Frekans: Makine öğrenmesi daha iyi sıralıyor", [
        f"Yüzde 20'lik test portföyünde riski sıralama gücü (Gini) Poisson GLM'de {tr(f['poisson_glm']['gini'], 3)}, Poisson gradient boosting'de {tr(f['poisson_gbm']['gini'], 3)}. "
        "Kazanç gerçek; bedeli ise açıklanabilirlik. \"Neden bu fiyat?\" sorusu, doğruluk kadar önemli.",
    ]),
    ("Şiddet: Ortalaması bile belirsiz bir kuyruk", [
        f"Hasar başına tutarın medyanı 1.172, ortalaması 2.279 avro; en büyük tek hasar 4,07 milyon avro. Yüzde 99 eşiğinin ({tr(s['threshold_u_p99'])} avro) üstündeki "
        f"{s['claims_above_u']} hasara Uç Değer Teorisi'nin Genelleştirilmiş Pareto dağılımını uydurdum: şekil parametresi ξ = {tr(gpd['xi'], 2)}, "
        f"bootstrap güven aralığı {tr(E['xi_ci95'][0], 2)}–{tr(E['xi_ci95'][1], 2)}. ξ 1'i aşarsa ortalama tanımsızlaşır; yeniden örneklemelerin yüzde "
        f"{tr(E['share_xi_ge_1']*100, 0)}'sinde aştı. Test yılında en büyük 10 hasar toplam maliyetin yüzde {tr(E['test_top10_share']*100, 0)}'sini oluşturdu.",
    ]),
    ("Saf prim: Yükleme bir risk iştahı kararı", [
        f"Motor; frekans (gradient boosting) × olağan şiddet (Gamma GLM) + büyük hasar yüklemesinden oluşuyor (Gini {tr(pp['freq_gbm_x_sev']['gini'], 3)}). "
        f"Gözlenen büyük hasarlardan gelen yükleme ({tr(E['empirical_load'])} avro) ile tahmin/gerçekleşen oranı {tr(E['pp_ratio_empirical_load'], 3)}; "
        f"GPD yüklemesiyle ({tr(s['large_loss_load_per_claim'])} avro) {tr(E['pp_ratio_gpd_load'], 3)}, yani yüzde 23 daha ihtiyatlı. "
        "Hangisinin seçileceği sermayeye, reasüransa ve rekabete bağlı: Model kararı vermez, kararın bedelini görünür kılar.",
    ]),
    ("Sektör için üç ders", [
        "Birincisi, makine öğrenmesi riski daha iyi sıralıyor ama tek başına bir tarife değil; GLM ile birbirini denetleyen iki göz olarak çalışmalı. "
        "İkincisi, kuyruk bu kadar ağırken geçmiş deneyim gelecekteki büyük hasarı sistematik olarak eksik gösterebilir; EVT bu riski görünür kılar. "
        f"Üçüncüsü, veri kalitesi her şeyin önünde: {tr(c['claims_without_amount'])} tutarsız kaydı nasıl ele aldığınız, primi doğrudan değiştiriyor. "
        "Veri yönetimi fiyatlamanın arka odası değil, temelidir.",
    ]),
    ("Sınırlılıklar", [
        "Fransız ve tek dönemlik veri; enflasyon, IBNR ve reasürans modelde yok, kuyruk modeli 199 hasara dayanıyor. "
        "Sonuçlar bir yöntem gösterimidir, Türkiye için tarife önerisi değildir.",
    ]),
]

FIGURES = {  # keyed by the section heading before the colon
    "Frekans": [("04_lorenz.png", 8, "Grafik 1. Test portföyünde Lorenz eğrileri: köşegenden uzaklaştıkça sıralama gücü artar.")],
    "Şiddet": [("06_yogunlasma.png", 12, "Grafik 2. Test yılında hasar maliyetinin en büyük hasarlarda yoğunlaşması.")],
}


def build_docx(path: Path) -> None:
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(2.3)
    sec.top_margin = sec.bottom_margin = Cm(2.0)
    normal = doc.styles["Normal"]
    normal.font.name, normal.font.size = "Calibri", Pt(11)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.15
    h = doc.styles["Heading 1"]
    h.font.name, h.font.size, h.font.color.rgb, h.font.bold = "Calibri", Pt(13), NAVY, True
    h.paragraph_format.space_before, h.paragraph_format.space_after = Pt(10), Pt(4)

    for text, size, color, bold, italic in ((TITLE, 24, NAVY, True, False), (SUBTITLE, 12.5, ORANGE, False, False),
                                            (BYLINE, 9.5, None, False, True), (SPOT, 11.5, None, True, False)):
        p = doc.add_paragraph()
        r = p.add_run(text)
        r.bold, r.italic, r.font.size = bold, italic, Pt(size)
        if color:
            r.font.color.rgb = color
        if text == BYLINE:
            bottom_border(p)

    for heading, paras in SECTIONS:
        doc.add_heading(heading, level=1)
        for text in paras:
            doc.add_paragraph(text)
        for img, width, caption in FIGURES.get(heading.split(":")[0], []):
            doc.add_picture(str(ROOT / "outputs" / "charts" / img), width=Cm(width))
            doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
            cp = doc.add_paragraph()
            cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = cp.add_run(caption)
            r.italic, r.font.size = True, Pt(9)

    p = doc.add_paragraph()
    r = p.add_run(f"Kod: {GITHUB}  ·  Model: {HF}\nKaynak: Dutang, C. ve Charpentier, A., CASdatasets (freMTPL2, OpenML 41214/41215, CC0).")
    r.italic, r.font.size = True, Pt(8.5)
    doc.save(path)


if __name__ == "__main__":
    out = ROOT / "article" / "CafePolice_HasarAnalizi_MehmetAliKaya_Kisa.docx"
    build_docx(out)
    print("written:", out)
