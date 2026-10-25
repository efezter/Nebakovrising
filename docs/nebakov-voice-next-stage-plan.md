# NebakovVoice devam planı — 25 Ekim 2026

Uygulama notu: konum/kamera aktarımı, pygame oynatma, tek aktif konuşma ve mevcut Gemini/Kokoro adapter'ı kuruldu. Çalıştırma ve gerçek test durumu için [runtime rehberi](nebakov-voice-runtime.md). Aşağıdaki metin tasarım planının kaydıdır; native speech/lip-sync devam aşaması olarak duruyor.

## Sonuç ve kapsam

Mevcut entity referansları ve Lua → kcd.log → Python köprüsü korunarak ilerlenebilir. İlk hedef, önceden üretilmiş gerçek WAV'ları Marek/Hertl sırasıyla oyun açıkken dinlemek; ardından mevcut Gemini/Kokoro motorunu otomatik yakınlık tetikleyicisine bağlamaktır. Spawn, yemek/devriye davranışları ve çalışan üretim/TTS algoritması bu iş için yeniden tasarlanmaz.

Bu belge analiz ve implementasyon planıdır. Bu incelemede runtime kodu değiştirilmedi, referans mod çalıştırılmadı, paket/bağımlılık kurulmadı ve API çağrısıyla konuşma üretilmedi.

## İncelenen kaynakların kimliği

Kullanıcı, kendi oyununda çalışan sürümün `C:\Users\musta\Desktop\KCD2 Mod Sources\KCD2.AI.NPC-main.zip` olduğunu doğruladı. ZIP okunarak incelendi; arşiv SHA256:

`ed87e162b07d6841cb36eb7ecfbcc955a7af40bdbb81ddb73839597e1476b760`

GitHub [KRYSYS1/KCD2.AI.NPC](https://github.com/KRYSYS1/KCD2.AI.NPC) için incelenen commit: `bdacbd3f991cdca7bd8f7ce138414d85c8ccf8da`, 18 Ekim 2026. Yerel ZIP'in `server/main.py`, `server/tts_client.py`, `server/ambient.py`, iki Lua kaynağı ve `mod/ai_npc/Data/ai_npc.pak` dosyaları bu commit'ten indirilenlerle byte düzeyinde aynı.

Dağıtılan paketteki Lua, satır sonları normalize edilince `build/Data/Scripts/ai_npc/main.lua` ile aynı. `mod/ai_npc/main.lua` daha farklı içerik taşıyor. Entegrasyonda bu iki dosyadaki özellikler aynı sürümde varmış gibi birleştirilmemeli.

## Mevcut testin gösterdikleri

| Durum | Kanıt / sınır |
|---|---|
| Mevcut iki guard'ın kaydı doğrulandı | Marek = MeleeGuard_1, Hertl = MeleeGuard_2; entity adları değiştirilmedi. |
| Oyun → Python aktarımı doğrulandı | Arşiv oyun logunun son paketi ile Python snapshot'ı tam eşleşiyor; session `1.16577e+08-5`, seq 17. |
| Lua örneklemesi yaklaşık 1 Hz | 16 konum paketi ve bir test olayı; konumlar arası oyun zamanı ortalaması 1.004 s. Bu uçtan uca gecikme ölçümü değildir. |
| Henry hareketi/yön değişimi görüldü | NPC'ler bu testte sabit; hareket eden konuşmacı testi ayrıca gerekli. |
| Test trigger logda var | Seq 11. Alıcı olayları kalıcı arşivlemediği için Python işlemesi ayrıca kanıtlanamıyor. |
| Son `stale` oyun çıkışıyla uyumlu | Son paketten sonra normal ExitGame; crash kanıtı yok. |
| Native trigger API mevcut | Paket `native_audio_trigger=true`, eski `Sound.LoadSound` yok. Bu ölçüm ROM/Sound Framework yeteneklerini kapsamıyor. |
| Otomatik üretim/oynatma henüz bağlı değil | `generation_enabled=false`; receiver sadece telemetry alıyor. |

Kaynak log: oyun kökündeki `logbackups/kcd Build(0) 25 Oct 26 (01 51 10).log`, satır 861–884. Python snapshot: `D:\NebakovVoice\output\bridge\latest_positions.json`. `user.cfg` içindeki geçersiz bind satırları bridge hatası değil.

## Çalışan referans moddan alınacak parçalar

[tts_client.py](https://github.com/KRYSYS1/KCD2.AI.NPC/blob/bdacbd3f991cdca7bd8f7ce138414d85c8ccf8da/server/tts_client.py) içindeki `_play_file` (202), `_compute_spatial_volume` (94) ve position-provider deseni doğrudan ihtiyacımıza karşılık geliyor. Gerçek oynatma pygame kanalında; kamera yönüyle pan ve mesafeyle ses seviyesi hesaplanıyor, oynatma sırasında güncelleniyor. `server/main.py` (677) POS paketlerini alıyor. Bizde isim bazlı iki konuşmacının taze konumu kullanılmalı.

Native dispatch callback'i tanımlı ancak incelenen arşivde bu setter'ı çağıran kod yok. Bu nedenle standart dispatch, pygame fallback'ine ulaşır. Lua'daki `rom.audio.play_file_3d` ayrıca API varlığını kontrol eden bir test komutudur (loose main.lua 4284; build kaynağı 3813). Bu kodun bulunması bizim kurulumda native WAV oynatmanın çalıştığı kanıtı değildir. Referansın kullanıcı tarafından çalıştırılmış olması güçlü bir dayanak; hangi backend'in kullanıldığına dair yorum kaynak akışından yapılan çıkarımdır.

Uyarlarken şu farklar gerekli:

- Referans `_play_file` sonunda geçici dosyayı siler; bizim `output/conversations` arşivindeki WAV'lar korunacak.
- Her satıra ayrı, bağımsız playback thread açılmayacak. Tek konuşma sıralayıcısı gerçek kanal bitişini bekleyecek. Referans ambient akışındaki metin uzunluğundan süre tahmini kullanılmayacak.
- Telemetry kaybolduğunda ilk konumla oynatmaya devam edilmeyecek; konuşma durdurulacak. Pan geçmişi konuşmacı değişiminde sıfırlanacak.
- Referansın LLM/TTS sağlayıcıları taşınmayacak; mevcut Gemini 3.5 Flash Lite/Kokoro fonksiyonları kullanılacak.
- Kod kopyalanırsa MIT telif ve izin metni üçüncü taraf bildirimine eklenecek: [LICENSE](https://github.com/KRYSYS1/KCD2.AI.NPC/blob/bdacbd3f991cdca7bd8f7ce138414d85c8ccf8da/LICENSE).

## Kurulumdaki ek native seçenek

`Mods/soundframework` içinde Sound Framework 1.2.0 KCSE eklentisi zaten kurulu. `KCSE/Plugins/KCD2_SoundFramework.log` 25 Ekim 01:57 oturumunda FMOD bağlantısının hazır olduğunu ve `sfw_play`/`sfw_say` komutlarının kaydını gösteriyor. Henüz Nebakov WAV oynatma kanıtı yok; kayıtlı özel ses sayısı sıfır.

[Sound Framework modding rehberine](https://github.com/tkhquang/KCD2Tools/blob/main/SoundFramework/docs/MODDING.md) göre loose WAV'lar bir sound pack ve `sfw_play` ile dünya konumunda oynatılabiliyor. NPC speech/lip-sync yolu `sfw_say` ve localization paketi kullanıyor; paketteki kayıtlar başlangıçta okunuyor. Bundan dolayı yeni üretilen WAV'ın anında native konumsal oynatılması ile dudak senkronlu NPC speech ayrı kabul testleridir. Rehber birinci yol için runtime pack reload sunuyor; ikinci yolun dinamik üretime uygunluğu ayrıca doğrulanmalı.

## Uygulama sırası ve kabul ölçütleri

### 1. Canlı telemetry ve ses backend'i için kısa doğrulama

`tools/nebakov_voice_receiver.py` alım döngüsüne dosya günlüğü ve callback arayüzü ekle. Snapshot korunurken olaylar `bridge_events.jsonl` dosyasına session, seq, event ve alım zamanı ile yazılsın. Nesil üretme yetkisi olmayan tanı modu ve geçmiş replay modu ayrı kalsın. Replay hiçbir koşulda üretim/oynatma tetiklemesin.

Lua listener yönü öncelikle `System.GetViewCameraDir()` ile alınsın; başarısızsa mevcut `GetDirectionVector(1)` fallback'i kullanılsın. Kaynak türü pakette bildirilsin. Referans ve yerel API dökümü kamera fonksiyonunu içeriyor; canlı serbest bakış testiyle doğrulanacak. Yerel vücut yönü kamera serbestçe dönerken yanlış pan verebilir.

Mevcut bir manifest ile iki sınırlı ses testi yap:

1. Referanstaki pygame deseniyle aynı WAV'ın oynatılması. Mevcut NebakovVoice venv'de numpy/sherpa_onnx var, pygame yok; yalnızca gereken pygame bağımlılığı eklenecek. Son incelenen WAV'lar mono, 24 kHz, 16-bit PCM. Mixer sample rate ve stereo dönüşümü bunlara göre doğrulanacak; TTS çıktısı değişmeyecek.
2. Kurulu Sound Framework ile tek loose WAV pack'i oluşturup `sfw_play` üzerinden gerçek NPC konumunda native oynatma denemesi. Reload tamamlanmadan play gönderilmeyecek; framework logundan kayıt doğrulanacak. Hareket eden NPC'yi takip etme ve durdurma yeteneği ayrıca test edilecek. Sabit dünya konumunda başarılı olmak entity'ye bağlı takip başarısı sayılmayacak.

Native seçenek runtime WAV, doğru yön/mesafe, durdurma ve hareket eden konuşmacı koşullarını sağlarsa tercih edilsin; sağlamazsa referansta çalışan pygame yöntemiyle devam edilsin. Backend aynı `play/stop/is_busy` sözleşmesini sunsun. İki backend aynı satırı birlikte oynatmasın.

Kabul: oyun kapanmadan paketler düzenli ulaşmalı; alım geçmişiyle toplu log flush olmadığı gösterilmeli. Kamera sola/sağa çevrildiğinde ses yön değiştirmeli, uzaklaşınca kısılmalı. Telemetry kesilince ses durmalı. Gemini/TTS çağrısı olmadan test tamamlanmalı.

### 2. Mevcut conversation.json için sıralı oynatma

Yeni `nebakov_voice_playback.py`, manifest'in dört satırını `index` sırasıyla oynatsın. Her satırdaki `speaker`, o anda kayıtlı entity adına bağlansın. Dosyalar manifest klasörünün içinde, okunabilir ve geçerli WAV olmalı; bilinmeyen konuşmacı veya eksik dosyada anlaşılır hata ve temiz duruş uygulanmalı. Önce bütün manifest doğrulansın, sonra ilk satır başlasın.

Her satır başlangıcında taze NPC konumu alınsın; pygame sırasında yaklaşık 100 ms'de bir son telemetry ile seviyeler güncellensin. Lua örnekleme aralığı canlı gecikme ölçümüne göre 250 ms'ye indirilebilir. 100 ms playback döngüsü, 1 Hz telemetry'yi 10 Hz ölçüme dönüştürmez. Satır sırası gerçek `is_busy`/kanal bitişiyle ilerlesin; ilk sessizlik korunsun.

Kabul: Marek → Hertl → Marek → Hertl, dört WAV birer kez; üst üste binme yok. Konuşma sırasında hareket/kamera dönüşü, despawn, ölüm, yeni kayıt yükleme ve log kesilmesi denenmeli. Çıkışta kullanılan kanal durmalı, WAV dosyaları kalmalı.

### 3. Tek aktif konuşma ve yakınlık yöneticisi

Yeni `nebakov_voice_runtime.py` telemetry callback'lerini okuyup `waiting → idle → generating → ready → playing → cooldown` durumlarını yönetsin. Proximity kararının tek sahibi Python olsun; Lua sadece veri ve açıkça ayrılmış gerçek trigger olayları göndersin. Mevcut `nebakov_voice_trigger_test` tanı komutu olarak kalsın.

Önerilen başlangıç ayarları: Henry her iki NPC'ye en fazla 8 m, NPC'ler birbirine en fazla 6 m, çıkış eşiği 12 m, cooldown 120 s, tazelik limiti 2 s; hepsi yapılandırılabilir. Cooldown başarılı bitişte başlasın. İlk geçerli yakınlıkta bir kez tetiklensin; tekrar için uzaklaşıp dönme ve cooldown koşulları aransın. Hata için kısa backoff olsun; bekleyen konuşma kuyruğu oluşmasın.

Zamanlamada Python monotonic saat kullanılsın. Session/entity eşleşmesi değişince üretim sonucu iptal edilsin. Her iş session + konuşma kimliği taşısın; eski işin geç tamamlanması ses başlatamasın. Aynı anda ikinci runtime süreci çalışması da tek-instance kilidiyle önlensin.

Kabul: eşikte dururken spam yok; iki tetikleyici çakışınca bir iş var; cooldown ve yeniden giriş doğru; stale/replay/eski-session paketi konuşma başlatamıyor.

### 4. Mevcut Gemini/Kokoro motoruna adapter

Ayrı kalıcı Python worker, mevcut `conversation_engine.generate_conversation`, `create_tts`, `generate_audio` fonksiyonlarını kullansın. `create_tts()` normal worker yaşamında bir kez çağrılsın. Dört satır tek Gemini isteğiyle üretilsin; mevcut manifest ve WAV biçimi korunsun. Çıktı klasörü konuşma kimliğiyle benzersiz olsun; manifest bütün WAV'lar hazır olduğunda atomik yayınlansın.

Supervisor log okumayı ve ses kontrolünü sürdürsün; model yükleme, API ve sentez bu döngüyü bloklamasın. Hazır olmadan tetikleme kabul edilmesin. Mevcut API timeout'u doğrulanıp iş deadline'ı eklensin. İptal edilmiş bir worker işi fiziksel olarak sürüyorsa ikinci iş açılmasın; takılma halinde kontrollü worker restart uygulanabilsin. TTS yalnızca böyle bir restart'ta yeniden yüklenir.

Kabul: Henry yaklaşınca bir konuşma klasörü, tek API isteği, dört WAV; model tekrar yüklenmiyor. Üretim sürerken telemetry güncelleniyor. Henry uzaklaşır veya NPC kaybolursa sonuç sonradan çalmıyor. API/TTS hatasından sonra sistem kontrollü biçimde tekrar kullanılabiliyor.

### 5. Native speech / görsel konuşma isteğe bağlı devam aşaması

Ses testinden sonra altyazı ve konuşan NPC'nin yüzü ele alınabilir. Sound Framework'ün localization/speech yolu bilinen bir örnekle sınanmalı; sonradan üretilen kayıtları oyun yeniden başlamadan oynatabildiği gösterilmeden dinamik lip-sync sözü verilmemeli. Referans server'da FACETALK komutu var fakat incelenen iki Lua kaynağında/pakette aynı marker için handler görülmedi; bu parça doğrulanmadan taşınmamalı.

Python → Lua gerekiyorsa referanstaki `Script.LoadScript(path, true)` yöntemi izole Nebakov namespace'iyle denenmeli. Önce sabit, zararsız ping komutu ve Lua → log acknowledgment ile dosya yolu/yeniden yükleme doğrulansın. Ardından atomik yazılan, whitelist eylemli, session ve artan command ID içeren tek komut alanı; acknowledgment gelene kadar üzerine yazmama uygulanmalı. Model çıktısı Lua kodu olarak çalıştırılmamalı. Global `sfw_stop_all`/`sfw_reload` rutin iptal için kullanılmamalı; diğer modların seslerini etkiler.

## Değişecek dosyalar ve doğrulama

Lua: mevcut `src/Scripts/mods/nebakov_voice_bridge.lua` kamera/capability ve gerekirse kontrollü inbound komut desteği; `nebakovrising.lua` yalnızca bridge ayarları. Python: mevcut receiver'ın ayrıştırılmış callback'i; yeni runtime, playback ve engine adapter modülleri; ayrı runtime launcher. Mod deposundaki Python kaynakları esas alınarak `D:\NebakovVoice\server` kopyaları hash ile doğrulansın.

Otomasyon testleri state geçişleri, iki eşzamanlı tetikleyici, stale/session iptali, manifest sırası, dosya koruma ve konuşmacı seçimini kapsasın. Kamera panı, log flush gecikmesi, native komut teslimi ve gerçek işitsel yön mutlaka oyun içinde sınansın. Mevcut 11 bridge ve 29 yemek/devriye testi, runtime kodu değiştiğinde regresyon kontrolü olarak çalıştırılsın. Her aşama kendi oyun içi kabulünden sonra tamamlandı sayılsın.
