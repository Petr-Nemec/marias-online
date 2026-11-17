# Jak program uplatňuje pravidla

Výchozí dokumenty:

- Obecná pravidla hry mariáš (Český svaz mariáše),
- Pravidla licitovaného mariáše ČSM, platná od roku 2014,
- Bodovací tabulka prémiových bodů pro licitovaný mariáš, platná od roku 2014
  (<https://www.talon.cz/pb/Bodovaci_tabulka_2014.pdf>).

Tento dokument popisuje, co přesně program dělá, a u pravidel, která vyžadují úsudek rozhodčího
nebo hráčů, uvádí zvolený výklad. Kódem se rozumí moduly v adresáři `marias/`.

## 1. Karty, rozdávání

- 32 karet, barvy červené (trumfy „červená“), zelené, kule, žaludy.
- Pořadí v hrách s trumfy: 7, 8, 9, spodek, svršek, král, **desítka**, eso.
  Při betlu a durchu: 7, 8, 9, desítka, spodek, svršek, král, eso.
- Body: eso a desítka po 10, poslední štych 10, celkem 90. Hláška 20, trumfová 40.
- Rozdává se 5-5-5, dvě karty do talonu, 5-5-5; první karty dostává forhont (hráč po levici
  rozdávajícího). Rozdávající se po každé hře posouvá.
- Soutěžní režim stolu: karty se po hře **nemíchají**. Program sesbírá hromádky štychů,
  nevyhrané karty a talon v náhodném pořadí hromádek (uvnitř hromádky pořadí zachová) a balíček
  sejme (nejméně dvě karty). Stůl lze založit i s mícháním před každou hrou.
- U stolu pro čtyři rozdávající pauzíruje a vyúčtovává se jako obránce (platí i dostává).

## 2. Licitace (`deal.py`)

Licitační žebříček (číslo = stupeň):

| | | | |
|---|---|---|---|
| 1 Sedma | 4 Sto a sedma | 7 Betl | 10 Dvě sedmy a sto |
| 2 Sedma červená | 5 Sto červených | 8 Durch | 11 Dvě sedmy, červená trumf |
| 3 Sto | 6 Sto a sedma červených | 9 Dvě sedmy | 12 Dvě sedmy, červená trumf, a sto |

- Licituje se po dvojicích. Začíná **zadák**, který nabízí **forhontovi**. Forhont má přednost:
  na nabídku odpovídá „mám“ (drží stupeň), nebo „pas“. Nabízející musí jít výš, stupně smí
  přeskakovat.
- Odstoupí-li nabízející, nastoupí na jeho místo prostřední hráč a nabízí dál proti držiteli.
  Odstoupí-li držitel, přejde přednost na prostředního hráče, který na právě nabídnutý stupeň
  může jen říct „mám“. Odstoupivší hráč se do licitace nevrací.
- Licitaci vyhrává hráč, který zůstane poslední. Nabídne-li někdo stupeň 12 a druhý jej drží,
  zbývá už jen pas.
- **Nikdo nelicitoval**: hrát musí forhont, nejméně sedmu (smí ohlásit cokoli vyššího, smí
  i složit – viz omyl).

## 3. Talon a ohlášení závazku

- Vítěz licitace vezme talon (vidí, které dvě karty v něm byly), odloží dvě karty a ohlásí
  závazek: vylicitovaný, nebo jakýkoli vyšší. Trumfovou barvu, u dvou sedem i pomocnou, volí sám
  (u „červených“ stupňů jsou trumfy červené).
- Esa a desítky smí do talonu jen při betlu a durchu. Hlášenou sedmu (trumfovou, u dvou sedem
  i pomocnou) do talonu odložit nelze.
- Sedmu nelze ohlásit bez trumfové sedmy v ruce.
- **Omyl**: kdo vylicitoval jen obyčejnou sedmu (stupeň 1, i když hraje z povinnosti), smí karty
  složit. Platí každému flekovanou hru a flekovanou sedmu, tj. 2 + 4 = **6 násobků základu**.

## 4. Fleky

- Pořadí: **flek** (obrana), **re** (aktér), **tutti** (obrana), **boty** (aktér); každý stupeň
  sazbu zdvojnásobí. Víc stupňů není.
- Flekuje se zvlášť každá část závazku: hra a sedma, sto a sedma, sto, betl, durch, dvě sedmy,
  dvě sedmy a sto. Na flek obrany může aktér dát re jen na tu část, která byla fleknuta, a tak dál.
- V kole obrany se ptá nejprve hráč po aktérovi, pak druhý obránce; flek kteréhokoli z nich platí
  pro celou obranu.
- **Sedma se sehrává, jen když obrana dala flek na sedmu, nebo aktér dal re na hru.** Jinak se
  nesehrává: nefleknutá hra i sedma se aktérovi vyplatí, hra fleknutá bez re se počítá jako
  prohraná (aktér platí flekovanou hru) a sedma jako vyhraná.
- Dvě sedmy: má-li některý obránce v ruce **čtyři a více pomocných**, dvě sedmy se nesehrávají
  a aktér je platí. U dvou sedem a sta se hra sehrává kvůli stu a dvě sedmy jsou prohrané.

## 5. Sehrávka (`rules.py`)

- Vynáší forhont, při betlu a durchu aktér. Štych bere nejvyšší karta vynesené barvy, nebo
  nejvyšší trumf.
- Povinnosti: **přiznat barvu**; **přebít**, pokud to jde (je-li barva už přebita trumfem, stačí
  ji přiznat); nemá-li hráč barvu, **musí trumfovat**, a je-li ve štychu trumf, **přebít vyšším
  trumfem**, pokud může; jinak odhazuje libovolně. Při betlu a durchu trumfy nejsou, přiznávat
  a přebíjet se musí.
- Program nedovolí zahrát kartu, která pravidla porušuje, takže **renonc nastat nemůže**
  a sankce za něj nejsou potřeba. Hráč vidí, proč kartu zahrát nesmí.
- **Hlášená sedma** smí aktér zahrát až jako poslední kartu její barvy (u dvou sedem platí
  pro obě sedmy).
- **Hlášky** se hlásí zahráním první karty dvojice (svršek nebo král, druhou má hráč v ruce),
  a to v závazcích, kde se počítají body (sedma, sto, sto a sedma, dvě sedmy a sto). Hlášku může
  hlásit kdokoli a štych může vzít kdokoli. V klientu se hlásí automaticky; po vypnutí volby se
  program při každé hlášce zeptá („Hlásit 40“ / „Zahrát mlčky“).
- Betl končí prvním štychem aktéra, durch prvním štychem obrany, dvě sedmy prvním porušením
  (pomocná sedma musí vzít předposlední štych, trumfová poslední).

## 6. Vyúčtování (`scoring.py`)

Sazby v násobcích základu (soutěžně 0,20 Kč):

| Část | Sazba | | Část | Sazba |
|---|---|---|---|---|
| hra | 1 | | betl | 15 |
| sedma | 2 | | durch | 30 |
| sto | 4 | | dvě sedmy | 40 |
| tichá sedma | 1 (nikdy se neflekuje) | | omyl | 6 |

- Červené trumfy zdvojnásobují všechny sazby trumfových závazků (včetně tiché sedmy).
- Každý flek sazbu dané části zdvojnásobí. Částky se platí každým obráncem (a pauzírujícím).
- **Hra** (v závazku sedma): vyhrává strana s **více** body; při rovnosti aktér prohrává.
- **Tiché sto**: dosáhne-li kterákoli strana ve hře 100 a více bodů (počítají se všechny hlášky),
  sazba hry se zdvojnásobí a vítězná strana dostane dvojnásobnou hru ještě za každých dalších
  10 bodů nad sto. Vzorec: `hra × 2 × (1 + (body − 100) / 10)`.
- **Sto vyhrané**: do stovky se počítá jen jedna hláška, další hlášky se ale počítají do přebytku.
  Platí se sazba sta × (1 + počet desítek nad 100).
- **Sto prohrané**: do stovky se počítá jen jedna hláška. Aktér platí sazbu sta za každých
  chybějících 10 bodů a navíc za každých 10 bodů, které obrana získala hláškami.
- **Sedma**: vyhrává, když aktér vezme poslední štych trumfovou sedmou.
- **Tichá sedma** (jen při závazku sto, kde sedma není hlášená): vezme-li poslední štych majitel
  trumfové sedmy jejím zahráním, jeho strana dostane polovinu sazby sedmy. Je-li sedma
  v posledním štychu zabita – i spoluhráčem –, platí strana, které patřila.
- **Limit**: nejvýš 500 násobků základu za hru, 750, pokud flekovali oba obránci.

## 7. Prémiové body (`premium.py`)

Body se připisují jen za ohlášený a vyhraný závazek (u fleků na betl a durch za úspěšný flek).
Rozhoduje dvanáct karet aktéra po vzetí talonu, tj. **odložené karty se počítají**, jako by je
aktér držel. Každé kritérium má hodnotu „s výnosem“ (aktér je forhont) a „bez výnosu“.
Splní-li hra víc kritérií, sčítají se, ale jen nejvyšší z nich se počítá v hodnotě bez výnosu.
Červené trumfy body zdvojnásobují.

- **Sedma** na 3 / 2 / 1 trumf: 5 / 10 / 20 s výnosem, 7 / 14 / 28 bez výnosu.
- **Sto** podle počtu trumfů a toho, zda aktér měl trumfové eso a desítku, s příplatkem za sto
  s netrumfovou hláškou; sto na pět nebo šest trumfů bez obou ostrých.
- **Dvě sedmy** podle počtu trumfů (2–4) a pomocných (4), vyšší hodnoty se stem, příplatek bez
  trumfového esa, výjimky z poznámek 4 a 5 tabulky.
- **Betl**: chytající eso 10, šesterák s jedinou chytající kartou 5 (ne, byla-li tato karta hned
  vynesena prvním výnosem).
- **Durch**: 10 za každou barvu, která není ložená.
- **Úspěšný flek na betl** se dvěma nebo třemi barvami v ruce: 5. **Úspěšný flek na durch**
  s chytajícími kartami nejvýš ve dvou barvách (ne jen se dvěma esy): 10.

Posouzení „chytající karty“ a „ložené barvy“ tabulka ponechává na hráčích. Program je proto
počítá pevným vzorcem:

- karta je při betlu **chytající**, má-li soupeř pod ní více karet její barvy, než kolik jich má
  aktér pod ní (aktér ji pak nemůže vždy „podlézt“);
- barva je při durchu **ložená**, nemůže-li v ní aktér ztratit štych, ani kdyby všechny chybějící
  karty barvy držel jediný obránce.

## 8. Co program nedělá

- **Ložená hra** (vyložení karet a prohlášení výsledku bez dohrání) se nepoužívá, hra se vždy
  dohraje; betl, durch a dvě sedmy končí automaticky, jakmile je o nich rozhodnuto.
- Sankce za renonc, chybné rozdání a podobné procesní chyby nejsou potřeba, protože je program
  nedovolí.
- Prémiové body se zapisují na lístek stolu; soutěžní tabulky turnajů program nevede.
