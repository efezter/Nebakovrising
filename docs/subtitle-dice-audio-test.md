# Altyazı, yemek sonrası zar ve ses tanılama denemesi

## Başlatma

Güncel mod paketi ve Python köprüsü birlikte kullanılmalı. Oyunu yeniden başlatıp save'i yükle; `D:\NebakovVoice\server\start_patrol_conversations.cmd` köprüsünü de yeniden başlat. Mevcut TTS router çalışıyorsa yeniden başlatmak gerekmez. TTS/model üretim algoritması değiştirilmedi.

## NPC üstünde yazı

`nebakov_subtitle_test` yakındaki bir muhafızın başı üzerinde 8 saniye test metni gösterir; konuşma üretmez. Normal sohbetlerde satırın gerçek metni mevcut `line_start` mesajıyla taşınır. Ek bir mesaj/onay turu yoktur. Lua 5.1 için UTF-8 metni güvenli byte kaçışlarıyla veri olarak aktarılır.

`NebakovSubtitle` adlı küçük script entity'si yalnız aktif yazı sırasında frame güncellemesini açar ve `System.DrawLabel` çağırır. Uzaklaşınca yazı gizlenir; satır sonu, süre dolması, konuşma iptali, save-load veya NPC kaybında temizlenir. Uzun metin yaklaşık iki satırlık sayfalara bölünür. Sayfalar ses süresine eşit dağıtılır; kelime düzeyinde zamanlama üretilmez. Henüz vanilla balonunun birebir görünümü veya duvar arkasında gizlenme iddiası yoktur.

Konsoldaki tek `World label render callback active` mesajı, frame callback'inin gerçekten çalıştığını belirtir; görünüm/okunabilirlik oyun içinde kontrol edilmeli.

## Vardiya sonrası ilk iki muhafızla zar

Yemek davranışı gerçek ayağa kalkma adımını tamamlayıp yemek koltuğunu bıraktıktan sonra aday olur. Adayın mesai sonrası yemek bayrağı tamamlanmış olmalı ve kendi vardiyasının yemek–uyku aralığında bulunmalı. Kahvaltı sonrası göreve başlayacak guard seçilmez. Uyku, combat, oyuncu diyaloğu ve mevcut sohbet rezervasyonu da seçimi engeller.

İlk uygun guard ikinciyi en fazla 90 saniye bekler. İkinci geldiğinde tek çift kurulur. Masa, yakın `SmartObjectHolder` nesnelerinin native zar tür GUID'si ve gerçek seat/cup linkleriyle bulunur; runtime entity ID hardcode edilmez. Challenger native `use_challenger` davranışına girer; ikinci guard birincinin doğru masadaki native `dice_table` linkini bekleyip `use_opponent` davranışını ister. Engine `ReserveBehavior`/`CallBehavior` koltukları ve animasyonları yönetir.

İki guard da native masaya bağlandıktan sonra test 120 saniye sürer. Yaklaşma, partner bekleme ve oyun süresi sınırlıdır. Uyku vaktinde veya bir katılımcı kaybolduğunda iki rezervasyon da bırakılır; native davranış iptal edilip ayağa kalkma ve mevcut bekleme rutinine dönülür. Masanın kendisi veya gereken linkler yoksa normal rutin devam eder. Native masanın kendi para/tepki davranışları bu prototipte yeniden yazılmaz.

Bu denemede **save/oyun oturumu başına ilk çift** kullanılır. `nebakov_dice_status` masa eşleşmesi ve aşama bilgisini gösterir. `nebakov_dice_reset` sonraki yemek bitiren uygun muhafızlar için denemeyi yeniden kurar; hâlihazırda bekleyen iki guard'ı rastgele seçmez.

Config: `Config/routines.lua` içindeki `dice` ve `subtitles` tabloları. Gece ekibi için mesai sonrası pencere 08:00–11:00, gündüz ekibi için 20:00–00:00'dır. Ayarlar save yüklenince yeniden okunur.

## Sabit ses tanılaması

Python, yalnız gerçek satır oynarken en fazla saniyede iki örneği `D:\NebakovVoice\output\bridge\audio_spatial.jsonl` dosyasına yazar. Dosya 256 KiB'de döner; bir yedekle toplam yaklaşık 512 KiB tutulur. Konsola ve normal olay günlüğüne bu örnekler yazılmaz.

Örneklerde session/seq, satır, konuşmacı/entity, WAV yolu, güncel NPC/Henry konumu, mesafe, hesaplanan sol/sağ gain, mixer ayarı, kanalın dolu olması ve beklenen Sound'u oynatıp oynatmadığı bulunur. `channel_scalar_volume`, stereo gain'in ölçümü değildir; stereo değerleri `left/right` alanlarıdır. Başlangıç gain'i `Channel.play` sonrasında da uygulanır; pygame'in belgelenmiş reset davranışı için korumadır. Bu değişiklik sabit ses sorununun bütünüyle çözüldüğü iddiası değildir.

Oyun içi testte aynı satır sürerken 2, 8, 16 ve 24 metreye uzaklaş. Sesi hâlâ sabit duyuyorsan bu dosya, gerçekten değişen mesafe/gain ile kanal sahipliğini karşılaştırmak için yeterli ayrıntıyı sağlayacaktır. 24 metre ve üstünde hesaplanan gain sıfır olmalı.

## Doğrulama sınırı

255 otomatik test geçti. Yeni testler gerçek Lua seçimini, vardiya şartlarını, partner/süre/combat/despawn iptallerini, Unicode/veri güvenliğini, altyazı yaşam döngüsünü ve ses seviyesinin aynı satır sırasında yenilenmesini kapsar. Native zar masası, motor frame callback'i ve animasyon/yol bulma testlerde taklit edilir. Gerçek Python/pygame süreciyle dört satırlık yaklaşmalı ve yerinde konuşma akışları dummy audio üzerinde ayrıca geçti. Yeni görsel yazı ve vanilla zar bağlanması için gerçek oyun testi hâlâ gereklidir.
