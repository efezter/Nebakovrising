# Muhafız vardiyaları

Saatler `Mods/nebakovrising/Config/routines.lua` içindeki `shifts` tablosundan okunur:

| Vardiya | Uyanma / kahvaltı | Mesai sonu / yemek | Uyku |
|---|---|---|---|
| day | 08:00 | 20:00 | 00:00–08:00 |
| night | 19:00 | 08:00 | 11:00–19:00 |

Yemek sonrası mevcut ayakta bekleme davranışı sürer. Gece ekibi 08:00 yemeğini bitirince 11:00'e kadar bekler. Gündüz ekibi 19:00–20:00 arasında devriyeye devam ederken gece ekibi uyanıp hazırlanır. İlk muhafız hemen, aynı vardiyanın diğer uyuyan muhafızları rastgele 5–15 saniye arayla uyanır; bu aralık mevcut `wakeStagger` ayarıdır. Vardiyalar birbirlerinin uyanma sırasını sıfırlamaz.

Bir muhafızda gece ataması yoktur; iki veya üç muhafızda bir gece muhafızı vardır. Dört ve üzerinde gece sayısı `ceil(toplam * 0.30)` olur. Dağılım melee ve ranged muhafızların toplamından hesaplanır. Diğer roller bu hesaba girmez.

Atama mevcut kalıcı NPC kaydının `guardShift` alanına yazılır. Save/load sonrası korunur. Yeni muhafızlar gereken vardiyaya öncelikli atanır; gerekirse mevcut muhafızlardan yalnız eksik/fazla sayıyı giderecek kadarı değiştirilir. Yükten çıkan muhafızların kayıtları sayılmaya devam eder; doğrulanmış ölü muhafızlar sayılmaz. Mevcut doğum/ölüm, save restore ve iki saniyelik konum kontrolü kullanılır; yeni sürekli zamanlayıcı eklenmez.

Saat kontrolleri NPC'ye göre yapılır. Gece yarısı gece devriyesini durdurmaz. Uyku, yemek, devriye ve konuşma uygunluğu aynı vardiya saatlerini kullanır. Değişen atamalar mevcut native ayağa kalkma ve aktivite çıkış akışlarıyla uygulanır. Uyuyan bir gündüz muhafızı geceye geçirilirse uyku döngüsü yeni saatleri görüp uyanır; sıradan uyanıştaki ekipman ve kahvaltı akışını kullanır.

## Oyun içi test

1. Güncel paketle oyunu yeniden başlatıp save'i yükle. Eski save'lerde atamalar otomatik oluşturulur.
2. Konsolda `nebakovrising_shift_status` çalıştır. Toplam/gündüz/gece sayılarını ve her muhafızın saatlerini gösterir.
3. 19:00, 20:00, 00:00, 08:00 ve 11:00 geçişlerini izle. 00:00'da gece ekibinin çalıştığını, 11:00'de yatağa gittiğini kontrol et.
4. Yeni muhafız ekleyip dağılımı tekrar kontrol et. Save/load veya bölgeden uzaklaşıp dönmek mevcut atamaları değiştirmemeli.

234 otomatik test geçti; bunların 22'si vardiya dağılımını, kayıtların korunmasını, gece yarısı/saat sınırlarını, ayrı uyanma sıralarını, yemek sonrası 11:00 uykusunu ve vardiyaya göre sohbet uygunluğunu kapsar. Kontroller gerçek Lua 5.1 rutinlerini ve yemek davranış ağacını çalıştırır; motorun animasyon ve yol bulması taklit edilir. 22 Lua dosyası ve 124 gömülü Lua bloğu ayrıca derleme kontrolünden geçti. Gerçek oyunda vardiya değişimi ayrıca test edilmelidir. Python/TTS tarafında bu özellik için değişiklik yapılmaz.
