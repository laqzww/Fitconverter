# Route Amenities Demo

Et fuldt containeriseret MVP, der demonstrerer hele kæden fra rute ➜ buffer ➜ faciliteter (POI) ➜ filtrering ➜ GPX-eksport. Projektet leverer en FastAPI-backend med PostGIS, en Redis-cache med RQ-jobkø og en MapLibre/React-frontend, så alt virker offline med indbyggede demo-data.

## Arkitektur

- **PostgreSQL 16 + PostGIS** (`db`): sandhedskilde for ruter og faciliteter.
- **Redis 7** (`redis`): cache til søgninger/MVT-tiles og backend for RQ-jobkø.
- **FastAPI** (`api`): leverer JSON-endpoints, MVT-tiles og GPX-eksport.
- **RQ worker** (`worker`): læser køen `gpx`, genererer GPX-filer og gemmer download-links i Redis.
- **Vite + React + MapLibre** (`frontend`): kort-GUI der loader vektor-tiles, håndterer filtre og kalder søgning/eksport.

Mappen `/app/backend/out` (volumen) deles mellem `api` og `worker`, så eksporterede GPX-filer kan hentes via `/files/{filnavn}`.

## Hurtig start

```bash
git clone <repo>
cp .env.example .env  # hvis du kører lokalt
docker compose up --build
# initér databasen med demo-data
docker compose exec db psql -U postgres -d gis -f /docker-entrypoint-initdb.d/01_schema.sql
docker compose exec db psql -U postgres -d gis -f /docker-entrypoint-initdb.d/02_seed_demo.sql
# frontend: http://localhost:5173
# api: http://localhost:8000
```

Efter seed vil frontend automatisk vise demo-ruten omkring København og 20 POIs. MapLibre styler kun de lokale amenities, så alt fungerer uden internet.

### Smoke-test (obligatorisk)

```bash
# kør efter at alle services er startet
docker compose exec api python smoke_tests.py
```

Scriptet verificerer hele flowet:
1. `GET /healthz`
2. `POST /routes` med en test-GeoJSON-linje
3. `GET /search` og måler cache-hit (< 500 ms)
4. `POST /export/gpx` ➜ polling af `/export/status/{job_id}` ➜ henter den genererede fil
5. `GET /mvt/amenities/14/8801/5371` og sikrer at tile indeholder data

### API-overblik

| Endpoint | Metode | Beskrivelse |
| --- | --- | --- |
| `/healthz` | GET | Simpelt sundhedstjek for PostGIS + Redis |
| `/routes` | POST | Gemmer en LineString-rute (GeoJSON body eller multipart med `gpx_file`). Returnerer `route_id`. |
| `/search` | GET | Finder POIs omkring en rute. Parametre: `route_id`, `radius_m`, `filters` (JSON eller komma-separeret). Resultatet cachelagres i Redis i 90 sekunder. |
| `/export/gpx` | POST | Opretter et RQ-job (`gpx`-køen). Returnerer `job_id`. |
| `/export/status/{job_id}` | GET | Rapporterer jobstatus + download-URL (`/files/{job_id}.gpx`) når den er klar. |
| `/mvt/amenities/{z}/{x}/{y}` | GET | Genererer Mapbox Vector Tiles fra PostGIS (cache 600 sek.). |
| `/files/{fil}` | GET | Statisk GPX-download mappe. |

### Frontend-workflow

1. Upload en GPX-fil eller brug den seedede rute.
2. Justér radius (meter) og (de)aktiver kategori-filtre. MapLibre lag anvender klient-side `match`-filtre for hurtigt UI.
3. Tryk **“Find i buffer”** for at køre en PostGIS `ST_Buffer`/`ST_DWithin`-forespørgsel.
4. Tryk **“Eksportér GPX”** for at oprette et baggrundsjob. Når status = `finished`, bliver linket aktivt.

### PG Tileserv (valgfrit)

Backend eksponerer `/mvt/amenities/...`. Hvis du ønsker at teste med `pg_tileserv`, kan du tilføje en ekstra service i `docker-compose.yml` og pege MapLibre-sourcen på `http://tiles:7800/public.amenities/{z}/{x}/{y}.mvt`. README’en behøver ikke opdateres; MapLibre-koden accepterer nemt et andet tile-URL.

### Valgfri OSM/Overpass-import

Kør `python tools/osm_seed.py --bbox <south> <west> <north> <east> --categories toilet water cafe` for at hente faciliteter via Overpass. Outputtet er `INSERT`-statements, der kan kopieres ind i `sql/02_seed_demo.sql`. Scriptet er kun tænkt som convenience og kræver internet.

## Udvikling

- Backend kører FastAPI via `uvicorn` (hot reload ikke aktiveret i Docker). Lokalt kan du køre `pip install -r requirements.txt && uvicorn main:app --reload` inde fra `app/backend`.
- Frontend bruger Vite. Lokalt: `npm install && npm run dev` i `app/frontend`.
- Miljøvariabler (se `.env.example`):
  - `POSTGRES_*` til database, `REDIS_URL`, `API_PORT`, `FRONTEND_PORT`, `VITE_API_URL` (frontend → backend), `GPX_OUTPUT_DIR` (sat via Compose).

## Troubleshooting

| Problem | Løsning |
| --- | --- |
| `cached search slower than 500 ms` i smoke-test | Kontroller at Redis kører, og at `REDIS_URL` peger korrekt. Test `redis-cli PING` i `redis`-containeren. |
| `Export job failed` | Se logs fra `worker`-containeren. Sikr at `app/backend/out` er mountet til både `api` og `worker`. |
| CORS-fejl i browseren | Tjek at du bruger `http://localhost:5173` og at backend kører på `http://localhost:8000`. FastAPI er konfigureret til `allow_origins=['*']` under udvikling. |
| Manglende PostGIS-funktioner | Sørg for at køre `01_schema.sql` før `02_seed_demo.sql`. |
| Overpass-script fejler | Overpass kan throttles; prøv igen senere eller brug en mindre bounding box. |

## Testdata

`sql/02_seed_demo.sql` lægger en rute (`Indre By Demo Loop`) og 20 amenities i København (toilet, vandpost, café, udsigtspunkt, bænk). Dataene holder projektet offline-kompatibelt.

---

Bygget af senior full-stack + DevEx-assistenten. God fornøjelse!
