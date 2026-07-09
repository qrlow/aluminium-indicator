# Aluminium LME/SHFE Arb Monitor

Aluminium LME/SHFE Arb Monitor is a static dashboard and scanner for aluminium market signals.
It combines public market quotes, an import-parity calculator, source-linked coverage rows, and public news scans into a GitHub Pages-ready dashboard.

## What It Tracks

- LME aluminium proxy quotes from Sina Finance, SHFE aluminium front/active contracts, nearby SHFE calendar spreads, and USD/CNY plus USD/CNH.
- Indicative import parity using the working formula `SHFE - landed cost`, with editable premium, freight, duty, VAT, admin, and financing assumptions.
- Source/status rows for cash/3M, China spot and bonded premiums, regional physical premiums, freight, warehouse queues, warrants, taxes, funding, fees, and margin requirements.
- Short-term demand: manufacturing, construction already underway, transport schedules, packaging, trade flows, and restocking.
- Short-term supply: smelter operations, power costs, alumina and bauxite disruptions, inventories, regional premiums, trade policy, and scrap flows.
- Long-term demand: housing and infrastructure pipelines, grid and renewables buildout, EVs, aircraft, and lightweighting.
- Long-term supply: new aluminium capacity, alumina and bauxite projects, carbon policy, energy mix, and recycling capacity.

Some physical premiums, warehouse reports, broker fees, and margin add-ons are source-linked rather than scraped because they are exchange login flows, broker-specific, or vendor-restricted data. The dashboard shows those rows explicitly instead of filling them with stale or invented values.

## SMM Import-Arb Benchmark

SMM's Aluminum import arbitrage(Spot) page is a vendor benchmark for the spot import window, not the dashboard's own tradable futures backtest. SMM describes the calculation as:

```text
SHFE futures contract + SMM A00 aluminum spot premium
- (LME 3M + SWAP Fee + import premium)
  * SGX USD/CNH FX futures
  * (1 + VAT rate)
  * (1 + import tariff)
- charges
```

In that formula, `SWAP Fee` is the LME prompt-date spread adjustment in USD/t, shown on the SMM page as `Spread ($/T)`. It is the cost or credit for converting the LME 3M basis to the relevant import-pricing prompt; it is not a broker commission or FX swap fee.

## Run A Scan

```sh
python3 scripts/scan_news.py
```

The scanner writes market data and grouped factor signals to `docs/data/latest.json`.
It uses public endpoints and does not need an API key.

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

`.github/workflows/scan.yml` runs on weekday mornings UTC and can also be run manually with `workflow_dispatch`.

## License

[MIT](LICENSE)
