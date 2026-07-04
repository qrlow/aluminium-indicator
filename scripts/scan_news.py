#!/usr/bin/env python3
"""Scan aluminium market news and classify factor impact."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple


NEWS_ENDPOINT = "https://news.google.com/rss/search"
USER_AGENT = "AluminiumIndicator/0.1"


@dataclass(frozen=True)
class Factor:
    id: str
    label: str
    side: str
    horizon: str
    metrics: Tuple[str, ...]
    keywords: Tuple[str, ...]
    queries: Tuple[str, ...]


FACTOR_CATALOG: Tuple[Factor, ...] = (
    Factor(
        id="demand_macro_manufacturing",
        label="Manufacturing and industrial activity",
        side="demand",
        horizon="short",
        metrics=("manufacturing PMI", "industrial production", "factory orders"),
        keywords=(
            "manufacturing",
            "manufacturing pmi",
            "industrial production",
            "factory orders",
            "fabrication",
            "semis demand",
        ),
        queries=(
            '("aluminium" OR "aluminum") ("manufacturing" OR "PMI" OR "industrial production")',
        ),
    ),
    Factor(
        id="demand_construction_near_term",
        label="Construction activity already underway",
        side="demand",
        horizon="short",
        metrics=("construction output", "project starts", "completed floor space"),
        keywords=(
            "construction",
            "building",
            "real estate",
            "property",
            "infrastructure",
            "extrusion",
            "window frames",
        ),
        queries=(
            '("aluminium" OR "aluminum") ("construction" OR "building" OR "infrastructure")',
        ),
    ),
    Factor(
        id="demand_transport_near_term",
        label="Transport production schedules",
        side="demand",
        horizon="short",
        metrics=("auto production", "EV output", "aircraft deliveries"),
        keywords=(
            "auto production",
            "automotive",
            "vehicle production",
            "ev production",
            "aircraft deliveries",
            "transport",
            "lightweighting",
        ),
        queries=(
            '("aluminium" OR "aluminum") ("automotive" OR "auto production" OR "EV" OR "aircraft deliveries")',
        ),
    ),
    Factor(
        id="demand_packaging",
        label="Packaging and beverage cans",
        side="demand",
        horizon="short",
        metrics=("beverage can output", "packaging volumes", "consumer goods sales"),
        keywords=(
            "packaging",
            "beverage can",
            "beverage cans",
            "can sheet",
            "canned drinks",
            "food packaging",
        ),
        queries=(
            '("aluminium" OR "aluminum") ("packaging" OR "beverage cans" OR "can sheet")',
        ),
    ),
    Factor(
        id="demand_trade_restocking",
        label="Trade flows and restocking",
        side="demand",
        horizon="short",
        metrics=("export orders", "container throughput", "customer inventories"),
        keywords=(
            "export orders",
            "restocking",
            "destocking",
            "global trade",
            "container throughput",
            "orders",
            "premiums",
        ),
        queries=(
            '("aluminium" OR "aluminum") ("export orders" OR "restocking" OR "global trade" OR "premiums")',
        ),
    ),
    Factor(
        id="supply_smelter_operations",
        label="Smelter outages, restarts, and curtailments",
        side="supply",
        horizon="short",
        metrics=("primary production", "smelter utilization", "curtailed capacity"),
        keywords=(
            "smelter",
            "smelting",
            "curtailment",
            "curtailed",
            "outage",
            "restart",
            "primary aluminium",
            "primary aluminum",
            "production cut",
        ),
        queries=(
            '("aluminium" OR "aluminum") ("smelter" OR "curtailment" OR "outage" OR "restart")',
        ),
    ),
    Factor(
        id="supply_power_energy",
        label="Power availability and electricity cost",
        side="supply",
        horizon="short",
        metrics=("power prices", "grid restrictions", "hydropower levels"),
        keywords=(
            "power",
            "electricity",
            "energy prices",
            "hydropower",
            "power cuts",
            "grid",
            "coal prices",
            "gas prices",
        ),
        queries=(
            '("aluminium" OR "aluminum") ("power" OR "electricity" OR "energy prices" OR "hydropower") ("smelter" OR "production")',
        ),
    ),
    Factor(
        id="supply_alumina_bauxite_near_term",
        label="Alumina and bauxite disruptions",
        side="supply",
        horizon="short",
        metrics=("alumina price", "refinery output", "bauxite exports"),
        keywords=(
            "alumina",
            "bauxite",
            "refinery",
            "mine",
            "ore",
            "supply disruption",
            "export ban",
        ),
        queries=(
            '("alumina" OR "bauxite") ("refinery" OR "mine" OR "supply" OR "export")',
        ),
    ),
    Factor(
        id="supply_inventories",
        label="Exchange and visible inventories",
        side="supply",
        horizon="short",
        metrics=("LME stocks", "SHFE stocks", "bonded stocks"),
        keywords=(
            "lme stocks",
            "shfe stocks",
            "inventory",
            "inventories",
            "warehouse",
            "bonded stocks",
            "stockpiles",
        ),
        queries=(
            '("aluminium" OR "aluminum") ("LME stocks" OR "SHFE stocks" OR "inventory" OR "warehouse")',
        ),
    ),
    Factor(
        id="supply_trade_policy",
        label="Tariffs, sanctions, and export controls",
        side="supply",
        horizon="short",
        metrics=("tariff rates", "sanctioned volumes", "export quotas"),
        keywords=(
            "tariff",
            "tariffs",
            "sanctions",
            "export ban",
            "quota",
            "duties",
            "anti-dumping",
            "trade restrictions",
        ),
        queries=(
            '("aluminium" OR "aluminum") ("tariff" OR "sanctions" OR "export ban" OR "quota" OR "anti-dumping")',
        ),
    ),
    Factor(
        id="supply_scrap_secondary",
        label="Scrap and secondary aluminium flows",
        side="supply",
        horizon="short",
        metrics=("scrap collection", "secondary output", "recycling spreads"),
        keywords=(
            "scrap",
            "recycling",
            "secondary aluminium",
            "secondary aluminum",
            "recycled aluminium",
            "recycled aluminum",
        ),
        queries=(
            '("aluminium" OR "aluminum") ("scrap" OR "recycling" OR "secondary aluminium" OR "secondary aluminum")',
        ),
    ),
    Factor(
        id="demand_housing_infrastructure_pipeline",
        label="Housing, infrastructure, and urbanization pipeline",
        side="demand",
        horizon="long",
        metrics=("housing starts", "building permits", "infrastructure capex"),
        keywords=(
            "housing starts",
            "building permits",
            "infrastructure spending",
            "urbanization",
            "stimulus",
            "construction pipeline",
        ),
        queries=(
            '("aluminium" OR "aluminum") ("housing starts" OR "building permits" OR "infrastructure spending" OR "urbanization")',
        ),
    ),
    Factor(
        id="demand_grid_renewables",
        label="Grid expansion and renewables buildout",
        side="demand",
        horizon="long",
        metrics=("grid capex", "transmission additions", "solar and wind installations"),
        keywords=(
            "grid expansion",
            "transmission",
            "renewables",
            "solar",
            "wind",
            "power cable",
            "conductor",
            "energy transition",
        ),
        queries=(
            '("aluminium" OR "aluminum") ("grid expansion" OR "transmission" OR "solar" OR "wind" OR "renewables")',
        ),
    ),
    Factor(
        id="demand_transport_structural",
        label="EV, aircraft, and lightweighting trends",
        side="demand",
        horizon="long",
        metrics=("EV penetration", "aircraft order book", "lightweighting programs"),
        keywords=(
            "ev adoption",
            "electric vehicles",
            "aircraft orders",
            "order book",
            "lightweighting",
            "battery enclosure",
        ),
        queries=(
            '("aluminium" OR "aluminum") ("EV adoption" OR "electric vehicles" OR "aircraft orders" OR "lightweighting")',
        ),
    ),
    Factor(
        id="supply_new_capacity",
        label="New smelter capacity and permanent closures",
        side="supply",
        horizon="long",
        metrics=("announced capacity", "capex", "permanent closures"),
        keywords=(
            "new smelter",
            "capacity expansion",
            "permanent closure",
            "greenfield",
            "brownfield",
            "ramp up",
            "ramp-up",
            "new capacity",
        ),
        queries=(
            '("aluminium" OR "aluminum") ("new smelter" OR "capacity expansion" OR "permanent closure" OR "greenfield")',
        ),
    ),
    Factor(
        id="supply_alumina_bauxite_projects",
        label="Alumina refinery and bauxite mine projects",
        side="supply",
        horizon="long",
        metrics=("refinery capacity", "bauxite mine capacity", "ore grade"),
        keywords=(
            "alumina refinery",
            "bauxite mine",
            "mine development",
            "ore grade",
            "refinery expansion",
            "mining project",
        ),
        queries=(
            '("alumina refinery" OR "bauxite mine") ("expansion" OR "project" OR "capacity" OR "ore grade")',
        ),
    ),
    Factor(
        id="supply_carbon_policy_energy_mix",
        label="Carbon policy and long-term energy mix",
        side="supply",
        horizon="long",
        metrics=("carbon price", "emissions rules", "renewable power contracts"),
        keywords=(
            "carbon price",
            "carbon tax",
            "emissions",
            "decarbonisation",
            "decarbonization",
            "green aluminium",
            "renewable power",
            "power contract",
        ),
        queries=(
            '("aluminium" OR "aluminum") ("carbon price" OR "emissions" OR "green aluminium" OR "renewable power")',
        ),
    ),
    Factor(
        id="supply_recycling_capacity",
        label="Recycling infrastructure and scrap processing",
        side="supply",
        horizon="long",
        metrics=("recycling capacity", "scrap processing capacity", "collection rates"),
        keywords=(
            "recycling plant",
            "recycling capacity",
            "scrap processing",
            "closed loop",
            "collection rate",
            "secondary capacity",
        ),
        queries=(
            '("aluminium" OR "aluminum") ("recycling plant" OR "recycling capacity" OR "scrap processing" OR "closed loop")',
        ),
    ),
)


TIGHTENING_TERMS = (
    "outage",
    "shortage",
    "curtail",
    "curtailed",
    "cut output",
    "production cut",
    "strike",
    "ban",
    "sanction",
    "tariff",
    "disruption",
    "closure",
    "fire",
    "power cuts",
    "flood",
)

EASING_TERMS = (
    "restart",
    "ramp up",
    "ramp-up",
    "expansion",
    "new capacity",
    "higher output",
    "increased output",
    "record output",
    "surplus",
)

DEMAND_UP_TERMS = (
    "growth",
    "boost",
    "rises",
    "increase",
    "investment",
    "stimulus",
    "strong demand",
    "recovery",
    "orders rise",
)

DEMAND_DOWN_TERMS = (
    "slowdown",
    "weak demand",
    "slump",
    "falls",
    "decline",
    "cuts forecast",
    "recession",
    "destocking",
)


def clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def canonical_text(value: str) -> str:
    return clean_text(value).lower()


def phrase_count(text: str, phrase: str) -> int:
    escaped = re.escape(phrase.lower())
    return len(re.findall(r"(?<![a-z0-9])" + escaped + r"(?![a-z0-9])", text))


def parse_date(value: str) -> str:
    if not value:
        return ""
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def factor_to_json(factor: Factor) -> Dict[str, object]:
    return {
        "id": factor.id,
        "label": factor.label,
        "side": factor.side,
        "horizon": factor.horizon,
        "metrics": list(factor.metrics),
        "keywords": list(factor.keywords),
    }


def build_news_url(query: str) -> str:
    params = {
        "q": query,
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en",
    }
    return NEWS_ENDPOINT + "?" + urllib.parse.urlencode(params)


def fetch_url(url: str, timeout: int) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def parse_rss_items(xml_bytes: bytes, query_factor_ids: Sequence[str]) -> List[Dict[str, object]]:
    root = ET.fromstring(xml_bytes)
    items: List[Dict[str, object]] = []
    for item in root.findall(".//item"):
        title = clean_text(item.findtext("title", ""))
        link = clean_text(item.findtext("link", ""))
        description = clean_text(item.findtext("description", ""))
        published_at = parse_date(item.findtext("pubDate", ""))
        source = ""
        source_node = item.find("source")
        if source_node is not None:
            source = clean_text(source_node.text or "")
        if not title or not link:
            continue
        items.append(
            {
                "title": title,
                "url": link,
                "source": source,
                "description": description,
                "published_at": published_at,
                "query_factor_ids": list(query_factor_ids),
            }
        )
    return items


def matched_terms(text: str, factor: Factor) -> List[str]:
    return [term for term in factor.keywords if phrase_count(text, term)]


def classify_article(article: Dict[str, object]) -> Dict[str, object]:
    text = canonical_text(
        " ".join(
            str(article.get(key, ""))
            for key in ("title", "source", "description")
        )
    )
    query_factor_ids = set(article.get("query_factor_ids", []))
    factor_scores: List[Tuple[int, Factor, List[str]]] = []
    for factor in FACTOR_CATALOG:
        terms = matched_terms(text, factor)
        score = len(terms)
        if factor.id in query_factor_ids:
            score += 3
        if score >= 2:
            factor_scores.append((score, factor, terms))

    if not factor_scores:
        # Keep a weakly matched article visible under its query factor.
        for factor in FACTOR_CATALOG:
            if factor.id in query_factor_ids:
                factor_scores.append((1, factor, []))

    factor_scores.sort(key=lambda item: (-item[0], item[1].label))
    selected = factor_scores[:4]
    factors = [factor for _, factor, _ in selected]
    terms = sorted({term for _, _, matched in selected for term in matched})
    side = aggregate_dimension([factor.side for factor in factors])
    horizon = aggregate_dimension([factor.horizon for factor in factors])
    impact = estimate_impact(text, factors)
    return {
        **article,
        "side": side,
        "horizon": horizon,
        "impact": impact,
        "factor_ids": [factor.id for factor in factors],
        "factor_labels": [factor.label for factor in factors],
        "matched_terms": terms[:12],
        "market_read": build_market_read(side, horizon, impact, terms),
    }


def aggregate_dimension(values: Iterable[str]) -> str:
    values = list(values)
    if not values:
        return "monitor"
    unique = sorted(set(values))
    return unique[0] if len(unique) == 1 else "mixed"


def estimate_impact(text: str, factors: Sequence[Factor]) -> str:
    sides = {factor.side for factor in factors}
    supply_score = sum(phrase_count(text, term) for term in TIGHTENING_TERMS)
    easing_score = sum(phrase_count(text, term) for term in EASING_TERMS)
    demand_up_score = sum(phrase_count(text, term) for term in DEMAND_UP_TERMS)
    demand_down_score = sum(phrase_count(text, term) for term in DEMAND_DOWN_TERMS)

    if "supply" in sides and supply_score > easing_score:
        return "supply tightening"
    if "supply" in sides and easing_score > supply_score:
        return "supply easing"
    if "demand" in sides and demand_up_score > demand_down_score:
        return "demand upside"
    if "demand" in sides and demand_down_score > demand_up_score:
        return "demand downside"
    return "watch"


def build_market_read(side: str, horizon: str, impact: str, terms: Sequence[str]) -> str:
    side_label = {
        "demand": "demand",
        "supply": "supply",
        "mixed": "mixed demand/supply",
    }.get(side, "market")
    horizon_label = {
        "short": "0-3 month",
        "long": "3+ month",
        "mixed": "mixed horizon",
    }.get(horizon, "watchlist")
    reason = ", ".join(terms[:4]) if terms else "the search topic"
    return f"{impact}; {horizon_label} {side_label}; matched {reason}."


def dedupe_articles(articles: Sequence[Dict[str, object]]) -> List[Dict[str, object]]:
    by_key: Dict[str, Dict[str, object]] = {}
    for article in articles:
        key_text = canonical_text(str(article.get("title", "")))
        key = hashlib.sha1(key_text.encode("utf-8")).hexdigest()
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = dict(article)
            continue
        existing_ids = set(existing.get("query_factor_ids", []))
        existing_ids.update(article.get("query_factor_ids", []))
        existing["query_factor_ids"] = sorted(existing_ids)
        if not existing.get("source") and article.get("source"):
            existing["source"] = article["source"]
        if not existing.get("published_at") and article.get("published_at"):
            existing["published_at"] = article["published_at"]
    return list(by_key.values())


def summarize(articles: Sequence[Dict[str, object]]) -> Dict[str, object]:
    counts = {
        "total_articles": len(articles),
        "side": {},
        "horizon": {},
        "impact": {},
        "factors": {},
    }
    for article in articles:
        increment(counts["side"], str(article.get("side", "monitor")))
        increment(counts["horizon"], str(article.get("horizon", "monitor")))
        increment(counts["impact"], str(article.get("impact", "watch")))
        for factor_id in article.get("factor_ids", []):
            increment(counts["factors"], str(factor_id))
    return counts


def increment(mapping: Dict[str, int], key: str) -> None:
    mapping[key] = mapping.get(key, 0) + 1


def scan_news(max_per_query: int, lookback_days: int, timeout: int) -> Dict[str, object]:
    all_items: List[Dict[str, object]] = []
    query_log: List[Dict[str, object]] = []
    suffix = f" when:{lookback_days}d"

    for factor in FACTOR_CATALOG:
        for query in factor.queries:
            full_query = query + suffix
            url = build_news_url(full_query)
            status = "ok"
            error = ""
            count = 0
            try:
                xml_bytes = fetch_url(url, timeout=timeout)
                items = parse_rss_items(xml_bytes, [factor.id])[:max_per_query]
                all_items.extend(items)
                count = len(items)
            except Exception as exc:  # pragma: no cover - network defense
                status = "error"
                error = str(exc)
            query_log.append(
                {
                    "factor_id": factor.id,
                    "query": full_query,
                    "status": status,
                    "items": count,
                    "error": error,
                }
            )
            time.sleep(0.2)

    deduped = dedupe_articles(all_items)
    classified = [classify_article(article) for article in deduped]
    classified.sort(key=lambda article: str(article.get("published_at", "")), reverse=True)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "name": "Google News RSS",
            "lookback_days": lookback_days,
            "max_per_query": max_per_query,
        },
        "summary": summarize(classified),
        "factors": [factor_to_json(factor) for factor in FACTOR_CATALOG],
        "queries": query_log,
        "articles": classified,
    }


def write_json(path: Path, payload: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan aluminium market news.")
    parser.add_argument("--output", default="docs/data/latest.json")
    parser.add_argument("--max-per-query", type=int, default=8)
    parser.add_argument("--lookback-days", type=int, default=14)
    parser.add_argument("--timeout", type=int, default=20)
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)
    if args.max_per_query < 1:
        raise SystemExit("--max-per-query must be at least 1")
    if args.lookback_days < 1:
        raise SystemExit("--lookback-days must be at least 1")
    payload = scan_news(
        max_per_query=args.max_per_query,
        lookback_days=args.lookback_days,
        timeout=args.timeout,
    )
    write_json(Path(args.output), payload)
    print(
        "Wrote "
        f"{len(payload['articles'])} classified articles to {args.output}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
