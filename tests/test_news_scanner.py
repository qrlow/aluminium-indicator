import unittest

from scripts.scan_news import (
    build_factor_groups,
    classify_article,
    group_articles,
    is_low_information_article,
    parse_rss_items,
)


class NewsScannerTests(unittest.TestCase):
    def test_classifies_short_term_supply_tightening(self):
        article = {
            "title": "Power cuts force aluminium smelter curtailment",
            "description": "The outage reduces primary aluminium output.",
            "source": "Example Metals",
            "url": "https://example.com/supply",
            "published_at": "2026-07-01T00:00:00+00:00",
            "query_factor_ids": ["supply_power_energy"],
        }

        classified = classify_article(article)

        self.assertEqual(classified["side"], "supply")
        self.assertEqual(classified["horizon"], "short")
        self.assertEqual(classified["impact"], "supply tightening")
        self.assertIn("Power availability and electricity cost", classified["factor_labels"])

    def test_classifies_long_term_demand_upside(self):
        article = {
            "title": "Automakers increase electric vehicles investment",
            "description": "Lightweighting programs could boost aluminium demand.",
            "source": "Example Autos",
            "url": "https://example.com/demand",
            "published_at": "2026-07-01T00:00:00+00:00",
            "query_factor_ids": ["demand_transport_structural"],
        }

        classified = classify_article(article)

        self.assertEqual(classified["side"], "demand")
        self.assertEqual(classified["horizon"], "long")
        self.assertEqual(classified["impact"], "demand upside")
        self.assertIn("EV, aircraft, and lightweighting trends", classified["factor_labels"])

    def test_parses_google_news_rss_items(self):
        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <rss><channel><item>
          <title>Alumina refinery restarts - Source Name</title>
          <link>https://news.google.com/example</link>
          <pubDate>Wed, 01 Jul 2026 12:00:00 GMT</pubDate>
          <source url="https://example.com">Source Name</source>
          <description>&lt;a href=&quot;https://example.com&quot;&gt;Story&lt;/a&gt;</description>
        </item></channel></rss>"""

        items = parse_rss_items(xml, ["supply_alumina_bauxite_near_term"])

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["source"], "Source Name")
        self.assertEqual(items[0]["query_factor_ids"], ["supply_alumina_bauxite_near_term"])
        self.assertTrue(items[0]["published_at"].startswith("2026-07-01T12:00:00"))

    def test_filters_low_information_company_outlook(self):
        article = classify_article(
            {
                "title": "Vedanta outlook and strategy as investors weigh long-term growth - Ad-hoc-news.de",
                "description": "Generic company overview with no aluminium market signal.",
                "source": "Ad-hoc-news.de",
                "url": "https://example.com/vedanta",
                "published_at": "2026-07-01T00:00:00+00:00",
                "query_factor_ids": ["demand_housing_infrastructure_pipeline"],
            }
        )

        self.assertTrue(is_low_information_article(article))

    def test_groups_japan_premium_sources_with_details(self):
        articles = [
            classify_article(
                {
                    "title": "Japan buyers agree on higher aluminum fees Due to war disruption - Mining.com",
                    "description": "",
                    "source": "Mining.com",
                    "url": "https://www.mining.com/web/japan-buyers-agree-on-higher-aluminum-fees-due-to-war-disruption/",
                    "published_at": "2026-07-04T00:04:00+00:00",
                    "query_factor_ids": ["demand_trade_restocking"],
                }
            ),
            classify_article(
                {
                    "title": "Japan's Q3 aluminium premium hits 11-year high at $395/t as physical supply tightens - AL Circle",
                    "description": "",
                    "source": "AL Circle",
                    "url": "https://www.alcircle.com/news/japans-q3-aluminium-premium-hits-11-year-high-at-395-t-as-physical-supply-tightens-120181",
                    "published_at": "2026-07-03T00:00:00+00:00",
                    "query_factor_ids": ["demand_trade_restocking"],
                }
            ),
        ]

        signals = group_articles(articles)

        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]["source_count"], 2)
        self.assertEqual(signals[0]["side"], "supply")
        self.assertEqual(signals[0]["horizon"], "short")
        self.assertIn("Physical premiums and regional tightness", signals[0]["factor_labels"])
        self.assertIn("$395/t", " ".join(signals[0]["details"]))
        self.assertIn("$460-$480/t", " ".join(signals[0]["details"]))

    def test_enriches_luoyang_wanji_capacity_details(self):
        signal = group_articles(
            [
                classify_article(
                    {
                        "title": "On the morning of June 30, the 20,000 mt aluminum foil capacity expans - SMM Metal",
                        "description": "Luoyang Wanji Aluminum expands foil capacity and enters trial production.",
                        "source": "SMM Metal",
                        "url": "https://news.metal.com/newscontent/103987818-luoyang-wanji-aluminum-expands-foil-capacity-enters-trial-production-with-advanced-equipment",
                        "published_at": "2026-07-04T12:00:00+00:00",
                        "query_factor_ids": ["supply_new_capacity"],
                    }
                )
            ]
        )[0]

        detail_text = " ".join(signal["details"])
        self.assertIn("New aluminium capacity and permanent closures", signal["factor_labels"])
        self.assertIn("20,000 mt/year", detail_text)
        self.assertIn("50,000 mt/year", detail_text)

    def test_builds_section_summary_for_factor_group(self):
        signals = group_articles(
            [
                classify_article(
                    {
                        "title": "Japan buyers agree on higher aluminum fees Due to war disruption - Mining.com",
                        "description": "",
                        "source": "Mining.com",
                        "url": "https://www.mining.com/web/japan-buyers-agree-on-higher-aluminum-fees-due-to-war-disruption/",
                        "published_at": "2026-07-04T00:04:00+00:00",
                        "query_factor_ids": ["supply_physical_premiums"],
                    }
                )
            ]
        )

        group = next(
            group
            for group in build_factor_groups(signals)
            if group["id"] == "supply_physical_premiums"
        )

        self.assertIn("1 grouped signal", group["section_summary"])
        self.assertIn("1 source article", group["section_summary"])
        self.assertIn("Japan Q3 aluminium premium", group["section_summary"])

    def test_groups_ega_recycling_plant_title_variants(self):
        titles = [
            "Emirates Global Aluminum (EGA) has officially inaugurated its aluminum - SMM Metal",
            "UAE opens largest aluminium recycling plant to drive circular economy - middle-east-online.com",
            "Supports the circular economy. Emirates Aluminum launches a recycling plant with a capacity of 185 thousand tons annually - صوت الإمارات",
            "EGA opens aluminium recycling capacity in the UAE",
            "185,000 tonnes of change: EGA opens UAE’s largest aluminium recycling plant to power circular economy - Gulf Business",
        ]
        articles = [
            classify_article(
                {
                    "title": title,
                    "description": "",
                    "source": "Example Source",
                    "url": f"https://example.com/ega-{index}",
                    "published_at": f"2026-07-0{index + 1}T00:00:00+00:00",
                    "query_factor_ids": ["supply_recycling_capacity"],
                }
            )
            for index, title in enumerate(titles)
        ]

        signals = group_articles(articles)

        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]["id"], "ega_aluminium_recycling_plant")
        self.assertEqual(signals[0]["source_count"], len(titles))
        self.assertIn("185,000", " ".join(signals[0]["details"]))


if __name__ == "__main__":
    unittest.main()
