# Patrol sohbetleri — kurulum ve oyun testi

Güncel kullanım: [JSON profilleri, rastgele patrol sohbetleri ve önce-hazırla akışı](nebakov-natural-patrol.md).

Güncel aşama: [dinamik guard ses havuzu, kalıcı atamalar ve karşılıklı dönme](nebakov-guard-voices.md).

## Yeni üretim ve ağız animasyonu testi

TTS servisi açıkken `D:\NebakovVoice\server\start_patrol_conversations.cmd` çalıştırılır. Bu mod, yeni dört repliki mevcut `conversation_engine.generate_conversation` ile üretir ve mevcut `render_with_chatterbox` fonksiyonu üzerinden servise gönderir. Motor/TTS kodu değiştirilmez. Çıktılar yine `D:\NebakovVoice\output\conversations` altında tutulur.

Oyun yeniden başlatıldıktan sonra iki patrol guard'ının 20 metre yakınında `nebakov_conversation_test` komutu kullanılır. NPC'ler buluşurken üretim sürer; varış ve tüm WAV'ların doğrulanması beklenir. Her replikin `line_start` komutu oyun tarafından onaylanınca ses başlar; `line_end`, iptal ve süre güvenliği yüz katmanını temizler. Rastgele tetikleme hâlâ kapalıdır.

Yalnız animasyonu sınamak için `nebakov_voice_face_test` (5 saniye), durdurmak için `nebakov_voice_face_stop` kullanılabilir. İlk komut kayıtlı Marek'i, kayıt yoksa 20 metre içindeki en yakın aktif patrol guard'ını seçer. Ses üretmez. Ayrıntılar: [ağız animasyonu](nebakov-voice-lipsync.md).

## Güncel ilk test: servis tarafından hazırlanmış diyalog

TTS artık `D:\NebakovVoice\tts\tts_router.py` üzerinden çalışıyor. Mevcut servis ve üretim kodu değiştirilmedi. `chatterbox/` altındaki dört WAV desteklenir; tamamlanmamış çıktılar atlanır. Bu test üretim veya model yüklemesi başlatmaz. Rastgele sohbet varsayılan olarak kapalıdır (`randomEnabled=false`).

1. Eski **ses köprüsü** penceresini Ctrl+C ile kapat; TTS servisini açık bırakabilirsin.
2. Güncel paketi yüklemek için oyunu yeniden başlat. Bu modun `tools\test_patrol_voices.cmd` dosyasını çift tıkla (D: sürücüsündeki eski kopyayı değil). En yeni tamamlanmış diyalog seçilir.
3. Nebakov'da devriye yapan iki guard'ın 20 metre yakınına gel. Konsolda `nebakov_conversation_status` çalıştır; `Python=true`, `hazir=true` beklenir. Bağlantının oluşması birkaç saniye sürebilir.
4. `nebakov_conversation_test` yaz ve konsolu kapat. Biri bekler, diğeri yanına yürür. İkisi buluşunca hazır dört replik Marek/Hertl sırasıyla ve NPC konumlarından oynar. Sonra devriyeye dönerler.

Bu akışta `nebakov_voice_bind_pair` gerekmez. `python_not_connected` sürerse durum çıktısı ve `D:\NebakovVoice\output\bridge\bridge_events.jsonl` incelenmeli; TTS servisinin açık olması tek başına oyun köprüsünün bağlı olduğu anlamına gelmez. Aşağıdaki eski kurulum notları Kokoro sürümüne aittir; güncel servis için üstteki komutlar kullanılır.

25 Ekim 2026. Önceki ses oynatma aşaması kullanıcı tarafından oyun içinde doğrulandı. Bu aşamadaki yeni NPC seçimi, ayağa kalkma, buluşma ve çift yönlü kontrol akışı yerel testlerde geçti; gerçek oyun navigasyonu ve kontrol dosyasının Lua tarafından okunması ayrıca doğrulanmalı.

## Başlatma

1. Önceki NebakovVoice Python penceresini Ctrl+C ile kapat. Güncel mod paketini yüklemek için oyunu yeniden başlat ve Nebakov'daki kaydı yükle.
2. `D:\NebakovVoice\server\start_patrol_conversations.cmd` dosyasını çalıştır. `engine_ready` mesajını bekle. Yeni üretilen konuşmaları mevcut Gemini/Kokoro motoru hazırlayacak.
3. Henry ile devriye yapan iki mod guard'ına yaklaş. İkisi de Henry'nin 20 metre çevresinde ve yaklaşık aynı katta olmalı. Yemek yiyen/uyuyan guard bu test için uygun değildir.
4. Konsolda:

   ```text
   nebakov_conversation_start
   nebakov_conversation_status
   ```

   Python tarafında `control_ack` ve `accepted: true` görünmeli. Durum komutunda `Nebakov=true`, `Python=true`, `hazir=true` beklenir. `hazir=false`, modelin yüklenmesini veya önceki iptal edilmiş işin tamamlanmasını beklediğini gösterebilir.

5. Rastgele beklemeyi atlayıp anında denemek için:

   ```text
   nebakov_conversation_test
   ```

   İki uygun NPC otomatik seçilir. Bu akış `nebakov_voice_bind_pair` gerektirmez; eski bind komutu eski ses testine geçmek için yeni yöneticiyi durdurur.

6. Konsolu kapat ve gözlemle: iki guard mevcut patrol davranışından çıkar; oturuyorlarsa önce ayağa kalkar. Birinci bekler, ikinci birincinin yaklaşık 1,8 metre yakınına yürür. Üretim bu yaklaşma aşamasında başlar. Sesler hazır **ve** ikinci NPC varmışsa konuşma çalar. Konuşma bitince ikisi de scheduler üzerinden o an uygun görevine döner.

Gemini/TTS kullanmadan aynı buluşma akışını mevcut WAV'larla denemek için `start_patrol_conversations.cmd` yerine `D:\NebakovVoice\server\test_patrol_voices.cmd` açılır. Aynı konsol komutları kullanılır. Bu modda rastgele tetikleme de etkin olduğu için test komutu verilmeden bir buluşma başlamış olabilir.

## Otomatik tetikleme ve ayarlar

Yeni runtime bağlı ve hazırken yönetici, Nebakov içinde rastgele 30–60 saniyelik aralıklarla uygunluk kontrolü yapar. Test komutu bu rastgele beklemeyi atlar; bölge, patrol, mesafe, tek aktif konuşma ve cooldown koşullarını korur.

`src/Scripts/mods/nebakovrising.lua` içindeki `Config.conversations`:

| Ayar | Varsayılan |
|---|---|
| `searchRadius` | Henry çevresinde 20 m |
| `playerExitRadius` | Katılımcılardan 30 m uzaklaşınca iptal |
| `regionCenter` | Canlı testte gözlenen kapı çevresi: 1895, 1213, 52 |
| `regionRadius` / `regionExitRadius` | 250 / 280 m; sınırda sürekli açılıp kapanmayı önler |
| `regionHeight` | Merkezden dikey fark en fazla 80 m |
| `randomMinSeconds` / `randomMaxSeconds` | 30 / 60 s |
| `cooldownSeconds` | Başarılı sohbetten sonra genel 120 s |
| `npcCooldownSeconds` | Aynı NPC için 180 s |
| `preparationTimeout` | Ayağa kalkma/hazırlık için 30 s |
| `approachTimeout` | Yaklaşma için 35 s |
| `conversationTimeout` | Oynatma aşamasında en fazla 150 s |
| `peerTimeout` | Python kontrol bağlantısı için 12 s |

Bölge kontrolü, mevcut modun kullandığı `trosecko` dünya entity'sinin varlığı ve yapılandırılmış bölge mesafesiyle yapılır. Bu bir layer render kontrolü değildir. Bölge sınırı ilk oyun testinde kalenin istenen kapsamına göre ayarlanabilir. Değişiklikten sonra `python tools/build_pak.py` çalıştırılıp oyun yeniden başlatılır.

Uzakta üç saniyede bir bölge/kontrol kanalı kontrolü; bölgede boşta saniyede bir; aktif buluşma/konuşma sırasında 250 ms telemetry kullanılır. NPC aday taraması yalnız bölge içindeki tetikleme denemesinde yapılır. Yeni runtime'ın `--proximity` gibi eski mod ayarları bu seçim yarıçapını değiştirmez; seçim Lua yöneticisine aittir.

## Güvenli iptal ve dönüş

- Guard'ın yalnız rolü değil, çalışan `patrol` activity token'ı ve taze BT heartbeat'i doğrulanır. Combat/diyalog, ölüm/bilinç kaybı ve yemek/uykuya geçiş uygunluğu engeller veya mevcut sohbeti iptal eder.
- İki NPC tek sohbet kimliğiyle birlikte ayrılır. Onları başka bir sohbet aynı anda seçemez. Combat algısı, fizik ve yüksek öncelikli AI kesmeleri kapatılmaz.
- Ayağa kalkma ve yürüyüş mevcut BT stance/navigasyon düğümleriyle yapılır. Teleport veya doğrudan konum ataması yoktur. Yürüyüş başarısı ayrıca mesafe ve kat farkıyla doğrulanır; yol hatası/zaman aşımı iki katılımcıyı serbest bırakır.
- Patrol sırasında bekleme, yürüyüş veya oturma devam ederken yeni sohbet isteği paralel observer ile fark edilir. Mevcut activity heartbeat'i sosyal davranış boyunca sürer.
- Konuşma sonunda eski davranış kaydı zorla geri yüklenmez. Mevcut scheduler güncel yemek/uyku/patrol koşullarını tekrar değerlendirir. Sosyal kesilme, eski patrol noktasını bozuk yol olarak işaretlemez.
- Python kapanırsa, kontrol lease'i dolarsa, yeni kayıt yüklenirse veya eski token/session'dan komut gelirse sahne güvenli biçimde sona erer. Geç tamamlanan üretim ses başlatamaz.

Yöneticiyi durdurmak için `nebakov_conversation_stop`; yeniden başlatmak için `nebakov_conversation_start`. Python'u kapatmak için Ctrl+C. Aktif sahne varsa kapanışta iptal komutu gönderilir; ulaşamazsa Lua lease/zaman aşımı serbest bırakır.

## İletişim ve davranışa özel prompt

Lua, mevcut `NEBAKOV_VOICE_V1` paketine director kimliği, phase, varış, bölge, runtime sahibi ve kontrol onayı ekler. Python, oyun kökündeki `Data/Scripts/nebakov_voice/command.lua` dosyasına atomik olarak yalnız sabit kontrol komutları yazar. Lua önce `dofile` ile fiziksel dosya yollarını, sonra açık `Script.ReloadScript` yolunu dener. Okuyucunun başarılı sayılması için gerçek `Receive` çağrısı gözlenmelidir; yalnız `pcall` başarısı veya `LoadScript` dönüş değeri yeterli değildir. İlk kabul edilmiş heartbeat/onay, bu yolun gerçek kurulumda çalıştığı kabul testidir. `director.control_io` alanı okuyucuyu, yolu ve son hatayı raporlar.

Komutlar runtime kimliği, artan sıra numarası, session ve sohbet kimliği taşır. Tek komut slotunda onay gelmeden sıradaki eylem yazılmaz; yeniden deneme aynı sıra numarasını kullanır. Hazır ses/varış sonrasında oynatma için de Lua onayı gerekir. Prompt ve model çıktısı Lua kodu olarak aktarılmaz.

Şu anda yalnız `patrol` handler'ı var. Patrol bağlamı iki guard'ın görevini kısa süre bırakıp buluştuğunu, oyun saatini ve Henry'nin yakında dinleyici olduğunu anlatır. Yemek ve combat, patrol prompt'una düşmez; sonraki aşamada kendi kuralları ve prompt builder'larıyla eklenecek. Marek/Hertl konuşmacı alias'ları seçilen iki farklı runtime entity'sine bağlanır; NPC'lerin gerçek adları/spawn mekanizması değişmez. Mevcut motorun Gemini/Kokoro fonksiyonları korunur ve TTS normal worker yaşamında bir kez yüklenir.

## Beklenen loglar ve sorun giderme

`D:\NebakovVoice\output\bridge\bridge_events.jsonl` içinde tipik sıra:

```text
control_sent → control_ack
conversation_selected
generation_started → state: generating
state: waiting_arrival
control_ack: audio_ready
control_ack: playing
line_started / line_finished (dört satır)
conversation_finished
```

`conversation_selected` gerçek entity adlarını kaydeder. Varış üretimden önce veya sonra olabilir; `line_started`, Lua `phase=playing` onayından önce oluşmamalı.

Oyun logundaki açık ret nedenleri:

| Neden | Kontrol |
|---|---|
| `outside_nebakov` | Dünya ve bölge sınırı, Henry'nin konumu |
| `python_not_connected` | Yeni patrol başlatıcısı açık mı, kontrol onayı geliyor mu? |
| `python_not_ready` | `engine_ready` beklenmeli; önceki iptal edilmiş üretim sürüyor olabilir |
| `two_eligible_patrol_npcs_required` | İki guard gerçekten devriyede mi, 20 m içinde mi, kendi cooldown'ları bitti mi? |
| `conversation_active` | Önceki sahne devam ediyor |
| `global_cooldown` | Son sohbet sonrası bekleme sürüyor |

Python'da `control_waiting_for_ack` varsa yeni paketin yüklendiğini, oyunun açık olduğunu, `nebakov_conversation_start` çalıştırıldığını ve kontrol dosyasının logda belirtilen yolu kontrol et. Hızlıca tekrar tekrar test etmek için cooldown değerleri geliştirme ayarından azaltılabilir; test komutu bu koşulları gizlice atlamaz.

## Doğrulama sınırı

Yeni 23 test; gerçek Lua/BT koduyla seçim, rezervasyon, stance öncesi hareket yasağı, bloklanan yürüyüşün kesilmesi, başarılı buluşma sonrası scheduler'a dönüş, combat/bağlantı/zaman aşımı iptali, eski komutların reddi ve her iki üretim/varış sırası geçti. Dosya okuyucusu için `LoadScript` çağrısının sessizce etkisiz kalması, `dofile` ile değişen komutun okunması ve açık reload fallback'i de sınanıyor. Önceki 57 test de geçti.

Kurulu Python runtime, gerçek Lua komut/ACK kodu, gerçek dört WAV ve pygame'in sessiz SDL aygıtıyla sentetik uçtan uca test geçti. Navigasyon/stance API'leri bu testte mock'tur. Bu sonuç gerçek oyun içinde NPC'nin yürüdüğünü veya engine'in kontrol dosyasını okuduğunu kanıtlamaz; yukarıdaki oyun testiyle doğrulanmalıdır.
