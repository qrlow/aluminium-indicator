# Aluminium Demand/Supply Monitor

Aluminium Demand/Supply Monitor is a static dashboard and news scanner for the aluminium market.
It scans public news for signals tied to measurable demand and supply factors, filters low-information hits, consolidates similar articles, and writes a GitHub Pages-ready dashboard.

## What It Tracks

- Short-term demand: manufacturing, construction already underway, transport schedules, packaging, trade flows, and restocking.
- Short-term supply: smelter operations, power costs, alumina and bauxite disruptions, inventories, regional premiums, trade policy, and scrap flows.
- Long-term demand: housing and infrastructure pipelines, grid and renewables buildout, EVs, aircraft, and lightweighting.
- Long-term supply: new aluminium capacity, alumina and bauxite projects, carbon policy, energy mix, and recycling capacity.

## Run A Scan

```sh
python3 scripts/scan_news.py
```

The scanner writes the latest grouped factor signals to `docs/data/latest.json`.
It uses Google News RSS and does not need an API key.

## Preview The Dashboard

```sh
python3 -m http.server 8000
```

Open `http://localhost:8000/docs/`.

## Test

```sh
python3 -m unittest discover -s tests
```

## GitHub Pages

Publish the `docs/` directory with GitHub Pages.
The dashboard reads `docs/data/latest.json`, so every scan refreshes the visible data.

## Refresh Workflow

`.github/workflows/scan.yml` can be run manually with `workflow_dispatch`.
The daily cron is included as a commented block and can be enabled when daily refresh is wanted.

## License

[MIT](LICENSE)
