# Dinamik guard sesleri ve buluşma

## Kullanım

1. Oyun, önceki voice bridge ve TTS router pencerelerini kapatıp yeniden başlat: `D:\NebakovVoice\start_tts_router.ps1`, ardından `D:\NebakovVoice\server\start_patrol_conversations.cmd`.
2. Köprü başlangıçta `D:\NebakovVoice\tts\voices` klasöründeki `guard*.wav` dosyalarını tarar. `guard1.wav`, `guards16.wav`, `guards_new.wav` desteklenir. Dosya adında yalnız ASCII harf/rakam, `_` ve `-` kullanılır. Örnekler 5 saniyeden uzun olmalı. Geçersiz örnekler loglanır ve havuza alınmaz; mevcut `guard1.wav` geçersizse yanlış fallback kullanmamak için başlangıç durdurulur.
3. Nebakov'da `nebakov_voice_assignments` ile kalıcı atamaları gör. `nebakov_conversation_test` iki uygun patrol guard'ını seçer. Rastgele tetikleme kapalıdır.
4. Birinci guard bekler; ikinci yaklaşık 1,3 metreye yürür (varış sınırı 1,8 metre). İkisinin gövde yönü kontrollü yaw adımlarıyla birbirine çevrilir; sonuç parametresiz GetDirectionVector() ile doğrulanır. Gövde dönüşünde Entity.GetAngles/SetAngles çifti kullanılır; Actor.SetAngles ile Entity.GetAngles karıştırılmaz. Her iki yön de 20 derece toleransla doğrulanmadan ses başlamaz.
5. Save alıp yükledikten sonra aynı guard'ın dosya adı korunmalı. Ölen guard'ın sesi yeni bir guard'a verilebilir.

## Atama kuralları

Dosyanın tam adı `voicesampleid` olur. Mevcut NPC kayıtları ve ses kataloğu, zaten kullanılan serialize edilen `BasicEntity.health` save store'unda tutulur. Yalnız eksik atamalar yapılır; yeni ses seçimi boş örnekler arasında rastgeledir. Hayatta olan fakat geçici olarak stream dışındaki guard'ın sesi rezerve kalır.

Havuz dolarsa `guard1.wav` kullanılır. Klasörde bu ad hiç yoksa doğal sıralamadaki ilk geçerli örnek fallback olur. Sonradan havuz büyüdüğünde yaşayan guard'ların sesleri değiştirilmez; yeni örnekler sonraki atamalarda kullanılabilir. Önceden overflow nedeniyle aynı sesi alan yaşayan guard'lar da sesini korur.

Atanmış bir dosya kaldırılırsa save'deki kimlik korunur; oynatma için mevcut fallback kullanılır. Aynı isimle geri koyulduğunda eski kimlik tekrar kullanılabilir. Dosyaları yeniden adlandırmak yeni bir ses kimliği oluşturur.

Yeni sample ekledikten sonra **voice bridge'i yeniden başlatmak** yeterlidir; güncellenmiş servis her istekte dosya adına göre referans bulur. Oyun/save atamalarını yeniden kurmaya veya kod değiştirmeye gerek yoktur. Katalog yalnız köprü başlangıcında taranır; oyunda dosya tarama yapılmaz. Kontrol paketini sınırlamak için katalog üst sınırı 128 örnektir.

## Servis aktarımı

Lua, her konuşmacının `voicesampleid` bilgisini konum paketine ekler. Python bunu hem `conversation.json` satırlarına hem `/render` isteğinin `voicesampleid: {Marek: filename, Hertl: filename}` alanına koyar. Router bu alanı seçili Standard/Turbo worker'a iletir. Worker referansı `tts/voices` içinde doğrular ve mevcut conditioning cache'i dosya yolu/zamanına göre kullanır. Orijinal Gemini üretimi, TTS model yükleme ve sentez işlemleri korunur.

## Sabah

08:00'de uyuyan guard'lar rastgele sıralanır; ilk guard hemen uyanmaya başlar, sonraki guard'lar 5–15 saniyelik aralıklarla uyanır. Sıra runtime WUID ile kaydedilir ve her gece sıfırlanır; worker rolleri guard sırasına katılmaz. Önceden rastgele sıralama kullanmak, her adımda kalanlardan rastgele seçmekle aynı dağılımı verir.

## Doğrulama sınırı

140 otomatik test geçti. Bunlar katalog → Lua onayı → save kaydı → telemetri → üretim işi aktarımını; 15 benzersiz ses/overflow, ölüm, yeniden yükleme, dosya ekleme/çıkarma ve Standard/Turbo yönlendirmesini kapsıyor. Gerçek Python oynatıcı + Lua/BT buluşma/dönme akışı, WAV fixture'ları ve sessiz SDL çıkışıyla da geçti. Oyun navigasyonu, yeni karşılıklı dönüş ve gerçek save/load ses atamaları ayrıca oyun içinde doğrulanmalı.
