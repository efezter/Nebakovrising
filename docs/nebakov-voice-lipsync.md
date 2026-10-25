# Ağız hareketi ve servis üzerinden yeni üretim

Kullanıcı, hazır servis WAV'larıyla NPC buluşmasını ve ses oynatmayı oyun içinde doğruladı. Bu güncellemenin yeni üretim/yüz animasyonu birleşimi ayrıca oyun içinde test edilmeli.

## Yerel kaynak doğrulaması

- `KCD2.AI.NPC-main.zip`: Python `_face_talk_dispatch`, NPC kimliği ve replik süresini `FACETALK` ile gönderiyor; konfigürasyon yüz animasyon katmanını 12 olarak tanımlıyor. İlgili Lua handler'ı ZIP içinde bulunamadı.
- Kurulu oyunun `Data/Facials/Facials_english-part0.pak` içindeki `Animations/FacialAnimations.img` indeksinde `animations/humans/facials/cin/fa_cin_talk_neutral_01.caf` mevcut.
- `IPL_Characters-part3.pak` içindeki `male.chrparams`, yüz CAF'larını `Animations\humans\facials` altında wildcard ile kaydediyor.
- Yerel binding belgeleri `StartAnimation` / `StopAnimation` API'lerini; oyunun `AnimObject.lua` dosyası slot/katman/blend/hız/döngü argüman sırasını gösteriyor.

`VoiceFace`, bu mevcut CAF'ı slot 0 / katman 12 üzerinde döndürür. Gerçek fonem eşlemesi yapılmaz. Görsel sonucun doğru olduğu yalnız oyundaki testten sonra söylenebilir. Başlatma başarısızsa ses devam eder; teşhis `kcd.log` içinde `[VoiceFace]`, telemetride `director.face` alanında bulunur. `clip_not_loaded` ve `animation_api_unavailable` ayrı raporlanır.

## Yaşam döngüsü

Python, replik başlamadan `line_start(index,duration_ms)` yollar ve Lua onayını bekler. Lua konuşmacıyı replik sırasından seçer; dışarıdan entity ID veya animasyon kodu alınmaz. Ses bitince `line_end` yollanır. Yalnız yüz katmanı durdurulur. Konuşma iptali, dünya sıfırlaması ve süre güvenliği de aynı temizliği yapar. Eski süre callback'i sonraki repliki durduramaz; despawn/replacement kimliği kontrol edilir.

Mevcut motorun servis arayüzü varsa adapter yalnız `/health` kontrolü yapar; model yüklemez. Yeni diyaloğu Gemini ile üretir, JSON'u kaydeder ve mevcut `render_with_chatterbox` fonksiyonunu çağırır. Dört WAV okunabilir/geçerli olmadan oynatıcıya sonuç verilmez. Kokoro sürümü için eski adapter yolu korunur.

## Oyun testi

1. Önceki bridge penceresini kapat; mevcut TTS servisini açık tut. Güncel Lua'yı yüklemek için oyunu yeniden başlat.
2. Bir guard'ın yanında `nebakov_voice_face_test` kullan. Yalnız ağız/yüzün hareket edip etmediğine bak; 6 saniye içinde otomatik durur.
3. `start_patrol_conversations.cmd` aç. `engine_ready` sonrasında iki patrol guard'ının yakınında `nebakov_conversation_test` kullan.
4. Her replikte yalnız konuşan NPC'nin yüzü hareket etmeli; ses/animasyon bitince durmalı. `nebakov_conversation_stop` her ikisini temizlemeli.

Hazır WAV karşılaştırması için `test_patrol_voices.cmd` korunur. Yeni üretimde ilk TTS model yüklemesi uzun sürebileceğinden varıştan sonra bekleme sınırı 240 saniyedir.
