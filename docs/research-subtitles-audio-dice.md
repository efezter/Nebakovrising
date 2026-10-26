# NPC üstü altyazı, konumsal ses ve zar masası — 26 Ekim 2026

Araştırma kapsamı: mevcut Nebakov Lua/Python kodu, kurulu köprü dosyaları, son oyun/köprü logları, kullanıcının test ettiği KCD2.AI.NPC arşivi, yerel vanilla Lua/BT dökümü ve aşağıdaki birincil belgeler. Bu çalışmada oyun davranışları değiştirilmedi veya oyun içi deney yapılmadı.

## 1. Konuşan NPC'nin üstünde altyazı

**Uygulanabilir bir yol var; canlı oyunda çizim testi gerekiyor.** Yerel `lua_dump_state/LuaState_Sorted.txt:23273` içinde `System.DrawLabel`, `:23344` içinde `System.ProjectToScreen` kayıtlı. [CryEngine'in API belgesi](https://www.cryengine.com/docs/static/engines/cryengine-3/categories/1638401/pages/15008755), `System.DrawLabel(position, size, text, r, g, b, alpha)` imzasını açıklıyor. Yerel `Scripts/Scripts/Entities/WH/Others/CrimeDebugger.lua:53` da etkinleştirilmiş bir entity'nin `OnUpdate` içinde çizim çağrısı yaptığını gösteriyor. Dökümde bulunması, bu sürümde görsel çıktının başarıyla sınandığı anlamına gelmez.

İlk tercih: yalnız aktif konuşmacının başı üzerindeki dünya konumuna kısa, satırlara bölünmüş metin çizmek. Her kare yenileme, mesafe sınırı, ekran dışında gizleme ve konuşma iptalinde temizleme gerekir. Uzun cümleler için birkaç parçaya bölme, okunabilirlik için kontur/gölge değerlendirilir. Vanilla görünümünün birebir eşleştiği iddia edilmez; `DrawLabel` ilk prototip, gerekirse projeksiyon ve HUD çizimi ikinci adımdır. Mevcut 250 ms telemetri zamanlayıcısı, her kare çizimin yerine kullanılmamalı.

Referans ZIP'teki `mod/ai_npc/main.lua:1216–1304`, HUD/ekran altı metni deniyor. `CryAction.SetSubtitle` yoksa `Game.ShowTutorial` ve HUD çağrılarına dönüyor. Bu, başa bağlı altyazının çalıştığına kanıt değildir; hatasız dönen `pcall` da görünür çıktı kanıtı sayılmaz.

Mevcut protokolde `line_start` yalnız satır numarası ve süre taşıyor (`src/Scripts/mods/nebakov_conversations.lua:529`); Python'da `Line.text` hazır. Metin, mevcut atomik `command.lua` kanalında sınırlandırılmış ve güvenli kaçış uygulanmış veri olarak iletilmeli. Lua'nın yeni dosya açmasına ihtiyaç yok. Satır/sahne/oturum eşleşmesi, ACK, satır sonu ve iptal temizliği korunmalı.

## 2. Mesafeyle değişmeyen ses

**Düzeltilebilir; mevcut bulgular kök nedeni henüz kesinleştirmiyor.** `tools/nebakov_voice_playback.py:64` içindeki `spatial_gains`, üç boyutlu mesafe, stereo yön ve 24 m'de sessizlik hesaplıyor. `SequentialPlayback.tick` devam eden satırda da güncel paketten yeniden hesaplıyor. Kurulu Python dosyası kaynakla SHA-256 olarak aynı.

Son oyun logunda `playing` durumunda 709 paket ve iki konuşmacı için yaklaşık 0,66–29,99 m aralığı bulundu. Bu, logdaki konumların sabit olmadığını gösterir; duyulan her satıra doğru gain'in uygulandığını tek başına kanıtlamaz.

[pygame belgesi](https://www.pygame.org/docs/ref/mixer.html#pygame.mixer.Channel.set_volume) stereo kanal seviyesinin oynatma sırasında değiştirilebildiğini açıklıyor. Ayrıca `Channel.get_volume()` stereo ayrımını yansıtmıyor; tek başına ölçüm olarak kullanılmamalı.

Dışarıya ses çıkarmayan SDL dummy sürücüsünde gerçek mixer çıkışı (`Mix_SetPostMix`) ölçüldü: aynı ses oynarken 0,6 gain yaklaşık 5092 RMS; 0,12 gain yaklaşık 998 RMS; sıfır gain 0 RMS verdi. Oynatma öncesi ayar da bu kurulumda etkiliydi. Bu deney mixer'ın çalıştığını doğrular; oyun içi sorunun giderildiği anlamına gelmez.

Önerilen teşhis: yalnız kontrollü test süresince, saniyede iki kez küçük dosyaya konuşmacı/entity, paket sıra numarası/yaşı, mesafe, sol/sağ gain ve aktif kanal bilgisi yazmak. Aynı uzun satır sürerken 2, 8, 16 ve 24 m testleri yapılmalı. Uygulanan gain sıfırken ses sürerse başka ses kaynağı/işlem veya farklı oynatma yolu araştırılır; henüz bunun olduğuna dair kanıt yok. Güncel paket gelmiyorsa telemetri akışı; değerler değişip uygulanmıyorsa kanal güncellemesi düzeltilir.

Kurulu Sound Framework 1.2.0'ın son logu FMOD ve komutların hazır olduğunu gösteriyor; Nebakov satırını native oynatma başarısı göstermiyor. [Framework rehberi](https://github.com/tkhquang/KCD2Tools/blob/main/SoundFramework/docs/MODDING.md) loose WAV için `Space=3d`, mesafe sınırları ve konumlu `sfw_play` sunuyor. Ayrıca native ses ve baş üstü balon yolu var, fakat kayıt/metin localization paketi istiyor; paket değişikliği yeniden başlatma gerektiriyor. Dolayısıyla dinamik dört satır için doğrudan geçiş varsayılmamalı. Önce tek loose WAV ile konumsal ses denenmeli; iki backend aynı anda oynatılmamalı. Global `sfw_reload` diğer framework seslerini de durdurur.

## 3. İki muhafızın zar oynaması

**Vanilla davranışta doğrudan NPC–NPC desteği var.** Verilen `dice_behaviors` nesnesinin tür GUID'si `9a3317b0-9c92-466e-bab6-571f23356bca`, yerel `Libs/Tables/ai/smartEntity/SmartEntity__so_diceTable_new.xml:5` ile eşleşiyor. Masa yalnız dekor değil: iki oturma kaynağı, bardak/zar slotları ve challenger/opponent girişleri içeriyor.

Yerel `Scripts/AI/world/so_diceTable_new.xml` bulguları:

- `use_challenger` (:731) ikinci koltuğu, `use_opponent` (:1714) birinci koltuğu kullanıyor. Verilen prefab linkleriyle uyumlu.
- Challenger oturduktan sonra `use_opponent` davranışını etkinleştiriyor (:828). İkincisi başlangıçta disabled; bu sıra korunmalı.
- `playingAgainstNpc` ve `dice_playingNpcVsNpc` durumu (:902–906), karşılıklı bakış, senkronize sıra, `rollFirst`, `rollTurn`, `rollFinish` ve tepki animasyonları bulunuyor.
- Başarı/başarısızlık seçimleri `RandomGate` kullanıyor. Bu ambient oyun akışı, Henry'nin ekranlı ve puanlı minigame'ini iki NPC ile çalıştırdığımız anlamına gelmez.
- `DiceInteractor.OnUsed`, `dice:init` gönderiyor; masanın `Minigame.StartDice` çağrısı açıkça `player.id` kullanıyor (:101). NPC–NPC için Henry'yi bu çağrıya sokmak yerine mevcut ambient dallar kullanılmalı.
- Vanilla ağaç para kontrolü ve bazı durumlarda para oluşturma içeriyor. İlk prototipte ekonomi etkisi incelenmeli; `dice_playWithoutMoney` linkinin bulunması bütün para oluşturmayı otomatik olarak kaldırdığı şeklinde yorumlanmamalı.

İlk uygulama önerisi: tek masa ve iki muhafızla konsol testi; masanın gerçek runtime WUID'sini ve slot linklerini çözme; iki NPC/iki koltuğu atomik ayırma; doğal yaklaşma/oturma; challenger hazır olunca opponent; native sıra/animasyonları çalıştırma. Prefab içindeki genel `seat1_SO` adı veya editör child ID'si doğrudan tekil runtime kimliği varsayılmamalı.

İlk otomatik sürüm, yemek sonrası boşta olan ve uyanık muhafızlarla sınırlansın; nöbetteki muhafızlar masaya çekilmesin. Masa için ayrı rezervasyon, süre sınırı, combat/ölüm/despawn/save-load ve uyku vaktinde güvenli çıkış gerekir. Yemek masalarının rezervasyonları kullanılmamalı. AI sohbeti, temel zar oyunu doğrulandıktan sonra `dice-table-talk` profiliyle eklenebilir; native zar animasyonları sırasında standart konuşma için yürüme/dönme uygulanmamalı.

## Önerilen sıra ve kabul ölçütleri

1. Ses: mesafe/gain/kanal kaydıyla sorunu tekrarla; aynı satırda uzaklaşınca gerçek ses azalmalı ve 24 m'de susmalı.
2. Altyazı: tek satırlık `DrawLabel` denemesi, sonra mevcut `line_start/line_end` akışına metin ekleme. Metin yalnız doğru NPC'de, doğru satır süresince görünmeli.
3. Zar: bir challenger ve opponent, doğal oturma ve birkaç karşılıklı tur. İptalden sonra koltuk/aktivite rezervasyonu sızmamalı; ardından rutin ve vardiya entegrasyonu.

Bu bulgular uygulama için dayanak sağlar; üç özelliğin de güncel modda oyun içi başarıyla doğrulandığı iddia edilmez.
