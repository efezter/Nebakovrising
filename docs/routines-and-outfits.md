# Rutin süreleri, kıyafetler ve NPC isimleri

Tek düzenlenebilir rutin dosyası: mod klasöründeki `Config/routines.lua`.
Değerler saniyedir; pozitif tam sayı ve `minSeconds <= maxSeconds` olmalıdır.
Değişiklikleri save'i yeniden yükleyerek veya oyunu yeniden başlatarak uygula.
Mod açılışta dosya yolunu loglar; geçersiz/okunamayan config için önceki veya
varsayılan değerleri korur. Her karede dosya okunmaz.

| Bölüm | Başlangıç değerleri | Anlam |
|---|---|---|
| `breakfast` | 10–20 | Sabah masada yemek yeme süresi |
| `eveningMeal` | 10–20 | Akşam masada yemek yeme süresi |
| `patrol` | 10–180 | Patrol noktasında bekleme süresi |
| `wakeStagger` | 5–15 | Saat 08:00'de ilk guard hemen uyandıktan sonra guard'lar arasındaki aralık |
| `eveningMealStagger` | 10–30 | Akşam yemeğine gönderilen NPC'ler arasındaki aralık |

Sohbet sıklığı ayrı bir davranış ayarıdır ve mevcut
`D:\NebakovVoice\config\conversations.json` dosyasında kalır.

## Kıyafet akışı

Uyurken yalnız `body_cloth` (35), `body_cloth_padded` (36) ve
`leg_trousers_padded` (41) slotları bırakılır. Eldiven, ayakkabı, mahmuz,
takı, dış katmanlar ve silahlar dahil diğer insan ekipman slotları çıkarılır.
`UnequipInventoryItem` kullanılır; eşya silinmez veya envanter dışına taşınmaz.
Mevcut uyanış akışı çıkarılan ekipmanı tekrar kuşanır.

Kazandaki yemeğe yürümeye başlamadan önce hood, coif, padded/mail coif,
cap ve helmet slotları çıkarılır. Patrol yeniden başladığında aynı envanterdeki
başlıklar geri kuşanılır. Yemek ve uyku akışı yeni kıyafet preset'i üretmez.

Kazandan sonra masaya geçişte NPC zaten ayaktaysa gereksiz standing isteği ve
WaitAction atlanır. Oturan/yaslanan NPC'nin gerçek ayağa kalkma kontrolü korunur.
Kazan animasyonunun tamamlanma sinyali ve yemek koltuğu rezervasyonu korunur.

## Etkileşim noktasına yaklaşma

Patrol sandalyelerinde önce obje merkezine yürüyen ayrı Move artık çalışmaz;
bench StanceElement kendi yaklaşma ve oturma başlangıcını seçer. Yemek sandalyeleri
zaten bu yöntemi kullanıyordu. Yatakta da aynı şekilde lying StanceElement
yaklaşmayı yönetir; yaklaşma zaman aşımı korunur. Uyku kıyafeti, yatma girişinin
tamamlanması onaylandıktan sonra çıkarılır. Yeni varsayımsal koordinat ofsetleri
veya doğrudan konum/açı ataması eklenmedi. Gerçek oyun yolu ve animasyonları
ayrıca test edilmelidir.

## Görünen isimler ve prompt

Modun kendi 50 karakter/görünüm kimliği için sabit üretilmiş isimler vardır.
Spawn sırasında mevcut görünüm havuzundan rastgele seçilen kimlik ismi de belirler;
aynı kimlik yeniden kullanılırsa aynı isim kullanılır. Bu, native UI ile promptun
aynı kişiyi adlandırmasını sağlar. Runtime entity adı, rol, WUID ve spawn sistemi
değişmez. İsim ayrıca mevcut NPC save kaydında `displayName` olarak tutulur.

Skald tablosu modun isim anahtarlarını kullanır. Çeviri paketi
`Localization/english_xml.pak`, isimleri native UI'ye sağlar; oyunun belgelenmiş
mod İngilizce fallback'i diğer diller için de geçerlidir. Kaynak dosya
`localization_src/text__nebakovrising.xml` içindedir. `tools/build_pak.py` bu paketi
de kontrol ederek oluşturur; görünüm havuzu yeniden üretilirse
`tools/gen_appearance.py` isim eşleşmelerini de tekrar üretir.

Lua bağlamında `guard_a_name` ve `guard_b_name` prompta gider. `Marek`/`Hertl`
JSON speaker alanları ses yönlendirme kimlikleri olarak korunur. Prompt, konuşulan
cümlede gerçek adı kullanmasını ve ilk cümlede değişken, kısa bir selamlaşma
yapmasını ister. Bu, model talimatıdır; katı bir metin son işlemesi eklenmez.

## Ertelenen sorun

Bölge dışına çıkıp dönünce coif/chainmail'in envanterden kaybolması doğrulanamadı.
Restore sırasında preset'in yeniden uygulanması şüpheli bir yoldur, ancak belirli
iki slotun kaybına neden olduğu kanıtlanmadı. Kullanıcının isteği doğrultusunda bu
akış değiştirilmedi; kayıp eşyalar otomatik üretilip envantere eklenmedi.

184 otomatik test; kıyafet slotları, envanterin korunması, sabah/akşam süreleri,
native yaklaşma yapısı, standing kısa yolu ve UI/prompt isim eşleşmelerini kapsar.
Mevcut Lua/Python dört satırlık ses testi de geçti. Oyun içi görsel test yapılmadı.

## Lean çıkışı, handgonne ve sohbet kapanışı

Lean girişi başlamadan `needsStandingReset` işareti konur; mevcut NPC save
kaydında tutulur. Böylece temel stance `standing` olsa bile ortak stand fonksiyonu
hızlı yolu kullanmaz: native standing isteği ve WaitAction onayı tamamlanmalıdır.
İşaret yalnız güncel activity token'ıyla bu onaydan sonra temizlenir. Kesilen
aktivite/stream dönüşünde de korunur. Gerçek lean çıkış animasyonu oyun içinde
doğrulanmalıdır; test motoru fiziksel animasyonu taklit eder.

Ranged guard'ın Secondary weapon set'inde sağ elde `rifle` türü handgonne varsa,
guard noktası hizalaması ve bekleme süresi boyunca sağ el HandContentElement'i
açık tutulur. Handgonne için doldurma veya ateş etme komutu eklenmedi. Aynı sette
eski crossbow varsa guard noktasında handgonne önceliklidir. Crossbow kendi
sol el/yükleme akışını korur; zaten doluysa yeniden doldurulmaz. Handgonne için
yeni elde tutma davranışı guard noktalarıyla sınırlıdır; bench/lean bekleme
dallarının silah seçimi genişletilmedi.

Üç prompt profilinin son/final dördüncü cümlesi konuya bağlı doğal bir kapanış
isteyecek şekilde güncellendi. Yeni soru, konu veya cliffhanger açmaması; her
seferinde aynı vedayı kullanmaması ve oyun rutiniyle çelişen ayrılma talimatları
üretmemesi istenir. Dört satır ve mevcut selamlaşma/isim yönlendirmesi korunur.
Bu değişiklik yeniden üretilecek konuşmaları etkiler; hazır WAV'lar değişmez.

206 otomatik test ve iki ayrı Lua/Python ses akışı kontrolü geçti. Handgonne
animasyonu, lean çıkışı ve üretilen kapanışların doğallığı oyun içinde denenmelidir.
