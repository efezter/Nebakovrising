# Guard yemek geçişleri: hata analizi ve implementasyon planı

Tarih: 25 Ekim 2026

Kapsam: Oturan guard'ın akşam yemeğine giderken takılması ve yemek aldıktan sonra masa/bench akışında ayakta bekleyen NPC'ler. Düzeltmeler uygulandı. Aşağıdaki hata analizi ve satır referansları düzeltme öncesi sürüme aittir; uygulanan davranış ve doğrulama bilgileri belgenin sonundadır.

Son kullanıcı kararı: Akşam yemeğini bitiren NPC, kuyruk durumundan bağımsız olarak ayağa kalkar, koltuğunu bırakır ve uyku saatine kadar ayakta idle bekler. Yemek sonrası devriyeye dönüş şimdilik yapılmaz.

## İncelenen kanıtlar

- Çalışma ağacındaki `src/AI/nebakovrising_patrol.xml`, `src/AI/nebakovrising_walk_to_bed.xml`, `src/AI/npc/basic/switch/switch.xml`, `src/Scripts/mods/CastleUtils.lua` ve `src/Scripts/mods/roles/Guard.lua`.
- Oyun dizinindeki `kcd.log`. Log bir akşam yemeği akışı ve bu akış sırasında save/load içeriyor. Aşağıdaki satır numaraları incelenen log sürümüne aittir; oyun tekrar çalıştırıldığında değişebilir.
- Referans arşivindeki vanilla `Scripts/AI/world/so_fireplace.xml:1392` ve `Scripts/AI/world/so_sitPlace.xml:44`. Vanilla yemek akışı da atanmış oturma smart object'i üzerinde `StanceElement` kullanıyor. Bench'e ayrıca `Move` yazılmamış olması tek başına hata kanıtı değildir.
- Aktif `Data/nebakovrising.pak` içindeki üç ilgili AI XML'i ve `CastleUtils.lua`, çalışma ağacındaki kaynaklarla byte düzeyinde aynı. İncelenen dosyalar için kaynak/paket farkı bulunmadı.

## 1. Oturan guard'ın yemeğe geçerken takılması

### Kesin bulunan kod boşlukları

Verilen `Bench/bench_1place_low11_e16ab7d7-fe58-452a-bb1a-daecca10f3df` noktası melee patrol listesinde var (`roles/Guard.lua:48`). `getPatrolKind` bench'leri `sit` olarak sınıflandırıyor (`CastleUtils.lua:904`); noktanın yanlışlıkla normal ayakta guard noktası sayılması açıklaması kodla desteklenmiyor.

Normal devriye akışında oturma/lean sonrasında kalkış adımı zaten bulunuyor (`nebakovrising_patrol.xml:206`). Ancak bu adım normal sıralı akışın içinde. `OnFail` yalnızca noktayı bırakıp runtime durumunu `idle` yapıyor (`:240`); kalkışın tamamlandığına dair bir koşul yok.

Akşam yemeği `ShouldStartEveningMeal` ile `meal_pending` yazar (`CastleUtils.lua:1168`). Scheduler daha sonra `nebakovrising_resume_meal_walk` interrupt'ını gönderir (`switch.xml:745`). Bu davranış, hedefi çözdükten sonra doğrudan `Move` başlatır (`nebakovrising_walk_to_bed.xml:293`). Başlangıç stance'ini `standing` yapıp geçişi bekleyen bir adım bulunmuyor. Bu nedenle devriyeden veya save/load'dan oturarak gelen NPC için yürüyüşün önkoşulu güvence altında değil.

`AI.SetStance` çağrısının `pcall` ile hata vermemesi, sandalyeden kalkma animasyonunun ve smart object çıkışının tamamlandığını kanıtlamaz. Hareket, BT içindeki standing geçişinin tamamlanmasına bağlanmalı.

### Geçişi bozabilecek scheduler davranışı

`ShouldStartPatrol`, heartbeat 6 saniyeden eskiyse durumu `idle` yapıyor (`CastleUtils.lua:1211`). Heartbeat devriye döngüsünde ve nokta bekleyişinde yenileniyor; `Move`, stance giriş/çıkışı ve bazı animasyonlar boyunca yenilenmiyor. Bu işlemler sürerken aktif davranış boşta sanılabilir. Böylece yeni patrol veya önceliği daha yüksek yemek interrupt'ı, normal kalkış adımı tamamlanmadan gönderilebilir.

Logda 13 `Patrol davranisi basladi` kaydına karşılık 690 `Patrol interrupt baslatiliyor` kaydı var. Bu, gereksiz tekrar gönderimleri için somut kanıt. Verilen bench, `MeleeGuard_7` için log satırı 2536'da atanmış; bu guard'ın yemek tetiklemesi 2774'te görülüyor. Bununla birlikte mevcut kalkış loglarında NPC kimliği bulunmadığından, bu guard'ın tam olarak hangi kalkış/interrupt sıralamasında takıldığı mevcut logdan kesinleştirilemiyor.

### Hedef davranış

`meal_pending → patrol_exiting → standing tamamlandı → patrol noktası bırakıldı → kazan yürüyüşü`

Standing tamamlanmadan runtime durumunun yeni bir hareket başlatabilecek şekilde `idle` yapılmaması gerekir. Yeni yemek yürüyüşü, doğrudan çağrıldığında ve save/load sonrasında da aynı standing önkoşulunu kendi girişinde sağlamalı.

## 2. Yemek aldıktan sonra ayakta kalan NPC'ler

Bu belirtiyi üreten birden fazla yol var. Kullanıcının ek gözlemi, boş koltuk varken daha önce yemek alan NPC'nin beklediğini ve daha sonra yemek alanın oturduğunu belirtiyor. Logdaki yemek alma ve atama olayları birlikte izlendiğinde bu sıra bozulması da doğrulanıyor. Öncelikli düzeltme, yemek alma ile koltuk ataması/oturma arasındaki geçiş olmalı.

### A. Yemek alma anında koltuk ayrılmıyor; ayrı interrupt'a geçişte sıra kayboluyor — kod ve logla doğrulandı

Mevcut normal akış şu şekilde:

`kase dolduruldu → meal_ready yazıldı → switch döngüsü → eating yazıldı → AddInterrupt gönderildi → eat_at_table çalışırsa GetMealBench çağrıldı → oturma denendi`

Yemek alma işleminin sonunda (`nebakovrising_walk_to_bed.xml:228` ve `:348`) koltuk rezervasyonu yapılmıyor. İlk `GetMealBench` çağrısı ayrı `nebakovrising_eat_at_table` davranışının hedef arama döngüsünde (`:423`). Dolayısıyla atama sırası yemek alma sırasına değil, bu yeni davranışların hangi sırayla gerçekten çalıştığına bağlı. `GetMealBench` içinde yemek alma sırasına göre bir kuyruk da yok; ilk çağıran NPC ilk uygun slota sahip oluyor.

Scheduler ayrıca `eating` durumunu oturma interrupt'ını göndermeden önce yazıyor (`switch.xml:762`). Yeni davranış başlayamaz veya atama aşamasına ulaşamazsa NPC için yemek hazır ve runtime durum eating görünüyor; başlangıç onayı olmadığı için tekrar gönderilmiyor. Kullanılabilir koltuklar bu sırada diğer NPC'lere atanabiliyor.

Somut log sırası, save/load öncesinde:

| Log satırı | Olay | O ana kadar modun rezerve ettiği koltuk |
| --- | --- | --- |
| 2699 | `RangedGuard_12`: `meal_ready` | 3 / 10 |
| 2702 | Aynı NPC için `eating` yazılıyor | 3 / 10 |
| 2704 | Oturma interrupt'ı gönderildi logu | 3 / 10 |
| 2724 | Daha sonra `MeleeGuard_3`: `meal_ready` | 3 / 10 |
| 2729 | `MeleeGuard_3` için koltuk atanıyor | 4 / 10 |
| 2755–2929 | Diğer NPC'lere kalan koltuklar atanıyor | 10 / 10'a kadar |

`RangedGuard_12` için bu save/load'a kadar koltuk ataması yok. Boş koltuk bulunamadığı logları, yükleme sonrasında diğerlerinin rezervasyonları doluyken ortaya çıkıyor (`:3124`). Dolayısıyla bu NPC'nin ilk aksaması koltuk kapasitesi dolmadan oluşmuş; sonradan görülen kapasite yetersizliği başlangıçtaki sıra kaybını açıklamıyor. Yukarıdaki 3 / 10 sayısı Lua rezervasyon sayısıdır; tek başına vanilla NPC'lerin fiziksel doluluğunu ölçmez. Buna rağmen sonraki NPC'lerin atama alabilmesi, yemek alma sırasının korunmadığını doğrudan gösteriyor.

Kazan yürüyüşü ve oturma interrupt'ları aynı önceliği (`100`) ve `IgnorePriorityOnPreviousInterrupt=false` kullanıyor. Eski davranışın cleanup'ı bitmeden yeni interrupt gönderilmesi araştırılacak yarış koşullarından biri. Mevcut log, motorun bu isteği reddettiğini/ertelediğini veya BT'nin tam hangi düğümde durduğunu tek başına kanıtlamıyor; `submitted` kaydı davranış başlangıç onayı değildir.

### B. Koltuk kapasitesi ve koltuğun bırakılmaması — ek sorun, kod ve logla doğrulandı

`CastleUtils.mealBenchSelectors` toplam 10 oturma slotu içeriyor (`CastleUtils.lua:78`). Logda 13 ayrı guard için akşam yemeği başlatılıyor ve 10 slot atanıyor. `RangedGuard_12` için yemek alındıktan sonra tekrar tekrar `NPC icin bos yemek bench'i yok` yazılıyor (`kcd.log:3124`, `:3368` ve devamı).

Yemek bitince akşam yemeği NPC'leri `stayAtTable` döngüsüne girip uyku saatine kadar koltuğu tutuyor (`nebakovrising_walk_to_bed.xml:544–560`). Koltuk ancak davranışın sonunda bırakılıyor. Bu nedenle yemek süresi bitmiş olsa bile bekleyen NPC'lere yer açılmıyor. Yemeğe gitme başlangıçlarını zamana yaymak, koltuklar bırakılmadığında kapasite sorununu çözmez.

`smartObject` ve `smartObject2` adları aynı fiziksel bench'in iki ayrı oturma slotuna işaret ediyor: incelenen logda 10 selector 10 farklı WUID'ye çözülüyor. Bu çiftler birleştirilmemeli.

### C. Oturma denemesinin zaman aşımı pratikte etkisiz — kodla doğrulandı

Oturma watchdog'u `mealSeatWaitTicks < 1000000` koşulunu kullanıyor ve her turda `1s`, `GameTime` bekliyor (`nebakovrising_walk_to_bed.xml:565`). Kullanılamayan veya erişilemeyen bir slotta davranış çok uzun süre running kalabilir. Bu sırada dış scheduler durumu `eating` olarak görüyor; ayrı bir ilerleme denetimi yok.

### D. Retry aynı koltuğa dönebiliyor — kodla doğrulandı

`RetryMealBench` başarısız selector'ı `mealBenchAttempts[npcKey]` içine kaydediyor (`CastleUtils.lua:856`). `GetMealBench` bu listeyi okumadan ilk boş selector'ı seçiyor (`:823`). Böylece serbest bırakılan sorunlu koltuk bir sonraki denemede tekrar atanabilir.

Ayrıca oturma işlemi timeout yerine hemen fail olursa `OnFail`, `meal_retry_wait` yazar ama atamayı değiştirmez (`nebakovrising_walk_to_bed.xml:628`). Bu yol da aynı koltuğun sürekli denenmesine neden olabilir.

### E. Geçersiz kayıt ve eksik cleanup — kodla doğrulandı

- Aktif veya save'den gelen atanmış selector çözülemezse `GetMealBench` alternatif aramadan `nil` döner (`CastleUtils.lua:795–817`). BT'nin hedef beklemesi sona erip yeniden denense de bozuk atama kalabilir.
- `ReleaseMealBenchForNpc`, runtime assignment yoksa owners tablosunu temizlemeden döner (`:877`). Save'den yalnızca ownership rezerve edilmiş durumda bu, koltuğu dolu bırakabilir.
- Ölüm nedeniyle kayıt/yatak temizliği meal ownership tablolarını temizlemiyor (`RemoveManagedNpcRecord`, `ReleaseBedAssignmentForNpc`). Ölen NPC'nin koltuğu reload'a kadar rezerve kalabilir.
- Scheduler'ın erken `eating` yazması ve başlangıç onayının olmaması, yukarıdaki yemek sonrası geçiş sorununun parçası. Log `RangedGuard_12` için gönderim sonrası atama yapılmadığını gösteriyor; motor içindeki kesin durma noktası ayrıca izlenmeli.

## Uygulama sırası

### 0. Yemek alma ile koltuk rezervasyonunu aynı geçişe bağla

Dosyalar: `nebakovrising_walk_to_bed.xml`, `CastleUtils.lua`, `switch.xml`; ortak BT fonksiyonu ayrılırsa ilgili AI/SmartEntity kaydı.

- Her iki yemek toplama yolunda, kase doldurma başarıyla tamamlandığı anda ortak bir `OnMealCollected` benzeri işlem çağrılsın. Aynı Lua işlemi içinde yemek alındı bilgisini kaydetsin ve uygun koltuğu rezerve edip selector'ı persist etsin. Slot yoksa NPC'yi yemek alma sırasına göre bekleme kuyruğuna eklesin.
- Rezervasyon sırasında daha önce yemek alıp kuyrukta bekleyenlere öncelik verilsin. Yeni gelen doğrudan `GetMealBench` çağrısıyla sırayı geçemesin. Kuyruk sırası, yeniden denemelerde ve save/load'da korunabilsin.
- Normal yemek toplama sonrasında masaya gitme/oturma ortak bir BT alt akışıyla aynı aktif davranış içinde devam etsin. Böylece normal akışın ilerlemesi aynı öncelikli ikinci bir `AddInterrupt` isteğinin kabul edilmesine bağlı kalmasın. Save/load için aynı alt akışı kullanan ayrı bir resume wrapper'ı tutulabilir.
- Alt akış mevcut rezervasyonu kullansın; yeniden koltuk seçmesin. Geçersiz slot ve oturma hatasında kontrollü yeniden atama yapılsın. `meal_ready → walking_to_seat → seating → eating` ayrımı kurulsun; `eating` gerçek yemek animasyonu başladıktan sonra yazılsın.
- Slot arama nedeniyle, alınmış yemeğin varlığı doğrulandığı hâlde kazan yürüyüşü yeniden başlatılmasın. Yeni ortak akış için eski/save'den gelen `meal_ready` ve `eating` kayıtları uyarlanmalı.
- Ayrı interrupt gerektiren resume yolunda request ile gerçek başlangıç ayrı durumlar olsun; süreli başlangıç onayı ve koşullu retry bulunsun.

### 1. Geçiş sahipliğini ve gözlemlenebilirliği düzelt

Dosyalar: `CastleUtils.lua`, `nebakovrising_patrol.xml`, `switch.xml`.

- Devriye çıkışı için `patrol_exiting` gibi açık bir runtime durum ekle. Akşam yemeği isteği önce devriyenin güvenli çıkışını tetiklesin; yeni yemek interrupt'ı bu çıkış tamamlanınca gönderilsin.
- Davranış başlangıcında request'i onayla. Başlamış davranış, yalnızca son heartbeat eski diye tekrar gönderilmesin.
- Yürüyüş, stance geçişi ve uzun animasyonlarda heartbeat/progress güncelle. Watchdog, davranışın ilgili fazını ve varsa aktif geçiş sahipliğini kontrol etsin.
- Eski davranışın gecikmiş cleanup'ı yeni davranışın durumunu `idle` yapamasın; state değişikliği beklenen mevcut state/istek kimliğiyle koşullu olsun.
- Geçiş loglarına NPC adı, runtime durum, meal stage, kaynak/hedef selector, hedef WUID ve başarısızlık nedeni ekle. Logları durum değişimlerinde ve sınırlı sıklıkta üret.

### 2. Standing geçişini hareketin önkoşulu yap

Dosyalar: `nebakovrising_patrol.xml`, `nebakovrising_walk_to_bed.xml`.

- `nebakovrising_resume_meal_walk` girişinde standing stance'ini alıp giriş işleminin tamamlanmasını bekle; kazan `Move` düğümünü standing kapsamına yerleştir. Zaten ayakta olan NPC bu adımı gecikmesiz geçebilmeli.
- Normal devriye çıkışı ve fail/interrupt sonrası toparlanma aynı güvenli çıkış kuralını izlesin. Nokta rezervasyonunu NPC fiziksel olarak çıktıktan sonra bırak.
- Uyku yürüyüşünün girişinde de aynı önkoşulu uygula; `nebakovrising_walk_to_bed` ilk yatak `Move`'unu şu anda doğrudan başlatıyor (`:56`).
- Standing başarısız olursa yürüyüşe devam etme; süreli toparlanma durumuna geç. Süre dolunca başarı kabul edip hareketi zorlamak yerine nedeni loglayıp kontrollü tekrar dene.
- `AI.SetStance` yardımcı olarak kalabilir; başarı ölçütü standing BT geçişinin tamamlanması olsun.

### 3. Koltuk ataması ve retry'ı tamamla

Dosyalar: `CastleUtils.lua`, `nebakovrising_walk_to_bed.xml`, timeout ayarları için `nebakovrising.lua`.

- Slotları mevcut selector'larıyla ayrı tut; runtime'da WUID ve gerçek doluluk/rezervasyon durumunu, mevcut API veya vanilla kaynak mekanizmasıyla doğrula. Lua owners tablosu yalnızca modun rezervasyonunu gösterir.
- Hata nedenlerini ayır: `no_free_seat`, `target_not_ready`, `target_invalid`, `seat_busy`, `approach_failed`, `seat_timeout`, `eat_failed`.
- `mealBenchAttempts` bilgisini bütün seçim yollarında kullan. Başarısız slotu süreli cooldown'a al; diğer uygun slotları dene. Hepsi başarısızsa cooldown sonrası kontrollü yeni tur başlat.
- Hem timeout hem hemen fail olan oturma girişimleri sorunlu atamayı bırakıp başka uygun slota geçsin. Yemek animasyonu gibi slotla ilgisiz hatalar gereksiz yere bütün slotları engellemesin.
- `1000000` yerine yapılandırılabilir ve ölçülebilir timeout kullan. Başlangıç önerisi oturma/approach için toplam 30 saniye; uzun güzergâh ölçümünde approach ve oturma süreleri ayrılmalı. Süreler tek bir açık saat kaynağına dayanmalı ve oyun içi testte ayarlanmalı.
- Stream edilmemiş hedefe kısa bir hazır olma toleransı tanı. Süre sonunda hâlâ çözülemeyen atamayı temizleyip alternatif ara; WUID'leri save kimliği olarak kullanma.
- Koltuk değişirken `mealCollected=true` ve alınmış yemek bilgisi korunsun; NPC tekrar kazana gönderilmesin.

### 4. Kuyruğun ilerlemesini sağla

Dosyalar: `CastleUtils.lua`, `nebakovrising_walk_to_bed.xml`.

- Koltuk bekleyen NPC'ler için aynı anda tek kayıt içeren, adil sırayla ilerleyen bir kuyruk oluştur. Bekleme fazı açıkça izlenebilsin.
- Uygulanan davranış: akşam yemeğini bitiren her NPC ayağa kalkar, koltuğunu bırakır ve uyku saatine kadar ayakta idle bekler. Bu davranış kuyruk doluluğuna bağlı değildir.
- Koltuğu fiziksel çıkış tamamlandıktan sonra sıradakine ata. Böylece Lua tarafında boş görünen ama hâlâ kullanılan slota yeni NPC gönderilmesin.
- Kuyruk bekleme hali uyku saati, ölüm ve daha yüksek öncelikli davranışlarla sonlanabilsin; uykuya geçerken koltuk/kuyruk temizliği yapılsın.
- On koltuk, yemek bitirenlerin kalkmasıyla yeniden kullanılabilir. Bekleyen NPC'ler yemek alma sırasını korur.

### 5. Save/load ve cleanup'ı tamamla

Dosyalar: `CastleUtils.lua`, `switch.xml`, `nebakovrising_walk_to_bed.xml`.

- NPC adına göre idempotent bir meal cleanup işlemi oluştur. Runtime assignment yokken de owners tablosundaki o NPC'ye ait rezervasyonları temizlesin.
- Ölüm/kayıt silme, yemek tamamlanması, geçersiz hedef, uykuya geçiş ve kalıcı iptal yollarını bu temizliğe bağla. Geçici interruption sırasında alınmış yemek bilgisi korunmalı.
- Load'da rezervasyonları geçerli managed kayıtlar ve meal fazlarıyla uzlaştır; çakışan ve artık geçersiz selector'ları temizle. Kısa süreli streaming yokluğunu kalıcı bozuk hedefle karıştırma.
- Runtime request/heartbeat/deadline bilgilerini yeniden kur. `meal_resuming` ve oturma interrupt'larına başlangıç onayı ve süreli kurtarma ekle; çalışan davranışın kopyasını göndermemek için sahipliği denetle.
- Eski `meal_ready`/`eating` kayıtlarıyla uyumluluğu ve `mealCollected` kontrolünü koru. Yeni fazlar eklenirse eski kayıtları açıkça eşle.
- `seated`, `eating`, `meal_eaten_waiting`, `leaving_seat` durumlarını ayırt et; logdaki “yemek bitti” ile fiziksel koltuk boşalmasını aynı olay sayma.

## Doğrulama ve kabul ölçütleri

1. **Verilen bench:** `bench_1place_low11_e16ab7d7-fe58-452a-bb1a-daecca10f3df` üzerinde oturan guard'ın akşam yemeği tetiklensin. Log sırası çıkış isteği → standing tamamlandı → kazan hareketi olsun; sandalyede hareket denemesi görülmesin.
2. **Diğer başlangıçlar:** İkinci bench, leaning noktası ve normal ayakta guard noktası için aynı geçiş çalışsın. NPC otururken veya kalkarken save/load da kapsansın.
3. **Uzun hareket:** 6 saniyeden uzun patrol yürüyüşünde, stance girişinde ve kalkışta yeni patrol interrupt'ı gönderilmesin; yeni yemek davranışı eski cleanup tarafından bozulmasın.
4. **Slot kimliği:** 10 selector'ın 10 ayrı oturma WUID'sine çözüldüğü doğrulansın. Bir slotta aynı anda tek NPC rezervasyonu olsun; vanilla NPC doluluğu da hesaba katılsın.
5. **Bozuk/dolu slot:** Seçilen bir koltuk erişilemez veya kullanılıyor olsun. NPC timeout sonrasında farklı uygun koltuğa geçsin; aynı başarısız koltuk cooldown boyunca tekrar seçilmesin. Hemen fail yolu da aynı şekilde doğrulansın.
6. **13 guard / 10 koltuk:** Sonradan gelen üç guard kuyrukta ilerlesin. Yemek bitirenler bekleyenlere yer açsın; bütün guard'lar yemek yiyebilsin. Kuyruğa girmek ve koltuk değiştirmek tekrar yemek alma başlatmasın.
7. **Ölüm ve iptal:** Rezervasyonu olan NPC, runtime assignment kurulmadan önce ve kurulduktan sonra ayrı ayrı silinsin/ölsün. Owners, assignment, attempts ve kuyrukta artık kayıt kalmasın.
8. **Save/load:** Yemek alınmışken, koltuk beklerken, otururken ve yemeği bitirip masada beklerken kayıt yükle. Yemek toplama durumu korunsun, ölü veya kayıtsız NPC koltuk tutmasın, kesintisiz çalışan davranış kopyalanmasın.
9. **Uyku sınırı:** Koltuk bekleyen ve masada oturan NPC'ler uyku saati geldiğinde temiz şekilde yatak akışına geçsin.
10. **Statik/paket kontrolü:** Değişen XML'leri parse et, Lua ve XML içine gömülü Lua bloklarının sözdizimini kontrol et; ardından `.pak` içeriğini değişen kaynaklarla karşılaştır. Animasyon ve fiziksel kalkış başarısı oyun içinde doğrulansın.
11. **Boş koltuk varken yemek sırası:** A NPC'si yemek aldığında en az iki uygun slot bulunsun. A'nın koltuk rezervasyonu aynı yemek toplama geçişinde oluşsun; B daha sonra yemek aldığında A'ya ayrılmış koltuğu alamamalı. A'nın rezervasyonu ve masaya ilerlemesi başka interrupt'ın başlamasını beklememeli. A'nın hedefi bozuksa diğer uygun slota geçişini doğrula; B'nin farklı koltukta daha kısa yolu olması doğal hareket süresi farkı olarak ele alınmalı.
12. **Interrupt başlangıcı gecikmesi:** Resume sırasında oturma interrupt'ı başlayamasın. NPC yanlışlıkla `eating` durumunda kalmamalı; sahiplik kontrolüyle kontrollü tekrar denensin. Aynı NPC için iki oturma davranışı oluşmasın.

Geç rezervasyon, erken `eating`, retry ve cleanup kusurları koddan; yemek alma/atama sırasının bozulması, sonradan koltuk yetersizliği ve tekrar interrupt gönderimleri mevcut logdan doğrulandı. Oyun içindeki animasyon ve navigasyon sonucu ayrıca gözlemlenmeli.

## Uygulanan değişiklikler ve yerel doğrulama

- `CastleUtils.lua`: yemek alma anında kalıcı koltuk rezervasyonu; kalıcı FIFO sıra numarası; gerçek `benchOccupant` kontrolü; WUID çakışması kontrolü; süreli başarısız koltuk listesi; hedefin hazır olması için kısa tolerans; runtime atama olmasa da rezervasyon temizliği; ölüm temizliği; request/start ayrımı ve token ile davranış sahipliği.
- `nebakovrising_meal.xml`: ortak standing, yemek, idle, heartbeat, hareket zaman aşımı ve devriye çıkış gözlemcisi fonksiyonları. Stand başarısızsa hareket veya koltuk bırakma başarı kabul edilmez. Oturma zaman aşımı, kaseyi ele alma ve yemek animasyonuna giriş bekleyişini de kapsar.
- `nebakovrising_walk_to_bed.xml`: hem kahvaltı hem akşam yemek toplama yolları, rezervasyondan sonra aynı aktif davranış içinde ortak masa akışına devam eder. Uyku ve kazan hareketleri standing önkoşuluna bağlıdır. Eski `meal_ready`/`eating` kayıtları için ayrı resume girişleri korunmuştur.
- `nebakovrising_patrol.xml`: heartbeat bütün davranışı kapsar. Hareket/stance/animasyon girişi beklerken yemek veya uyku isteği gözlemlenir; önce standing, ardından devriye rezervasyonunun bırakılması ve yeni davranış gelir.
- `switch.xml`: interrupt gönderimini gerçek davranış başlangıcı saymaz ve yemek animasyonu başlamadan `eating` yazmaz. Yemek sonrası idle kaydı save/load'dan da devam eder.
- SmartEntity tablosu: ortak BT fonksiyonları ve akşam idle girişinin kayıtları eklendi.

Zaman aşımları `nebakovrising.Config` içindedir: request 10 sn, heartbeat 15 sn, hareket 120 sn, standing 20 sn, oturma 30 sn, hedef hazır olma toleransı 10 sn, başarısız koltuk cooldown'u 60 sn. Deadline'lar `System.GetCurrTime()` kullanır; heartbeat ve bekleme düğümleri bu süreleri gözlemler.

Yerel test komutu: `python tools/test_meal_flow.py`. Testler gerçek `CastleUtils.lua` kodunu Lua 5.1 içinde çalıştırır. Oyun API'leri mock'tur. Ortak XML akışı da kooperatif bir test yürütücüsüyle çalıştırılır: koltukta takılma, kaseyi ele alamama, standing başarısızlığı, alternatif koltuk, yemek bitirme, ayakta idle, uykuya geçiş ve yemek bitmiş save'den devam senaryoları kapsanır. Animasyonların ve gerçek navmesh'in başarısını bu testler doğrulamaz.

Paketleme komutu: `python tools/build_pak.py`. Önce geçici paket oluşturulur; dosya listesi, CRC ve bütün kaynak dosyalarıyla byte eşitliği doğrulanır. Mevcut kurulu paketin yedeği geçici dizine alınır ve doğrulanmış paket `Data/nebakovrising.pak` yerine konur.

25 Ekim 2026 yerel sonuç: 29 test geçti; tüm Lua dosyaları ve XML içindeki Lua blokları Lua 5.1 ile derlendi; XML ve SmartEntity ağaç referansları doğrulandı. Kurulu paket 78 dosyayla yeniden oluşturuldu; bütün içerik kaynaklarla byte düzeyinde karşılaştırıldı. Gerçek oyun içi animasyon/navmesh testi yapılmadı.
