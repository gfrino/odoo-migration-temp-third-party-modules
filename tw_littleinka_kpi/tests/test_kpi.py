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

        # The filter takes several sedi: the comparison «Per sede» shows the chosen ones only.
        other = self.env["tw.littleinka.kpi.sede"].create({"name": "Seconda sede"})
        third = self.env["tw.littleinka.kpi.sede"].create({"name": "Terza sede"})
        day = {"period": "custom", "date_from": "2026-11-12", "date_to": "2026-11-12"}
        both = dashboard.get_data(dict(day, sede_ids=[self.sede.id, other.id]))
        self.assertEqual(both["sede_ids"], sorted([self.sede.id, other.id]))
        self.assertAlmostEqual(both["totals"]["amount_online"], 20.0)
        self.assertEqual({row["id"] for row in both["by_sede"]}, {self.sede.id, other.id})
        self.assertAlmostEqual(dashboard.get_data(dict(day, sede_ids=[other.id, third.id]))["totals"]["amount_online"], 0.0)
        self.assertEqual(dashboard.get_data(dict(day, sede_ids=[self.sede.id]))["by_sede"], [])
        self.assertEqual(dashboard.get_data(dict(day, sede_ids=["x", None]))["sede_ids"], [])
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

    def test_additions_and_fallback(self):
        categories = self.env["tw.littleinka.kpi.category"]
        poke = self.env.ref("tw_littleinka_kpi.family_poke")
        accessories = self.env.ref("tw_littleinka_kpi.family_accessories")
        self.assertTrue(accessories.is_fallback)

        # One poké with an extra topping is one piece; a category nobody knows goes to «Accessori».
        order = _order(201, 30.0)
        order["lines"] += [
            {"product_id": 11, "variation_id": 0, "sku": "", "name": "Topping in più", "category": "Poké Extra",
             "quantity": 3, "total": "1.50", "total_tax": "0.00"},
            {"product_id": 12, "variation_id": 0, "sku": "", "name": "Cosa nuova", "category": "Categoria mai vista",
             "quantity": 1, "total": "2.00", "total_tax": "0.00"},
        ]
        self.assertEqual(self._post("orders", {"orders": [order]}).status_code, 200)
        extra = categories.search([("key", "=", "poke extra")])
        self.assertEqual(extra.family_id, poke)
        self.assertFalse(extra.count_pieces)
        self.assertEqual(categories.search([("key", "=", "categoria mai vista")]).family_id, accessories)
        self.assertFalse(categories.search_count([("family_id", "=", False)]))

        params = {"period": "custom", "date_from": "2026-11-12", "date_to": "2026-11-12", "sede_id": self.sede.id}
        dashboard = self.env["tw.littleinka.kpi.dashboard"]
        families = {f["id"]: f for f in dashboard.get_data(params)["families"]}
        self.assertEqual(families[poke.id]["qty_online"], 2)
        self.assertEqual(families[accessories.id]["qty_online"], 1)
        self.assertNotIn(False, families)
        detail = dashboard.get_family_detail(params, poke.id)
        self.assertEqual([p["name"] for p in detail["products"]], ["Test bowl"])
        self.assertEqual([(e["name"], e["qty_online"]) for e in detail["extras"]], [("Topping in più", 3)])

    def test_pos_categories_and_product_rules(self):
        categories = self.env["tw.littleinka.kpi.category"]
        poke = self.env.ref("tw_littleinka_kpi.family_poke")
        accessories = self.env.ref("tw_littleinka_kpi.family_accessories")
        parent = self.env["pos.category"].create({"name": "Crea la tua Poke test"})
        self.env["pos.category"].create({"name": "Taglia XXL test", "parent_id": parent.id})
        extras = self.env["pos.category"].create({"name": "Extras test"})
        products = self.env["product.template"].create([
            {"name": "Topping Extra test", "available_in_pos": True, "pos_categ_ids": [(6, 0, extras.ids)]},
            {"name": "Sacchetti piccoli test", "available_in_pos": True, "pos_categ_ids": [(6, 0, extras.ids)]},
        ])
        categories._refresh_pos()
        # The size takes the family of its parent category; the additions category does not count pieces.
        self.assertEqual(categories.search([("key", "=", "taglia xxl test")]).family_id, poke)
        extras_category = categories.search([("key", "=", "extras test")])
        self.assertFalse(extras_category.count_pieces)
        extras_category.family_id = poke
        categories._refresh_pos()
        rules = self.env["tw.littleinka.kpi.product"].search([("product_tmpl_id", "in", products.ids)])
        self.assertEqual(rules.product_tmpl_id.name, "Sacchetti piccoli test")
        self.assertEqual(rules.family_id, accessories)
        with self.assertRaises(Exception):
            poke.is_fallback = True

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
