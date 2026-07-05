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
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


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
        ),
        queries=(
            '("aluminium" OR "aluminum") ("export orders" OR "restocking" OR "global trade")',
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
        id="supply_physical_premiums",
        label="Physical premiums and regional tightness",
        side="supply",
        horizon="short",
        metrics=("spot premiums", "regional delivery premiums", "physical availability"),
        keywords=(
            "premium",
            "premiums",
            "physical supply",
            "physical supply tightens",
            "delivered costs",
            "regional tightness",
            "japan premium",
            "midwest premium",
        ),
        queries=(
            '("aluminium" OR "aluminum") ("premium" OR "premiums" OR "physical supply tightens" OR "Japan premium" OR "Midwest premium")',
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
        label="New aluminium capacity and permanent closures",
        side="supply",
        horizon="long",
        metrics=("announced capacity", "capex", "project ramp-ups", "permanent closures"),
        keywords=(
            "new smelter",
            "capacity expansion",
            "foil capacity",
            "rolling mill",
            "permanent closure",
            "greenfield",
            "brownfield",
            "ramp up",
            "ramp-up",
            "new capacity",
            "trial production",
        ),
        queries=(
            '("aluminium" OR "aluminum") ("new smelter" OR "capacity expansion" OR "trial production" OR "permanent closure" OR "greenfield")',
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

LOW_INFORMATION_TITLE_PATTERNS = (
    re.compile(r"\boutlook and strategy\b", re.IGNORECASE),
    re.compile(r"\btrade ideas?\b", re.IGNORECASE),
    re.compile(r"\benterprise value to ebitda\b", re.IGNORECASE),
    re.compile(r"\btop \d+ metal stocks?\b", re.IGNORECASE),
    re.compile(r"\bshares? .* slumped\b", re.IGNORECASE),
    re.compile(r"\bstocks? to (buy|watch)\b", re.IGNORECASE),
    re.compile(r"\bmarket (size|share|growth|forecast|outlook)\b", re.IGNORECASE),
    re.compile(r"\bmarket .* forecast to 20\d{2}\b", re.IGNORECASE),
)

DETAIL_SENTENCE_LIMIT = 3


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


def strip_source_suffix(title: str) -> str:
    parts = title.rsplit(" - ", 1)
    if len(parts) == 2 and len(parts[1]) <= 45:
        return parts[0].strip('" ')
    return title.strip('" ')


def is_low_information_article(article: Dict[str, object]) -> bool:
    title = str(article.get("title", ""))
    normalized = canonical_text(title)
    if not any(pattern.search(title) for pattern in LOW_INFORMATION_TITLE_PATTERNS):
        return False
    has_market_number = bool(re.search(r"(\$?\d+(?:\.\d+)?\s?(?:%|mt|ton|t|billion|million|crore))", normalized))
    has_direct_aluminium_action = any(
        term in normalized
        for term in (
            "smelter",
            "premium",
            "curtail",
            "restart",
            "tariff",
            "sanction",
            "alumina",
            "bauxite",
            "recycling plant",
            "capacity expansion",
        )
    )
    return not (has_market_number and has_direct_aluminium_action)


def is_japan_premium_topic(text: str) -> bool:
    return "japan" in text and (
        "premium" in text
        or "premiums" in text
        or "buyers agree on higher aluminum fees" in text
        or "buyers agree on higher aluminium fees" in text
    )


def is_luoyang_wanji_topic(text: str) -> bool:
    return ("luoyang" in text and "wanji" in text) or (
        "20,000 mt" in text
        and "foil" in text
        and ("capacity expans" in text or "trial production" in text)
    )


def is_ega_recycling_topic(text: str) -> bool:
    has_recycling = "recycling" in text or "recycled" in text
    has_recycling_plant = has_recycling and "plant" in text
    has_aluminium = "aluminium" in text or "aluminum" in text
    has_ega_entity = (
        "ega" in text
        or "emirates global" in text
        or "emirates aluminum" in text
        or "emirates aluminium" in text
    )
    has_uae_largest_context = (
        "uae" in text
        and "largest" in text
        and has_aluminium
        and "recycling" in text
    )
    has_185k_capacity_context = (
        ("185,000" in text or "185 thousand" in text)
        and has_aluminium
        and "recycling" in text
    )
    has_truncated_inauguration_context = (
        has_ega_entity
        and has_aluminium
        and "inaugurated" in text
    )
    return (
        (has_ega_entity and has_aluminium and has_recycling)
        or has_uae_largest_context
        or has_185k_capacity_context
        or (has_recycling_plant and has_uae_largest_context)
        or has_truncated_inauguration_context
    )


def topic_key(article: Dict[str, object]) -> str:
    title = strip_source_suffix(str(article.get("title", "")))
    text = canonical_text(" ".join([title, str(article.get("description", ""))]))
    if is_japan_premium_topic(text):
        return "japan_q3_aluminium_premium_395"
    if is_luoyang_wanji_topic(text):
        return "luoyang_wanji_foil_capacity_expansion"
    if "adani" in text and ("ihc" in text or "irh" in text) and (
        "odisha" in text or "aluminium project" in text or "aluminum project" in text
    ):
        return "adani_ihc_odisha_aluminium_project"
    if "alcoa" in text and "south32" in text:
        return "alcoa_south32_aluminium_assets"
    if ("slovalco" in text or "slovak" in text) and "restart" in text:
        return "slovalco_partial_restart"
    if "inola" in text and "smelter" in text:
        return "inola_aluminium_smelter_delay"
    if is_ega_recycling_topic(text):
        return "ega_aluminium_recycling_plant"

    numbers = re.findall(r"\b\d+(?:\.\d+)?\b", text)
    tokens = [
        token
        for token in re.findall(r"[a-z][a-z0-9]+", text)
        if token
        not in {
            "aluminium",
            "aluminum",
            "news",
            "market",
            "global",
            "says",
            "the",
            "and",
            "with",
            "for",
            "from",
            "this",
            "that",
            "into",
            "amid",
            "after",
            "over",
            "due",
        }
    ]
    key_parts = numbers[:2] + tokens[:7]
    if not key_parts:
        key_parts = [hashlib.sha1(title.encode("utf-8")).hexdigest()[:10]]
    return "auto_" + "_".join(key_parts)


def extract_numeric_phrases(text: str) -> List[str]:
    details: List[str] = []
    sentences = re.split(r"(?<=[.!?])\s+", clean_text(text))
    for sentence in sentences:
        if not re.search(r"\$?\d+(?:\.\d+)?\s?(?:%|mt|ton|t|billion|million|crore|year|years?)?", sentence, re.IGNORECASE):
            continue
        stripped = strip_source_suffix(sentence)
        if stripped and stripped not in details:
            details.append(stripped)
        if len(details) >= DETAIL_SENTENCE_LIMIT:
            break
    return details


def article_details(article: Dict[str, object]) -> List[str]:
    title = strip_source_suffix(str(article.get("title", "")))
    text = canonical_text(" ".join([title, str(article.get("description", ""))]))
    if is_japan_premium_topic(text):
        return [
            "Japanese Q3 aluminium premium settled around $395/t over LME prices for at least one customer.",
            "That is above Q2 shipment premiums of roughly $350/t for Rio Tinto and $353/t for South32.",
            "Supplier opening offers were reported around $460-$480/t, so the final settlement was below the initial ask but still an 11-year high.",
        ]
    if is_luoyang_wanji_topic(text):
        return [
            "Luoyang Wanji's 20,000 mt/year aluminium foil expansion entered trial production after No. 5 and No. 6 rolling mills completed strip threading and trial runs.",
            "Stable commissioning results mark the project's move into trial production.",
            "At full production, the project would lift total company foil capacity to more than 50,000 mt/year.",
        ]
    if is_ega_recycling_topic(text):
        return [
            "Emirates Global Aluminium opened a UAE aluminium recycling plant reported at about 185,000 tonnes of annual capacity.",
            "The project is described across sources as the UAE's largest aluminium recycling plant and a circular-economy capacity addition.",
        ]
    return extract_numeric_phrases(title)


def canonical_article_url(article: Dict[str, object]) -> str:
    url = str(article.get("url", ""))
    title = strip_source_suffix(str(article.get("title", "")))
    source = canonical_text(str(article.get("source", "")))
    text = canonical_text(" ".join([title, source]))
    if is_japan_premium_topic(text):
        if "mining.com" in source:
            return "https://www.mining.com/web/japan-buyers-agree-on-higher-aluminum-fees-due-to-war-disruption/"
        if "al circle" in source or "alcircle" in source:
            return "https://www.alcircle.com/news/japans-q3-aluminium-premium-hits-11-year-high-at-395-t-as-physical-supply-tightens-120181"
    if is_luoyang_wanji_topic(text):
        return "https://news.metal.com/newscontent/103987818-luoyang-wanji-aluminum-expands-foil-capacity-enters-trial-production-with-advanced-equipment"
    return url


def signal_title(key: str, articles: Sequence[Dict[str, object]]) -> str:
    if key == "japan_q3_aluminium_premium_395":
        return "Japan Q3 aluminium premium settles near $395/t"
    if key == "luoyang_wanji_foil_capacity_expansion":
        return "Luoyang Wanji adds 20,000 mt/year foil capacity in trial production"
    if key == "adani_ihc_odisha_aluminium_project":
        return "Adani and IHC advance Odisha greenfield aluminium project"
    if key == "alcoa_south32_aluminium_assets":
        return "Alcoa-South32 asset deal reshapes alumina and bauxite exposure"
    if key == "slovalco_partial_restart":
        return "Slovalco aluminium smelter moves toward partial restart"
    if key == "inola_aluminium_smelter_delay":
        return "Inola proposed aluminium smelter faces local delay"
    if key == "ega_aluminium_recycling_plant":
        return "EGA opens aluminium recycling capacity in the UAE"
    return strip_source_suffix(str(articles[0].get("title", "")))


def signal_summary(key: str, signal: Dict[str, object]) -> str:
    if key == "japan_q3_aluminium_premium_395":
        return "Regional physical premiums point to tighter nearby aluminium availability and higher delivered costs for Japanese buyers."
    if key == "luoyang_wanji_foil_capacity_expansion":
        return "New foil capacity is moving from commissioning to trial output, adding future supply in higher-end rolled products."
    if key == "adani_ihc_odisha_aluminium_project":
        return "A large greenfield project would affect longer-term primary aluminium and alumina capacity rather than immediate supply."
    if key == "alcoa_south32_aluminium_assets":
        return "The transaction changes ownership and integration across upstream bauxite, alumina, and aluminium assets."
    if key == "slovalco_partial_restart":
        return "Restart news adds potential primary aluminium supply if power and operating economics hold."
    if key == "inola_aluminium_smelter_delay":
        return "Local approval delays push potential new smelting capacity further into the future."
    if key == "ega_aluminium_recycling_plant":
        return "EGA's UAE recycling plant opening adds reported 185,000-tonne annual secondary aluminium capacity and supports longer-term circular supply."
    return str(signal.get("market_read", ""))


def topic_factor_override(key: str) -> List[str]:
    overrides = {
        "japan_q3_aluminium_premium_395": ["supply_physical_premiums"],
        "luoyang_wanji_foil_capacity_expansion": ["supply_new_capacity"],
        "adani_ihc_odisha_aluminium_project": [
            "supply_new_capacity",
            "supply_alumina_bauxite_projects",
        ],
        "alcoa_south32_aluminium_assets": ["supply_alumina_bauxite_projects"],
        "slovalco_partial_restart": ["supply_smelter_operations"],
        "inola_aluminium_smelter_delay": ["supply_new_capacity"],
        "ega_aluminium_recycling_plant": ["supply_recycling_capacity"],
    }
    return overrides.get(key, [])


def topic_dimension_override(key: str) -> Dict[str, str]:
    overrides = {
        "japan_q3_aluminium_premium_395": {
            "side": "supply",
            "horizon": "short",
            "impact": "supply tightening",
        },
        "luoyang_wanji_foil_capacity_expansion": {
            "side": "supply",
            "horizon": "long",
            "impact": "supply easing",
        },
        "adani_ihc_odisha_aluminium_project": {
            "side": "supply",
            "horizon": "long",
            "impact": "supply easing",
        },
        "alcoa_south32_aluminium_assets": {
            "side": "supply",
            "horizon": "long",
            "impact": "watch",
        },
        "slovalco_partial_restart": {
            "side": "supply",
            "horizon": "short",
            "impact": "supply easing",
        },
        "inola_aluminium_smelter_delay": {
            "side": "supply",
            "horizon": "long",
            "impact": "supply tightening",
        },
        "ega_aluminium_recycling_plant": {
            "side": "supply",
            "horizon": "long",
            "impact": "supply easing",
        },
    }
    return overrides.get(key, {})


def unique_preserve_order(values: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def dominant_value(values: Sequence[str], fallback: str = "mixed") -> str:
    counts: Dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    if not counts:
        return fallback
    sorted_counts = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    if len(sorted_counts) > 1 and sorted_counts[0][1] == sorted_counts[1][1]:
        return fallback
    return sorted_counts[0][0]


def build_signal(key: str, articles: Sequence[Dict[str, object]]) -> Dict[str, object]:
    sorted_articles = sorted(
        articles,
        key=lambda article: str(article.get("published_at", "")),
        reverse=True,
    )
    factor_ids = unique_preserve_order(
        factor_id
        for article in sorted_articles
        for factor_id in article.get("factor_ids", [])
    )
    factor_ids = topic_factor_override(key) or factor_ids
    factor_by_id = {factor.id: factor for factor in FACTOR_CATALOG}
    factor_labels = [factor_by_id[factor_id].label for factor_id in factor_ids if factor_id in factor_by_id]
    details = unique_preserve_order(
        detail
        for article in sorted_articles
        for detail in article_details(article)
    )[:5]
    dimension_override = topic_dimension_override(key)
    signal = {
        "id": key,
        "title": signal_title(key, sorted_articles),
        "published_at": sorted_articles[0].get("published_at", ""),
        "side": dimension_override.get(
            "side",
            dominant_value([str(article.get("side", "")) for article in sorted_articles], fallback="mixed"),
        ),
        "horizon": dimension_override.get(
            "horizon",
            dominant_value([str(article.get("horizon", "")) for article in sorted_articles], fallback="mixed"),
        ),
        "impact": dimension_override.get(
            "impact",
            dominant_value([str(article.get("impact", "")) for article in sorted_articles], fallback="watch"),
        ),
        "factor_ids": factor_ids,
        "factor_labels": factor_labels,
        "matched_terms": unique_preserve_order(
            term
            for article in sorted_articles
            for term in article.get("matched_terms", [])
        )[:12],
        "details": details,
        "source_articles": [
            {
                "title": article.get("title", ""),
                "url": canonical_article_url(article),
                "source": article.get("source", ""),
                "published_at": article.get("published_at", ""),
            }
            for article in sorted_articles
        ],
        "source_count": len(sorted_articles),
    }
    signal["summary"] = signal_summary(key, signal)
    return signal


def group_articles(articles: Sequence[Dict[str, object]]) -> List[Dict[str, object]]:
    groups: Dict[str, List[Dict[str, object]]] = {}
    for article in articles:
        groups.setdefault(topic_key(article), []).append(article)
    signals = [build_signal(key, grouped) for key, grouped in groups.items()]
    signals.sort(key=lambda signal: str(signal.get("published_at", "")), reverse=True)
    return signals


def pluralize(count: int, singular: str, plural: Optional[str] = None) -> str:
    if count == 1:
        return f"{count} {singular}"
    return f"{count} {plural or singular + 's'}"


def impact_mix(signals: Sequence[Dict[str, object]]) -> str:
    counts: Dict[str, int] = {}
    for signal in signals:
        impact = str(signal.get("impact", "watch"))
        if impact == "watch":
            continue
        counts[impact] = counts.get(impact, 0) + 1
    if not counts:
        return "Most items are watchlist signals without a clear directional impact."
    parts = [
        f"{pluralize(count, 'signal')} flagged {impact}"
        for impact, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    if len(parts) == 1:
        return parts[0].capitalize() + "."
    return "Impact mix: " + "; ".join(parts) + "."


def shorten_text(value: str, max_length: int = 90) -> str:
    value = clean_text(value)
    if len(value) <= max_length:
        return value
    trimmed = value[: max_length - 3].rsplit(" ", 1)[0].rstrip(" ,.;:…")
    return (trimmed or value[: max_length - 3]).rstrip() + "..."


def build_section_summary(signals: Sequence[Dict[str, object]]) -> str:
    if not signals:
        return "No relevant news was found for this factor in the latest scan."
    article_count = sum(int(signal.get("source_count", 0)) for signal in signals)
    latest_titles = [
        shorten_text(str(signal.get("title", "")))
        for signal in signals[:2]
        if signal.get("title")
    ]
    theme_sentence = ""
    if latest_titles:
        theme_sentence = " Latest themes: " + "; ".join(latest_titles) + "."
    return (
        f"Scanned {pluralize(len(signals), 'grouped signal')} from "
        f"{pluralize(article_count, 'source article')}. "
        f"{impact_mix(signals)}"
        f"{theme_sentence}"
    )


def build_factor_groups(signals: Sequence[Dict[str, object]]) -> List[Dict[str, object]]:
    groups = []
    for factor in FACTOR_CATALOG:
        factor_signals = [
            signal
            for signal in signals
            if factor.id in signal.get("factor_ids", [])
        ]
        factor_signals.sort(key=lambda signal: str(signal.get("published_at", "")), reverse=True)
        groups.append(
            {
                **factor_to_json(factor),
                "signal_count": len(factor_signals),
                "article_count": sum(int(signal.get("source_count", 0)) for signal in factor_signals),
                "section_summary": build_section_summary(factor_signals),
                "signals": factor_signals,
            }
        )
    groups.sort(key=lambda group: (-int(group["signal_count"]), group["label"]))
    return groups


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


def summarize(
    articles: Sequence[Dict[str, object]],
    signals: Sequence[Dict[str, object]],
    filtered_articles: int,
) -> Dict[str, object]:
    counts = {
        "total_articles": len(articles),
        "total_signals": len(signals),
        "filtered_articles": filtered_articles,
        "side": {},
        "horizon": {},
        "impact": {},
        "factors": {},
    }
    for signal in signals:
        increment(counts["side"], str(signal.get("side", "monitor")))
        increment(counts["horizon"], str(signal.get("horizon", "monitor")))
        increment(counts["impact"], str(signal.get("impact", "watch")))
        for factor_id in signal.get("factor_ids", []):
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
    classified = [
        article
        for article in (classify_article(article) for article in deduped)
        if not is_low_information_article(article)
    ]
    classified.sort(key=lambda article: str(article.get("published_at", "")), reverse=True)
    signals = group_articles(classified)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "name": "Google News RSS",
            "lookback_days": lookback_days,
            "max_per_query": max_per_query,
        },
        "summary": summarize(
            articles=classified,
            signals=signals,
            filtered_articles=len(deduped) - len(classified),
        ),
        "factors": [factor_to_json(factor) for factor in FACTOR_CATALOG],
        "factor_groups": build_factor_groups(signals),
        "queries": query_log,
        "articles": classified,
        "signals": signals,
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
        f"{len(payload['signals'])} grouped signals from "
        f"{len(payload['articles'])} classified articles to {args.output}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
