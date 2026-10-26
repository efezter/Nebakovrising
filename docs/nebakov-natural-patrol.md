# Doğal patrol sohbetleri

Servisler geliştirme sırasında elle başlatılır. Windows başlangıç görevi, izleyici veya mod-init dış süreç başlatıcısı eklenmedi.

## Başlatma

1. `D:\NebakovVoice\start_tts_router.ps1` ile mevcut TTS router'ı aç.
2. `D:\NebakovVoice\server\start_patrol_conversations.cmd` ile normal sohbet köprüsünü aç. `engine_ready` ve kabul edilmiş `conversation_config`/`voice_catalog` onaylarını bekle.
3. Güncel mod paketiyle oyunu aç. Henry Nebakov'dayken, saat sınırlaması olmadan otomatik denemeler yapılır. Yalnız doğrulanmış sabit bekleme/yemek davranışındaki uygun guard’lar seçilir.

`prewarmModel=true`, zaten elle başlatılmış servise model hazırlama isteği yollar; servisi kendisi başlatmaz. Model hazır olduğunda yeniden yüklenmez. Pencereler izleme için açık kalır.

## Ayarlar

`D:\NebakovVoice\config\conversations.json`:

Bu, tek düzenlenebilir ayar dosyasıdır. Projedeki JSON kopyaları kaldırıldı. Kurucu yalnız eksik dosyaları Python içindeki ilk kurulum değerlerinden oluşturur; mevcut ayarlara dokunmaz. Mevcut kurulumdaki deneme aralığı 20–50 saniyedir. Köprü başlangıçta okuduğu tam dosya yolunu ve değerleri penceresinde gösterir. Değişiklikleri uygulamak için sohbet köprüsünü yeniden başlat.

| Alan | Varsayılan | Anlam |
|---|---|---|
| `enabled` / `randomEnabled` | `true` / `true` | Sohbet sistemi ve otomatik denemeler |
| `nearbyDistance` | 2 | Yerinden kalkmadan konuşacak çift için azami başlangıç mesafesi; metre |
| `randomMinSeconds` / `randomMaxSeconds` | 120 / 240 | Denemeler arası rastgele süre; saniye |
| `searchRadius` | 20 | Henry çevresindeki uygun guard arama mesafesi |
| `cooldownSeconds` / `npcCooldownSeconds` | 0 / 0 | İsteğe bağlı ek genel/guard beklemesi; şu an kapalı |
| `prepareBeforeMeeting` | `true` | Önce bütün sesleri hazırla, sonra buluştur |
| `generationTimeout` | 240 | Hazırlık zaman aşımı; saniye |
| `profileId` | `patrol-daily-talk` | Kullanılacak prompt dosyasının kimliği |
| `prewarmModel` | `true` | Manuel köprü açılışında mevcut TTS modelini hazırla |

Uygun iki guard yoksa deneme atlanır; Gemini/TTS işi oluşturulmaz. Müsaitlik, gerçek patrol davranışı, combat/diyalog/uyku/yemek öncelikleri ve cooldown'larla belirlenir. Deneme sıklığı her denemenin konuşmaya dönüşeceği anlamına gelmez.

Dosyaları düzenledikten sonra yalnız sohbet köprüsünü yeniden başlatmak yeterlidir; model servisini veya mod paketini yeniden kurmak gerekmez. Kurucu mevcut kişisel JSON ayarlarını/profillerini değiştirmez. Yeni bir profil dosyası oluşturup `profileId` alanını değiştirerek kullanabilirsin.

## Prompt profili ve Lua parametreleri

`D:\NebakovVoice\config\prompts\patrol-daily-talk.json`, prompt şablonunu ve konu listesini tutar. Konular aile/memleket, gündelik sıkıntılar, yemek, ücretler, eski seferler, dostça takılmalar ve geleceğe dair umutları kapsar. Konu torbası aynı konuyu bütün liste dolaşılmadan yeniden seçmez; döngü sınırında da art arda aynı konuyu seçmez.

Lua profil kimliğini ve seçim anındaki verileri gönderir: `location`, `hour`, `time_of_day`, `trigger`, `guard_a`, `guard_b`, `guard_a_role`, `guard_b_role`, `event_kind`, `event_text`. Şablon bunları `$hour`, `$event_text`, `$topic` gibi yer tutucularla kullanır. Lua'dan gelen ek düz metin/sayı alanları da şablon parametresi olabilir. Prompt metni Lua kodu olarak çalıştırılmaz.

Mevcut modda doğrulanmış yeni guard oluşturulması ve actor API'siyle doğrulanmış guard ölümü olay bağlamına eklenir. Diğer Lua olayları şu girişten bilgi sağlayabilir:

```lua
nebakovrising.Conversations.SetEventContext(
    "gate_bell", "A bell has just sounded at the gate.", 120)
```

Bu çağrı yalnız olay gerçekten saptandığında yapılmalı. Son parametre geçerlilik süresidir (0–300 saniye; 0 temizler). Yağmur, saldırı veya katil gibi okunmamış bilgiler üretilip olay diye gönderilmez. Hazırlık sırasında olay bağlamı değişir/eskirse veya guard'lar uygunluğunu kaybederse eski diyalog iptal edilir. Üretilen `conversation.json` içinde `profile_id` ve `prompt_parameters` denetim için saklanır.

## Buluşma ve test

Seçilen guard'lar sesler hazırlanırken devriyelerine devam eder. Dört WAV doğrulanınca ikisi tekrar kontrol edilir; güncel patrol token'larıyla rezervasyon yapılır. Mevcut ayağa kalkma, yaklaşma, varışı doğrulama, native dönüş ve ağız animasyonu akışı korunur. Sesin başlaması için fiziksel varış/dönüş ve oyun onayları gereklidir; sesler eksikken oynatma yapılmaz.

`nebakov_conversation_test`, rastgele süreyi beklemeden deneme yapar; saat/mesafe/uygunluk kurallarını korur. `nebakov_conversation_status` ve `nebakov_voice_assignments` teşhis için kullanılabilir.

`test_patrol_voices.cmd` hazır WAV testidir; bu modda otomatik denemeler kapalı tutulur. Yeni ve duruma göre üretilen sohbetler için normal `start_patrol_conversations.cmd` kullanılmalı.

Python penceresinde `patrol_attempt`, `generation_started`, `state`, `control_ack` ve bitiş/iptal olayları görünür. `patrol_attempt` atlanan denemenin nedenini de içerir. Ayrıntılı olay kaydı: `D:\NebakovVoice\output\bridge\bridge_events.jsonl`. Ham telemetri ve normal heartbeat mesajları olay günlüğüne eklenmez. Günlük 2 MiB sınırında döner; en fazla iki yedeğiyle yaklaşık 6 MiB tutar. Eski büyük günlükler açılışta son kayıtları korunarak küçültülür.

## Doğrulama

196 otomatik test; hazır seslerden önce patrol'ün kesilmemesi, token yenileme, 24 saat uygunluk, uygun çift yokken atlama, config doğrulaması, Lua olay parametreleri, profil değişimi, konu çeşitliliği ve model hazırlığını kapsar. Önceki native dönüş/varış, ses atamaları ve oynatma kontrolleri korunur. Yeni otomatik zamanlama ve önce-hazırla akışının gerçek oyun testi ayrıca yapılmalı.

Yeni profil ve guard örnekleriyle bir gerçek Gemini/TTS isteği de tamamlandı: dört WAV doğrulandı ve profil/parametre metadatası kaydedildi. Bu kontrol oyun içinde tetikleme veya oynatma testi değildir. Oynatma kontrol mesajları boş heartbeat mesajlarından önce kuyruğa alınır; Lua onayları korunur.

## Küçük durum dosyası

Köprü, mevcut Lua komut kanalından oyuna `Data/Scripts/nebakov_voice/telemetry.json` yolunu gönderir. Lua `io.open` kullanılabilirliğini ve gerçek dosya yazımını çalışma anında sınar. Python bu dosyadan güncel bir paket okuyup ayrıca onay verdikten sonra `NEBAKOV_VOICE_V1` konsol paketleri kapatılır. Python penceresinde `telemetry_transport` / `mode: file`, oyunda bir kez `Telemetry channel=file` görünür.

Dosya her örneklemede üzerine yazılır; geçmiş birikmez. Okuyucu 16 KiB üst sınırı uygular, yarım yazımı yeniden okur; eski oturumlar ve tekrar paketleri çalıştırılmaz. Olay/ses kontrol protokolü ve örnekleme sıklığı korunur. Dosya yazımı desteklenmiyorsa veya sonradan başarısız olursa oyun logu kanalı çalışmaya devam eder; hata bir kez bildirilir. Bu durumda konsol paketleri devam eder. Dosya kanalının gerçek oyun ortamında kullanılabilirliği ayrıca doğrulanmalıdır.

Bu güncelleme için oyun ve sohbet köprüsü yeniden başlatılmalı. TTS router'da değişiklik yoktur. Testlerde gerçek Lua 5.1 kodu ve Python/pygame süreciyle dosya onayı, loga dönüş, dört satırın sırası ve ağız animasyonu komutları doğrulandı; oyun API'leri testte taklit edildi.

## Sohbet aralığı ve alıcının duruşu

`randomMinSeconds`/`randomMaxSeconds` süresi, devam eden sohbet bittikten sonra yeniden seçilir. Mevcut kurulumda 20–50 saniye korunur; önceki 120 saniyelik genel ve 180 saniyelik NPC cooldown değerleri 0 yapıldı. Böylece bu iki ek sınır aralığı uzatmaz. Bu süre yeni konuşmanın hazırlanmasına kadar olan beklemedir: uygun çift yoksa deneme atlanır; ses üretimi, yürüme ve varış/dönüş onayı duyulan başlangıca ayrıca eklenir. Arka arkaya konuşmalar aynı anda çalıştırılmaz.

Patrol BT'si, gerçek oturma/yaslanma adımı tamamlandıktan sonra bir duruş işareti tutar. Seçilen çiftte biri bu durumdaysa alıcı olarak tercih edilir. Sesler hazır olduğunda güncel duruş yeniden kontrol edilir. Alıcı, mevcut bench StanceElement'i veya leaningObject link'i açık kalırken konuşur; kendisine Stand, Move veya Turn verilmez. Diğer guard onun baktığı yöndeki yaklaşık 1.3 metre mesafeye yürüyüp alıcıya döner. Alıcının mevcut yönü ve gerçek varış yine doğrulanır; gövde açıları doğrudan değiştirilmez.

Sohbet boyunca alıcının patrol bekleme sayacı durur, nokta rezervasyonu korunur. Sohbet sonunda aynı bekleme davranışına devam eder; sosyal rezervasyon temizlenir ve NPC daha sonra yeniden seçilebilir. Combat, yemek/uyku önceliği, bağlantı kopması, duruşun değişmesi ve despawn mevcut iptal kurallarını korur. Standart iki ayakta guard akışı da korunur. Oturma/yaslanma akışı otomatik testlerde çalıştırıldı; gerçek oyunda animasyon ve erişilebilir yaklaşma noktası ayrıca kontrol edilmeli.

## 24 saat ve yerinde sohbet

Sohbetin ayrı bir saat penceresi yoktur. Eski `patrolStartHour` ve `patrolEndHour` alanları kaldırıldı; eski config bulunursa uyumluluk için yok sayılır. NPC'lerin kendi yemek/uyku programı değişmez. Uyuyan, yürüyen, duruş geçişi yapan, combat veya oyuncu diyaloğunda olan guard seçilmez. Native `GetVelocity()` kullanılabiliyorsa gerçek hareket de kontrol edilir; BT'nin doğruladığı sabit duruş işareti her durumda gereklidir. Başlangıçta belirsiz/işaretsiz NPC seçilmez.

İki guard `nearbyDistance` (varsayılan 2 metre) içindeyse ikisinin mevcut aktivite/koltuk rezervasyonu seçim anında tutulur. Hold, ses üretimi boyunca da etkindir. Aynı benchte veya masada olmak zorunlu değildir; gerçek dünya mesafesi kullanılır. Body Stand/Move/Turn veya karşılıklı gövde açısı şartı yoktur. Her iki BT de mevcut duruşun içinde hold adımına girdiğini onaylamadan ses başlamaz.

Patrol bekleme sayacı ilerlemez; yemek deadline'ının kalan süresi saklanıp sohbet bitiminde geri yüklenir. Sabit bekleme/oturma/yaslanma animasyonları devam eder. Yeni bir hareket adımı bekler. Başarı, üretim hatası, timeout, oyuncunun uzaklaşması, combat, despawn veya Python bağlantı kaybı hold'u kaldırır. Guard'ın mevcut activity token'ı ve koltuğu korunur. Hold sırasında NPC fiziksel olarak yerinden kayarsa/ayrılırsa sohbet iptal edilir.

Daha uzaktaki iki sabit patrol guard'ı mevcut yaklaşma akışını kullanır. Yemek yiyen veya akşam idle durumundaki guard uzaktaysa koltuğundan/aktivitesinden kaldırılıp buluşturulmaz. Ses hazırlanırken patrol guard'ı normal rutininde hareket etmeye başlarsa eski konuşma iptal edilir.

Prompt profilleri: patrol için `patrol-daily-talk`, en az biri yemek yiyorsa `meal-daily-talk`, diğer akşam bekleme çiftleri için `idle-daily-talk`. Gerçek isimler, iki NPC'nin doğrulanmış aktivitesi ve günün saati gönderilir. Hazırlama servisi/TTS algoritması değiştirilmedi. Mevcut `start_patrol_conversations.cmd` aynı başlatıcıdır; yeni config ve profilleri okumak için köprü yeniden başlatılmalıdır.

Gerçek Lua/Python ve dummy audio ile hem yaklaşmalı hem yerinde dört satırlık akış test edildi. İki yemek BT'sinin koltukları koruduğu ve timer'ların devam ettiği de test edildi. Gerçek oyun animasyonları ve seçimlerin oyun içi doğrulaması ayrıca gereklidir.
