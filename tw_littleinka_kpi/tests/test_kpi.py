import json

from odoo.tests import HttpCase, tagged


def _order(number, total, status="completed", category="01. Poké Bowl", qty=2, date="2026-11-12T11:15:00Z"):
    return {
        "id": number,
        "number": str(number),
        "status": status,
        "channel": "app",
        "fulfilment": "delivery",
        "date_created": date,
        "currency": "CHF",
        "total": f"{total:.2f}",
        "total_tax": "0.00",
        "shipping_total": "5.00",
        "discount_total": "0.00",
        "refunded": "0.00",
        "payment_method": "tw_datatrans_twint",
        "payment_method_title": "TWINT",
        "payment_group": "twint",
        "postcode": "6500",
        "city": "Test",
        "customer_ref": "a" * 64,
        "coupons": [],
        "lines": [
            {"product_id": 10, "variation_id": 0, "sku": "", "name": "Test bowl", "category": category,
             "quantity": qty, "total": f"{total - 5:.2f}", "total_tax": "0.00"},
        ],
    }


@tagged("post_install", "-at_install")
class TestLittleInkaKpi(HttpCase):
    def setUp(self):
        super().setUp()
        self.sede = self.env["tw.littleinka.kpi.sede"].create({"name": "Sede test"})
        action = self.sede.action_generate_key()
        self.key = self.env["tw.littleinka.kpi.key.wizard"].browse(action["res_id"]).key

    def _post(self, path, payload, key=None):
        return self.url_open(
            f"/tw_littleinka_kpi/v1/{path}",
            data=json.dumps(payload),
            headers={"Authorization": f"Bearer {key or self.key}", "Content-Type": "application/json"},
        )

    def test_key_is_hashed_and_checked(self):
        self.assertTrue(self.key.startswith("lik_"))
        self.assertNotEqual(self.sede.sudo().key_hash, self.key)
        self.assertEqual(self.sede.key_hint, "…" + self.key[-4:])
        response = self._post("ping", {"site": "https://test.example/"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["sede"], "Sede test")
        self.assertEqual(self.sede.website_url, "https://test.example/")
        self.assertEqual(self._post("ping", {}, key="lik_" + "x" * 40).status_code, 401)
        # «Fatto» forgets the plain key; the website keeps working with it.
        wizard = self.env["tw.littleinka.kpi.key.wizard"].search([("sede_id", "=", self.sede.id)], limit=1)
        wizard.action_done()
        self.assertFalse(wizard.key)
        self.assertEqual(self._post("ping", {}).status_code, 200)
        self.sede.action_revoke_key()
        self.assertEqual(self._post("ping", {}).status_code, 401)

    def test_orders_upsert_and_dashboard(self):
        response = self._post("orders", {"site": "https://test.example/", "orders": [_order(101, 30.0), _order(102, 20.0, status="cancelled")]})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["received"], 2)
        orders = self.env["tw.littleinka.kpi.order"].search([("sede_id", "=", self.sede.id)])
        self.assertEqual(len(orders), 2)
        counted = orders.filtered("is_counted")
        self.assertEqual(counted.external_id, 101)
        self.assertEqual(counted.channel, "app")
        self.assertEqual(counted.line_ids.category_key, "poke bowl")

        # There is no phone channel: an order typed by hand in WooCommerce counts as «Sito».
        by_hand = _order(103, 15.0)
        by_hand["channel"] = "phone"
        self._post("orders", {"orders": [by_hand]})
        self.assertEqual(self.env["tw.littleinka.kpi.order"].search([("external_id", "=", 103)]).channel, "web")
        self.env["tw.littleinka.kpi.order"].search([("external_id", "=", 103)]).unlink()

        # The same order again (refunded in part) updates it instead of creating a copy.
        changed = _order(101, 30.0)
        changed["refunded"] = "10.00"
        self._post("orders", {"orders": [changed]})
        self.assertEqual(self.env["tw.littleinka.kpi.order"].search_count([("sede_id", "=", self.sede.id)]), 2)
        self.assertAlmostEqual(counted.amount_net, 20.0)
        self.assertEqual(len(counted.line_ids), 1)

        # The category arrived with the order and went to «Poké» through its keywords.
        category = self.env["tw.littleinka.kpi.category"].search([("key", "=", "poke bowl")])
        self.assertEqual(category.family_id, self.env.ref("tw_littleinka_kpi.family_poke"))

        dashboard = self.env["tw.littleinka.kpi.dashboard"]
        data = dashboard.get_data({"period": "custom", "date_from": "2026-11-12", "date_to": "2026-11-12", "sede_id": self.sede.id})
        self.assertAlmostEqual(data["totals"]["amount_online"], 20.0)
        self.assertEqual([channel["key"] for channel in data["channels"]], ["web", "app", "pos"])
        self.assertEqual(data["totals"]["orders_online"], 1)
        poke = next(f for f in data["families"] if f["id"] == category.family_id.id)
        self.assertEqual(poke["qty_online"], 2)
        self.assertEqual(poke["qty_pos"], 0)
        detail = dashboard.get_family_detail(
            {"period": "custom", "date_from": "2026-11-12", "date_to": "2026-11-12", "sede_id": self.sede.id}, poke["id"]
        )
        self.assertEqual(detail["products"][0]["name"], "Test bowl")
        # The analysis views read the same data.
        self.assertEqual(self.env["tw.littleinka.kpi.report"].search_count([("sede_id", "=", self.sede.id)]), 1)

    def test_invalid_payloads(self):
        self.assertEqual(self._post("orders", {"orders": "nope"}).status_code, 400)
        self.assertEqual(self._post("orders", {"orders": [_order(1, 1.0)] * 101}).status_code, 413)
        response = self._post("orders", {"orders": [{"id": "x"}, _order(5, 9.0)]})
        self.assertEqual(response.json()["received"], 1)

    def test_pos_config_in_one_sede_only(self):
        config = self.env["pos.config"].create({"name": "Cassa test"})
        self.sede.pos_config_ids = config
        other = self.env["tw.littleinka.kpi.sede"].create({"name": "Altra sede"})
        with self.assertRaises(Exception):
            other.pos_config_ids = config
