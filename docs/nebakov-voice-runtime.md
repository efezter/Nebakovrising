# NebakovVoice — NPC konuşmalarını çalıştırma

25 Ekim 2026. İlk ses oynatma akışı kullanıcı tarafından oyun içinde doğrulandı. Sonraki patrol seçimi/buluşma sürümü için [patrol sohbetleri rehberi](nebakov-patrol-conversations.md) geçerlidir; aşağıdaki iki sabit konuşmacılı başlatıcılar bağımsız test olarak korunur.

## İlk oyun testi: mevcut seslerle

1. Mod paketi güncellendi; oyunu yeniden aç ve guard'ların bulunduğu kaydı yükle.
2. Önceki `start_bridge_positions.cmd` alıcısı veya başka NebakovVoice runtime penceresi açıksa kapat.
3. `D:\NebakovVoice\server\test_existing_npc_voices.cmd` dosyasını aç. Bu mod **Gemini/TTS çağırmaz**; en son tamamlanmış konuşmanın mevcut WAV'larını kullanır. Pencerede `READY` mesajını bekle.
4. Oyun konsoluna gir:

   ```text
   nebakov_voice_bind_pair
   ```

   İki mevcut guard Marek/Hertl etiketlerine bağlanır. Yeni NPC oluşturulmaz; isimleri, rolleri ve davranışları değiştirilmez.

5. İki NPC'ye de 8 metre içinde dur. NPC'lerin birbirine uzaklığı en fazla 6 metre olmalı. Şunu çalıştır:

   ```text
   nebakov_voice_talk
   ```

   Konsolu kapat. Dört satır sırayla Marek → Hertl → Marek → Hertl çalmalı. Python penceresinde her satır için `line_started` ve `line_finished`, sonunda `conversation_finished` görünmeli.

6. Konuşma sırasında kamerayı döndür; sağ/sol sesin konuşmacıyla birlikte değiştiğini dinle. Uzaklaşınca ses kısılmalı; NPC'lerden birinden 12 metre uzaklaşınca konuşma iptal edilmeli. Bu test başlatıcısında tekrar komutu için cooldown 5 saniye.

## Otomatik yeni konuşmalar

Test başlatıcısını Ctrl+C ile kapat. `D:\NebakovVoice\server\start_nebakov_voice.cmd` dosyasını aç. Ses aygıtı başlatılır, ayrı worker mevcut Kokoro modelini bir kez yükler. `engine_ready` mesajını bekle; `GEMINI_API_KEY` bu işlemin ortamında bulunmalı.

Oyunda yeniden `nebakov_voice_bind_pair` çalıştır. Henry iki guard'ın yakınına girdiğinde yaklaşık 1 saniye geçerli telemetry sonrasında bir konuşma işi başlar. Dört satır tek Gemini isteğiyle üretilir; WAV'lar tamamlanınca otomatik oynatılır. Üretim ve oynatma sırasında Lua thread'inde bekleme yoktur.

Varsayılanlar:

| Ayar | Değer |
|---|---|
| Henry'nin her iki NPC'ye uzaklığı | En fazla 8 m |
| İki NPC'nin birbirine uzaklığı | En fazla 6 m |
| Konuşmayı iptal eden Henry uzaklığı | NPC'lerden herhangi birinden 12 m |
| Başarılı konuşmadan sonraki cooldown | 120 saniye |
| Taze telemetry limiti | 2 saniye |
| Lua konum/kamera örneklemesi | 250 ms |
| Aynı anda konuşma | 1; bekleme kuyruğu yok |

Henry aynı yerde kalırken otomatik konuşma tekrarlanmaz. Yenisi için 12 m sınırının dışına çıkıp tekrar yaklaşmak ve cooldown'ın dolması gerekir. `nebakov_voice_talk` elle istek gönderir; mesafe ve cooldown kontrolleri yine uygulanır. `nebakov_voice_trigger_test` önceki tanı komutudur, konuşma isteği değildir.

NPC kaybolur, ölür, eşleşme/session değişir, yeni kayıt yüklenir veya telemetry kesilirse ses durur. Devam eden üretim sonucu geç gelirse çalınmaz. Mevcut kayıt yükleme davranışı gereği yeni kayıtta `nebakov_voice_bind_pair` tekrar çalıştırılır.

## Durdurma ve ayarlar

`nebakov_voice_stop` oyun verisini durdurur; runtime en geç tazelik limiti dolunca sessiz kalır. Python penceresinde Ctrl+C, sesi ve worker'ı kapatır. Oyun çıkışı da logdan algılanır.

Örnek özelleştirme (PowerShell):

```powershell
& 'D:\NebakovVoice\server\.venv\Scripts\python.exe' -u 'D:\NebakovVoice\server\nebakov_voice_runtime.py' --proximity 6 --exit-distance 10 --cooldown 60 --volume 0.7
```

Yalnız elle tetikleme için `--manual`; API çağırmadan mevcut kayıt için `--manifest latest`; tek konuşma sonunda kapanmak için `--once` ekle. Geçmiş oyun logunu yeniden oynatan bir runtime seçeneği yoktur. Aynı engine klasörü için ikinci runtime işletim sistemi kilidiyle reddedilir.

## Ses yöntemi ve native test

Etkin backend, test ettiğin KCD2.AI.NPC sürümündeki yöntemle uyumlu olan Python/pygame konumsal oynatmadır. Her satırda konuşmacının taze entity konumu seçilir; kamera yönüyle stereo pan ve üç boyutlu mesafeyle ses seviyesi hesaplanır. WAV'ların başlangıç/bitiş sessizliği korunur; dosyalar silinmez. Bu backend oyun ses slider'ına veya oyunun duvar arkasında ses engellemesine bağlanmaz; ses seviyesi `--volume` ile ayarlanır. Dudak/yüz animasyonu bu aşamaya dahil değildir.

Kurulu Sound Framework için ayrıca tek WAV'lık `SoundFramework/nebakov_voice_probe.ini` paketi hazırlandı. Runtime'ı kapatıp oyunu yeniden başlattıktan ve guard'ları bağladıktan sonra:

```text
nebakov_voice_native_test
```

Bu komut Marek'in o anki konumunda **tek native ses testi** gönderir. Başarı, sesi dinleyerek ve `Mods/soundframework/KCSE/Plugins/KCD2_SoundFramework.log` içindeki ses kaydı/oynatma çıktısıyla doğrulanmalıdır. Henüz native başarı veya hareket eden NPC'ye bağlı takip iddiası yoktur. Native test otomatik konuşmaların backend'ini değiştirmez. Diğer mod seslerini kesebilen global stop/reload komutları rutin akışta kullanılmaz.

## Loglar ve hata teşhisi

- `D:\NebakovVoice\output\bridge\bridge_events.jsonl`: session/seq/alım zamanı; iş başlangıcı, her satırın başlangıç/bitişi ve iptal/hata nedenleri. Kamera yönü kaynağı `camera` veya `entity` olarak kaydedilir.
- `D:\NebakovVoice\output\bridge\latest_positions.json`: son telemetry durumu; runtime kapanınca `runtime_stopped`.
- `D:\NebakovVoice\output\conversations\nebakov_...`: atomik yayımlanmış `conversation.json` ve dört WAV.

Hiç ses yoksa önce `test_existing_npc_voices.cmd` ile dene. `state=waiting` veya `telemetry_stale` varsa bind komutunu, iki guard'ın bulunmasını ve oyun açıkken log akışını kontrol et. `request_ignored` cooldown sebebini gösterir. `engine_ready` gelmiyorsa Python penceresindeki ilk hata incelenmeli. Worker 90 saniye içinde tamamlanmazsa runtime hata verip sesi/worker'ı kapatır; başlatıcı yeniden açılabilir. API/TTS iş hatasında cooldown yerine kısa 10 saniyelik hata beklemesi uygulanır; yeniden yaklaşma veya elle tetikleme kullanılabilir.

Model/mixer ön kontrolü (ses çalmaz, Gemini çağırmaz):

```powershell
& 'D:\NebakovVoice\server\.venv\Scripts\python.exe' -B 'D:\NebakovVoice\server\nebakov_voice_runtime.py' --check
```

## Yapılan kontroller

- 17 runtime/manifest/konumsal ses/worker-adapter testi, 11 bridge testi ve önceki 29 yemek/devriye testi geçti.
- Kurulu pygame 2.6.1 ile gerçek ses aygıtı başlatıldı; gerçek Kokoro worker `engine_ready` durumuna ulaştı.
- Bir gerçek Gemini isteğiyle adapter dört geçerli WAV ve manifest üretti. Bu testte oyun tetiklemesi veya ses oynatma yoktu.
- Kurulu runtime, gerçek dört WAV ve pygame'in sessiz SDL aygıtıyla sentetik oyun logunda sınandı: dört satırın gerçek kanal bitişi, sıra ve dosyaların korunması doğrulandı. Bu işitsel oyun testi değildir.
- Güncel mod paketi 79 kaynak dosyası için CRC/içerik denetimiyle üretildi. Python bridge dosyaları kurulumdan sonra hash ile kaynaklarıyla karşılaştırıldı; mevcut `conversation_engine.py`, `config.py`, `generate_dialogue.py`, `offline-tts.py` korunuyor.
