# Mariáš Online

Licitovaný mariáš pro tři (nebo čtyři) hráče v prohlížeči, podle soutěžních pravidel
**Českého svazu mariáše** (Obecná pravidla hry mariáš a pravidla licitovaného mariáše, 2014)
včetně **prémiových bodů** podle bodovací tabulky ČSM 2014.

Server je jediným zdrojem pravdy: hlídá licitaci, talon, fleky i každou zahranou kartu, takže
nelze zahrát renonc ani vidět cizí karty. Klient je čistý HTML/CSS/JS bez frameworku.

## Co umí

- **Licitace po dvojicích** přesně podle ČSM: zadák nabízí forhontovi, „mám“ / „pas“, přednost,
  nástup prostředního hráče, všech 12 stupňů od sedmy po dvě sedmy se stovkou (červenou).
- **Talon a ohlášení závazku**: odložení dvou karet (esa a desítky jen při betlu a durchu,
  hlášená sedma nikdy), ohlášení vylicitovaného nebo vyššího závazku, **omyl** u sedmy.
- **Fleky** flek – re – tutti – boty, zvlášť na každou část závazku (hra, sedma, sto…).
- **Sehrávka** s povinností přiznat barvu, přebíjet a trumfovat, hlášky 20/40, hlášená sedma
  až jako poslední karta barvy, předčasné ukončení betlu, durchu a dvou sedem.
- **Vyúčtování**: sazby ČSM, červené dvojnásob, sto po desítkách, tiché sto, tichá sedma,
  limit 500 / zvýšený limit 750 násobků základu, platba pauzírujícího hráče u stolu pro čtyři.
- **Prémiové body** za těžké hry a úspěšné fleky na betl a durch, s rozpisem.
- **Herna**: veřejné i soukromé stoly (odkaz s kódem), diváci, chat, počítačoví hráči na volná
  místa, časový limit na tah, náhrada odpojeného hráče počítačem, návrat po výpadku spojení,
  lístek se stavem všech her, prohlídka karet a štychů po hře, zvukové upozornění.
- **Soutěžní rozdávání**: karty se po hře nemíchají, jen sbírají a snímají (lze přepnout na míchání).

Podrobný popis, jak program jednotlivá pravidla uplatňuje, je v [docs/PRAVIDLA.md](docs/PRAVIDLA.md).

## Spuštění na vlastním počítači

Potřebuješ Python 3.11 nebo novější.

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python -m marias.server            # http://127.0.0.1:8000
```

Kontroly, které běží i v CI:

```bash
ruff check marias tests && ruff format --check marias tests
mypy                               # strict
pytest                             # přes 90 testů včetně tisíců náhodně sehraných her
```

## Nasazení na server

Hra drží stav v paměti jednoho procesu, proto vždy běží **jeden** proces serveru. Před něj patří
reverzní proxy s HTTPS. Restart serveru rozehrané stoly ukončí.

### Docker + Caddy (doporučeno, HTTPS automaticky)

```bash
git clone https://github.com/Petr-Nemec/marias-online && cd marias-online
echo "MARIAS_DOMAIN=marias.tvoje-domena.cz" > deploy/.env
docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build
```

DNS záznam domény musí mířit na server a porty 80 a 443 musí být otevřené. Caddy si certifikát
od Let's Encrypt vyžádá sám.

### systemd + nginx

Postup je v hlavičce [deploy/marias.service](deploy/marias.service), konfigurace proxy v
[deploy/nginx.conf](deploy/nginx.conf). Služba běží pod vlastním uživatelem s omezenými právy.

### Konfigurace (proměnné prostředí)

| Proměnná | Výchozí | Význam |
|---|---|---|
| `MARIAS_HOST` | `127.0.0.1` | adresa, na které server naslouchá |
| `MARIAS_PORT` | `8000` | port |
| `MARIAS_ALLOWED_ORIGINS` | *(prázdné)* | povolené originy WebSocketu oddělené čárkou, např. `https://marias.example.cz`; prázdné = jen stejný původ jako stránka |
| `MARIAS_HSTS` | `false` | posílat hlavičku Strict-Transport-Security (zapni jen za HTTPS) |
| `MARIAS_MAX_TABLES` | `50` | nejvýš otevřených stolů |
| `MARIAS_MAX_CONNECTIONS` | `300` | nejvýš spojení celkem |
| `MARIAS_MAX_CONNECTIONS_PER_IP` | `10` | nejvýš spojení z jedné IP adresy |
| `MARIAS_SESSION_TTL` | `86400` | jak dlouho (s) přežije identita hosta bez připojení |
| `MARIAS_LOG_LEVEL` | `INFO` | úroveň logování |
| `MARIAS_OPERATOR` | *(prázdné)* | správce osobních údajů uvedený v Ochraně soukromí (jméno nebo název) |
| `MARIAS_CONTACT` | *(prázdné)* | kontakt na správce, např. e-mail, uvedený v Ochraně soukromí |
| `FORWARDED_ALLOW_IPS` | `127.0.0.1` | adresy proxy, jejichž `X-Forwarded-For` se věří (Uvicorn) |

Stav serveru: `GET /healthz`.

## Bezpečnost

- Server je autoritativní: klient posílá jen záměr (např. „zahraj kulové eso“), vše ověřuje engine.
  Každý hráč dostává jen svůj pohled na hru; cizí karty a talon se odhalí až po skončení hry.
- Všechny zprávy klienta se validují striktním schématem (Pydantic), neznámá pole se odmítají,
  texty se normalizují a zbavují řídicích a bidi znaků. Do stránky se uživatelský text vkládá
  výhradně jako text (`textContent`), nikdy jako HTML.
- Kontrola `Origin` u WebSocketu brání cizím stránkám v připojení za hráče.
- Omezení rychlosti zpráv, chatu a zakládání stolů, limity velikosti zpráv, počtu spojení
  celkem i na IP adresu, odpojení klienta, který nestíhá číst.
- Identita hosta je náhodný 256bitový token uložený v prohlížeči; server drží jen jeho SHA-256
  otisk. Kódy soukromých stolů se porovnávají v konstantním čase a neexistující stůl i špatný kód
  vrací stejnou odpověď.
- HTTP hlavičky: přísné Content-Security-Policy bez inline skriptů, `X-Frame-Options: DENY`,
  `nosniff`, `Referrer-Policy: no-referrer`, volitelně HSTS.
- Kontejner běží jako neprivilegovaný uživatel s read-only souborovým systémem a bez capabilities;
  systemd jednotka používá sandbox (`ProtectSystem=strict`, filtr syscallů…).

## Struktura

```
marias/
  cards.py, contracts.py   karty, žebříček a sazby
  rules.py                 povinnosti při sehrávce, kdo bere štych
  deal.py                  stavový automat jedné hry (licitace → talon → fleky → sehrávka)
  scoring.py, premium.py   vyúčtování a prémiové body
  bot.py                   počítačový hráč
  table.py                 stůl: místa, rozdávání, časovače, lístek, záznam
  server/                  Starlette + WebSocket, protokol, limity, bezpečnostní hlavičky
  web/                     klient (HTML, CSS, JS moduly, písmo Bitter pod OFL)
tests/                     pytest
deploy/                    Docker Compose + Caddy, nginx, systemd
```

## Licence

Proprietární software, všechna práva vyhrazena (viz [LICENSE](LICENSE)). Bez písemného svolení
autora není dovoleno kód používat, šířit ani provozovat. Písmo Bitter je pod SIL Open Font License
([marias/web/fonts/OFL-Bitter.txt](marias/web/fonts/OFL-Bitter.txt)).
