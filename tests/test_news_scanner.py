import unittest

from scripts.scan_news import classify_article, parse_rss_items


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


if __name__ == "__main__":
    unittest.main()
