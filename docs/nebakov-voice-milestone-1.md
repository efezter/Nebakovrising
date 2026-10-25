# NebakovVoice — ilk entegrasyon aşaması

25 Ekim 2026. Durum: iki mevcut guard'ın kaydı ve gerçek oyun → Python konum aktarımı log/snapshot eşleşmesiyle doğrulandı. Canlı aktarım gecikmesi, otomatik konuşma üretimi ve ses oynatma henüz doğrulanmadı.

Devam sürümündeki konuşma runtime'ı artık kuruldu; güncel başlatma ve test durumu için [runtime rehberi](nebakov-voice-runtime.md). Bu dosyadaki pozisyon alıcısı bağımsız tanı modu olarak ses/üretim kapalı kalır.

## Gerçek oyun testinden kanıt

`logbackups/kcd Build(0) 25 Oct 26 (01 51 10).log` içinde Marek → `nebakovrising_MeleeGuard_1`, Hertl → `nebakovrising_MeleeGuard_2` eşleşmeleri bulunuyor. `1.16577e+08-5` session'ında seq 1–17 kesintisiz; seq 11 `conversation_trigger`, diğerleri konum paketi. Konum örneklerinin oyun zamanı aralığı ortalama 1.004 saniye. Henry'nin konumu ve forward vektörü değişiyor; bu kayıtta iki guard sabit duruyor.

`D:\NebakovVoice\output\bridge\latest_positions.json` içindeki son paket, oyun logundaki seq 17 ile bütün alanlarında eşleşiyor. Python alım zamanı `2026-10-24T22:53:41.719475+00:00` (25 Ekim 01:53:41, Atina). Son paketin ardından logda `C_UISaveLoad::ExitGame()` ile normal çıkış var; sonraki `stale` durumu bununla uyumlu. Snapshot'ta `generation_enabled=false` olması bu aşamanın beklenen davranışı.

Bu kanıt, paketlerin Python'a ulaştığını gösterir. Her paketin alım zamanı kalıcı tutulmadığı için oyun açıkken log flush gecikmesini veya seq 11 olayının Python'da işlenmesini tek başına kanıtlamaz. Sonraki aşamada alım günlüğü ve canlı gecikme testi eklenmeli. Ayrıntılı devam planı: [nebakov-voice-next-stage-plan.md](nebakov-voice-next-stage-plan.md).

## Bu aşamada yapılanlar

- Mevcut iki mod guard'ı, mevcut entity referansları kullanılarak Marek/Hertl konuşmacı etiketlerine bağlanır. Entity adı, rolü ve spawn mekanizması değişmez; yeni NPC oluşturulmaz. Kullanıcı ilk test için mevcut iki guard'ın etiketlenmesini seçti.
- Lua, Henry ile iki NPC'nin dünya konumlarını yapılandırılabilir aralıkta `System.LogAlways` ile oyun loguna gönderir. NPC kaybolursa, ölürse veya entity ID'si başka entity için kullanılırsa kayıt `available=false` olur. Eski konum tekrar kullanılmaz.
- Ayrı Python işlemi yalnızca işaretli JSON satırlarını takip eder ve `D:\NebakovVoice\output\bridge\latest_positions.json` dosyasını günceller. Eski session/sequence, kısmi satır, log truncation/rotation ve eksik telemetry durumları ele alınır.
- Manuel test komutu, aynı konumlarla `conversation_trigger` olayını gönderir. Bu milestone Gemini, TTS veya ses oynatmayı çalıştırmaz.

## İletişim seçiminin dayanağı

`System.LogAlways`, `Script.SetTimerForFunction`, `System.GetEntity` ve `GetWorldPos` mevcut modun kullandığı API'lerdir. Mevcut `kcd.log` içinde modun `LogAlways` çıktısı da gözlemlendi. Lua dosya yazma, socket veya HTTP erişimi varsayılmadı; mod bunları kullanmaz. Python dosya okumasını ayrı işlemde yapar. Konuşma motorunun API anahtarı Lua'ya veya log paketine taşınmaz.

İlk milestone Lua örnekleme aralığı 1000 ms idi; konuşma runtime'ı için mevcut varsayılan 250 ms'ye indirildi (`nebakovrising.Config.voiceBridge.sampleIntervalMs`, izin verilen aralık 250–10000 ms). Bu, uçtan uca gecikme garantisi değildir: oyunun log yazma/flush gecikmesi canlı testte ölçülmelidir. Bağımsız pozisyon alıcısı beş saniye yeni paket almazsa snapshot'ı `stale` işaretler; aralık büyütülürse `--stale-after` da artırılmalıdır.

Bu kanal tek yönlüdür. İlk milestone yalnızca Lua → Python aktarımı gerektirir. Python → Lua acknowledgment veya native ses komutu teslimi bu aşamada uygulanmış sayılmıyor.

## Oyun içi test

1. Güncellenmiş mod paketini yüklemek için oyunu yeniden aç. Mevcut guard'ların bulunduğu kaydı yükle.
2. `D:\NebakovVoice\server\start_bridge_positions.cmd` dosyasını çalıştır. Pencerede `Ready. In KCD2 run: nebakov_voice_bind_pair` mesajını bekle. Alıcıyı **bind komutundan önce** aç; varsayılan olarak eski log satırlarını tekrar oynatmaz.
3. Oyun konsolunda şu komutu çalıştır:

   ```text
   nebakov_voice_bind_pair
   ```

   Mevcut spawn listesindeki ilk iki yaşayan guard seçilir. Liste save/load sonrasında boşsa, yüklenmiş mevcut mod guard'ları ad sırasıyla bulunur. İki uygun guard yoksa işlem başarısız olur; otomatik spawn yapılmaz. Logda `Marek -> gerçek_entity_adı` ve `Hertl -> gerçek_entity_adı` eşleşmeleri görünür.

4. Python penceresinde şu biçimde canlı koordinatlar görünmeli:

   ```text
   [positions_ok] seq=1 Marek=(...) | Hertl=(...) | Henry=(...)
   ```

   Henry ile birkaç adım yürü; Henry koordinatlarının değiştiğini doğrula. Guard hareket ederse ilgili konuşmacının koordinatları da değişmeli. `latest_positions.json` içinde `status=positions_ok`, iki farklı `entity_name`, `player.position` ve iki NPC için `position` bulunmalı.

5. Konumlarla birlikte olay aktarımını test et:

   ```text
   nebakov_voice_trigger_test
   ```

   Python `TEST TRIGGER RECEIVED; no conversation generated (milestone 1).` yazmalı. `conversation_engine.py` çağrılmaz; API isteği ve yeni WAV üretimi olmaz.

6. Aktarımı durdurmak için:

   ```text
   nebakov_voice_stop
   ```

   Snapshot `stopped` olur. Receiver penceresini Ctrl+C ile kapatabilirsin. Başka kayıt yüklendiğinde eski referanslar temizlenir; `nebakov_voice_bind_pair` komutunu yeniden çalıştır.

Pencere açıcı yerine PowerShell'den de başlatılabilir:

```powershell
& 'D:\NebakovVoice\server\.venv\Scripts\python.exe' -u 'D:\NebakovVoice\server\nebakov_voice_receiver.py'
```

Farklı log konumu için `--game-log 'tam\yol\kcd.log'`, farklı snapshot dizini için `--output-dir 'tam\yol'` ekle. `--once --timeout 60`, tam konum paketi gelince çıkar; gelmezse hata kodu 2 döndürür. `--from-start` yalnızca tarihî log incelemesi içindir; canlı aktarım kanıtı sayılmaz.

## Mevcut referanslarla yeniden kullanım

Spawn mekanizmasını değiştirmeden, mevcut Lua çağıran kodundan:

```lua
local bridge = nebakovrising.VoiceBridge
bridge.Register("Marek", marekEntity)
bridge.Register("Hertl", hertlEntity)
bridge.Start()
```

`marekEntity` ve `hertlEntity` mevcut runtime referanslarıdır; bu örnekte yeni entity oluşturulmaz. `bridge.GetPosition("Marek")`, geçerli konum veya `nil, neden` döndürür. Konsol komutundaki ilk iki guard seçimi yalnızca ilk test kolaylığıdır.

## Sonraki aşama için doğrulanan arayüzler

`D:\NebakovVoice\server\conversation_engine.py` değiştirilmedi. Mevcut fonksiyonlar `generate_conversation`, `create_tts`, `generate_audio`; manifest `lines[]` kayıtları `index`, `speaker`, `audio_file` alanlarını içerir. Doğrulamadan sonra ayrı Python worker, `create_tts()` sonucunu bir kez tutarak mevcut fonksiyonları kullanabilir. Proximity, cooldown, tek aktif konuşma ve sıralı playback bu worker'ın bir sonraki aşamasıdır.

Native audio araştırmasında `AudioUtils.PlayAudioTrigger` / `entity:ExecuteAudioTrigger` yolunun entity'ye bağlı trigger oynattığı görüldü. Yerel runtime dökümünün `Sound` tablosunda `GetAudioTriggerID` gibi trigger fonksiyonları var; eski SDK HTML'lerindeki `Sound.LoadSound` / `Sound.PlaySound` aynı dökümde yok. Bu nedenle dışarıdaki rastgele WAV'ın native positional audio ile oynatılabildiği doğrulanmış değil. Paket ayrıca mevcut entity'de `ExecuteAudioTrigger` ve `Sound.LoadSound` fonksiyonlarının gerçekten bulunup bulunmadığını raporlar; fonksiyonun varlığı tek başına WAV oynatma testi değildir.

Native WAV yükleme doğrulanamazsa, sonraki aşamada Python/pygame kanal ses seviyeleri NPC–Henry göreli konumuyla hesaplanabilir. Paket, API mevcutsa Henry'nin forward vektörünü de gönderir; sağ/sol yön yalnızca dünya koordinatlarından hesaplanmamalıdır. Bu milestone ses çalmaz.

Yerel dayanaklar: referans arşivindeki `Scripts/Scripts/Utils/AudioUtils.lua`, `lua_dump_state/LuaState_Sorted.txt` (`Sound` tablosu: 22776), `CScriptBind_Entity__ExecuteAudioTrigger...html`, mevcut mod kaynakları ve oyun logu. Bunlar canlı oyun içi testin yerini tutmaz.

## Yerel test sonuçları

- `python tools/test_voice_bridge.py`: 11 test geçti. Gerçek Lua serializer'ı ile Python decoder/alıcı birlikte sınandı; despawn, ID tekrar kullanımı, eksik Henry, geçersiz konum, JSON escaping, eski timer, dünya yeniden yükleme, log truncation/rotation ve stale veri kapsanır.
- `python tools/test_meal_flow.py`: önceki 29 yemek/devriye testi de geçti; yeni Lua modülü Lua 5.1 sözdizimi kontrolüne dahil edildi.
- `D:\NebakovVoice\server\.venv\Scripts\python.exe` ile kurulu alıcı çalıştırıldı. Mock oyun API'lerinden gerçek Lua modülünün ürettiği JSON, geçici log dosyasına yazılıp bu alıcı tarafından okundu; Henry/Marek/Hertl koordinatları doğru snapshot'a ulaştı. Bu **sentetik uçtan uca testtir**, gerçek oyun içi doğrulama değildir.
- `conversation_engine.py`, `config.py`, `generate_dialogue.py` ve `offline-tts.py` dosyalarının hash'leri kontrol edildi; mevcut içerikleri değişmedi. Gemini isteği, TTS veya audio playback çalıştırılmadı.
