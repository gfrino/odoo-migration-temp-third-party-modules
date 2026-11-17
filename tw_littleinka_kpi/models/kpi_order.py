from datetime import datetime, timezone

from odoo import api, fields, models

from .kpi_family import normalize_name

CHANNELS = [("web", "Sito"), ("app", "App"), ("phone", "Telefono"), ("pos", "Cassa")]
FULFILMENTS = [("delivery", "Consegna"), ("pickup", "Ritiro"), ("in_store", "In sede")]
PAYMENT_GROUPS = [
    ("twint", "TWINT"),
    ("card", "Carta"),
    ("apple_pay", "Apple Pay"),
    ("google_pay", "Google Pay"),
    ("cash", "Contanti"),
    ("other", "Altro"),
    ("none", "Nessuno"),
]
# WooCommerce statuses whose amount counts as a sale (refunds are subtracted with «refunded»).
COUNTED_STATES = ("processing", "completed", "refunded")


def parse_datetime(value):
    """ISO date from WooCommerce (UTC, «Z») to a naive UTC datetime, or False."""
    if not value or not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def parse_date(value):
    try:
        return fields.Date.to_date(value) if value else False
    except (TypeError, ValueError):
        return False


def money(value):
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def text(value, size=255):
    return str(value or "").strip()[:size]


class LittleInkaKpiOrder(models.Model):
    _name = "tw.littleinka.kpi.order"
    _description = "Little Inka KPI: ordine online"
    _order = "date_order desc, id desc"
    _rec_name = "number"

    sede_id = fields.Many2one("tw.littleinka.kpi.sede", string="Sede", required=True, index=True, ondelete="cascade")
    company_id = fields.Many2one(related="sede_id.company_id", store=True, index=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    external_id = fields.Integer("ID WooCommerce", required=True, index=True)
    number = fields.Char("Ordine", required=True)
    state = fields.Char("Stato WooCommerce", index=True)
    is_counted = fields.Boolean("Conta nelle vendite", compute="_compute_is_counted", store=True, index=True)
    channel = fields.Selection(CHANNELS[:3], string="Canale", required=True, default="web", index=True)
    fulfilment = fields.Selection(FULFILMENTS[:2], string="Consegna o ritiro", index=True)
    date_order = fields.Datetime("Data", required=True, index=True)
    date_paid = fields.Datetime("Pagato il")
    date_completed = fields.Datetime("Completato il")
    service_date = fields.Date("Giorno di consegna/ritiro")
    service_time = fields.Char("Fascia oraria")
    amount_total = fields.Monetary("Totale")
    amount_tax = fields.Monetary("IVA")
    amount_shipping = fields.Monetary("Consegna")
    amount_discount = fields.Monetary("Sconti")
    amount_refunded = fields.Monetary("Rimborsato")
    amount_net = fields.Monetary("Netto", compute="_compute_is_counted", store=True, help="Totale meno rimborsi.")
    payment_method = fields.Char("Codice pagamento")
    payment_method_title = fields.Char("Pagamento")
    payment_group = fields.Selection(PAYMENT_GROUPS, string="Metodo di pagamento", index=True)
    postcode = fields.Char("CAP", index=True)
    city = fields.Char("Località")
    customer_ref = fields.Char("Cliente (codice anonimo)", index=True)
    coupons = fields.Char("Codici sconto")
    line_ids = fields.One2many("tw.littleinka.kpi.order.line", "order_id", string="Righe")
    item_count = fields.Float("Pezzi", compute="_compute_item_count", store=True)

    _sede_external_uniq = models.Constraint("unique(sede_id, external_id)", "Questo ordine della sede esiste già.")

    @api.depends("state", "amount_total", "amount_refunded")
    def _compute_is_counted(self):
        for order in self:
            order.is_counted = order.state in COUNTED_STATES and order.amount_total > order.amount_refunded
            order.amount_net = order.amount_total - order.amount_refunded

    @api.depends("line_ids.quantity")
    def _compute_item_count(self):
        for order in self:
            order.item_count = sum(order.line_ids.mapped("quantity"))

    @api.model
    def _values_from_payload(self, sede, data):
        lines = []
        for line in data.get("lines") or []:
            if not isinstance(line, dict):
                continue
            lines.append({
                "product_ref": text(line.get("product_id"), 32),
                "variation_ref": text(line.get("variation_id"), 32),
                "sku": text(line.get("sku"), 64),
                "name": text(line.get("name")) or "?",
                "category_name": text(line.get("category")),
                "quantity": money(line.get("quantity")),
                "amount_total": money(line.get("total")),
                "amount_tax": money(line.get("total_tax")),
            })
        channel = data.get("channel")
        fulfilment = data.get("fulfilment")
        payment_group = data.get("payment_group")
        coupons = data.get("coupons") if isinstance(data.get("coupons"), list) else []
        return {
            "sede_id": sede.id,
            "external_id": int(data["id"]),
            "number": text(data.get("number"), 64) or str(data["id"]),
            "state": text(data.get("status"), 32),
            "channel": channel if channel in dict(CHANNELS[:3]) else "web",
            "fulfilment": fulfilment if fulfilment in dict(FULFILMENTS[:2]) else False,
            "date_order": parse_datetime(data.get("date_created")) or fields.Datetime.now(),
            "date_paid": parse_datetime(data.get("date_paid")),
            "date_completed": parse_datetime(data.get("date_completed")),
            "service_date": parse_date(data.get("service_date")),
            "service_time": text(data.get("service_time"), 64),
            "amount_total": money(data.get("total")),
            "amount_tax": money(data.get("total_tax")),
            "amount_shipping": money(data.get("shipping_total")),
            "amount_discount": money(data.get("discount_total")),
            "amount_refunded": money(data.get("refunded")),
            "payment_method": text(data.get("payment_method"), 128),
            "payment_method_title": text(data.get("payment_method_title"), 128),
            "payment_group": payment_group if payment_group in dict(PAYMENT_GROUPS) else "other",
            "postcode": text(data.get("postcode"), 16),
            "city": text(data.get("city"), 64),
            "customer_ref": text(data.get("customer_ref"), 64) or False,
            "coupons": ", ".join(text(c, 64) for c in coupons[:10]) or False,
            "line_ids": [fields.Command.clear()] + [fields.Command.create(vals) for vals in lines],
        }

    @api.model
    def _receive(self, sede, orders):
        """Create or update the orders sent by the website of a sede. Returns the per-order results."""
        results = []
        valid = [o for o in orders if isinstance(o, dict) and str(o.get("id", "")).isdigit()]
        existing = {
            order.external_id: order
            for order in self.sudo().search([("sede_id", "=", sede.id), ("external_id", "in", [int(o["id"]) for o in valid])])
        }
        categories = set()
        for data in orders:
            if data not in valid:
                results.append({"id": data.get("id") if isinstance(data, dict) else None, "ok": False, "error": "invalid order"})
                continue
            vals = self._values_from_payload(sede, data)
            categories.update(cmd[2]["category_name"] for cmd in vals["line_ids"][1:] if cmd[2]["category_name"])
            order = existing.get(vals["external_id"])
            if order:
                order.write(vals)
            else:
                existing[vals["external_id"]] = self.sudo().create(vals)
            results.append({"id": vals["external_id"], "ok": True})
        if categories:
            self.env["tw.littleinka.kpi.category"].sudo()._ensure(categories, "online")
        sede.sudo().last_sync = fields.Datetime.now()
        return results


class LittleInkaKpiOrderLine(models.Model):
    _name = "tw.littleinka.kpi.order.line"
    _description = "Little Inka KPI: riga di un ordine online"
    _order = "order_id, id"

    order_id = fields.Many2one("tw.littleinka.kpi.order", required=True, index=True, ondelete="cascade")
    sede_id = fields.Many2one(related="order_id.sede_id", store=True, index=True)
    company_id = fields.Many2one(related="order_id.company_id", store=True)
    currency_id = fields.Many2one(related="order_id.currency_id")
    product_ref = fields.Char("ID prodotto")
    variation_ref = fields.Char("ID variante")
    sku = fields.Char("SKU")
    name = fields.Char("Prodotto", required=True)
    category_name = fields.Char("Categoria", index=True)
    category_key = fields.Char(compute="_compute_category_key", store=True, index=True)
    quantity = fields.Float("Quantità")
    amount_total = fields.Monetary("Importo")
    amount_tax = fields.Monetary("IVA")

    @api.depends("category_name")
    def _compute_category_key(self):
        for line in self:
            line.category_key = normalize_name(line.category_name) or False
