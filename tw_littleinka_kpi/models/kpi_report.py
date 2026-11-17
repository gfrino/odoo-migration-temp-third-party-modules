from odoo import fields, models, tools
from odoo.tools import SQL

from .kpi_order import CHANNELS, FULFILMENTS

SALES_TYPES = [("online", "Online"), ("pos", "Cassa")]
POS_DONE_STATES = ("paid", "done", "invoiced")
PAYMENT_LABELS = SQL(
    """CASE o.payment_group
         WHEN 'twint' THEN 'TWINT' WHEN 'card' THEN 'Carta' WHEN 'apple_pay' THEN 'Apple Pay'
         WHEN 'google_pay' THEN 'Google Pay' WHEN 'cash' THEN 'Contanti' WHEN 'none' THEN 'Nessuno'
         ELSE 'Altro' END"""
)


def _lang(env):
    """Language of the product names in the views: the one of the main company (Italian for Little Inka)."""
    company = env["res.company"].sudo().search([], limit=1, order="id")
    return company.partner_id.lang or "en_US"


class LittleInkaKpiReport(models.Model):
    """One row per sale: online orders (counted states, net of refunds) and POS orders of the linked tills."""

    _name = "tw.littleinka.kpi.report"
    _description = "Little Inka KPI: vendite"
    _auto = False
    _order = "date desc"

    date = fields.Datetime("Data", readonly=True)
    sede_id = fields.Many2one("tw.littleinka.kpi.sede", string="Sede", readonly=True)
    company_id = fields.Many2one("res.company", string="Azienda", readonly=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    sales_type = fields.Selection(SALES_TYPES, string="Vendita", readonly=True)
    channel = fields.Selection(CHANNELS, string="Canale", readonly=True)
    fulfilment = fields.Selection(FULFILMENTS, string="Consegna o ritiro", readonly=True)
    payment_label = fields.Char("Pagamento", readonly=True)
    order_count = fields.Integer("Ordini", readonly=True, aggregator="sum")
    item_count = fields.Float("Pezzi", readonly=True, aggregator="sum")
    amount_total = fields.Monetary("Fatturato (IVA incl.)", readonly=True, aggregator="sum")
    amount_untaxed = fields.Monetary("Fatturato senza IVA", readonly=True, aggregator="sum")

    def _query(self):
        return SQL(
            """
            SELECT o.id * 2 AS id, o.date_order AS date, o.sede_id, o.company_id,
                   'online' AS sales_type, o.channel, o.fulfilment, %(payment)s AS payment_label,
                   1 AS order_count, o.item_count,
                   o.amount_net AS amount_total,
                   o.amount_net - o.amount_tax AS amount_untaxed
              FROM tw_littleinka_kpi_order o
             WHERE o.is_counted
            UNION ALL
            SELECT po.id * 2 + 1, po.date_order, rel.sede_id, po.company_id,
                   'pos', 'pos', 'in_store',
                   (SELECT COALESCE(pm.name->>%(lang)s, pm.name->>'en_US')
                      FROM pos_payment pp JOIN pos_payment_method pm ON pm.id = pp.payment_method_id
                     WHERE pp.pos_order_id = po.id ORDER BY abs(pp.amount) DESC, pp.id LIMIT 1),
                   CASE WHEN po.amount_total < 0 THEN -1 ELSE 1 END,
                   (SELECT COALESCE(sum(l.qty), 0) FROM pos_order_line l
                     WHERE l.order_id = po.id
                       AND NOT EXISTS (SELECT 1 FROM pos_order_line c WHERE c.combo_parent_id = l.id)),
                   po.amount_total, po.amount_total - po.amount_tax
              FROM pos_order po
              LEFT JOIN tw_littleinka_kpi_sede_pos_config_rel rel ON rel.pos_config_id = po.config_id
             WHERE po.state IN %(states)s
            """,
            payment=PAYMENT_LABELS,
            lang=_lang(self.env),
            states=POS_DONE_STATES,
        )

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(SQL("CREATE OR REPLACE VIEW %s AS (%s)", SQL.identifier(self._table), self._query()))


class LittleInkaKpiReportLine(models.Model):
    """One row per product sold, with its family (through the category table)."""

    _name = "tw.littleinka.kpi.report.line"
    _description = "Little Inka KPI: prodotti venduti"
    _auto = False
    _order = "date desc"

    date = fields.Datetime("Data", readonly=True)
    sede_id = fields.Many2one("tw.littleinka.kpi.sede", string="Sede", readonly=True)
    company_id = fields.Many2one("res.company", string="Azienda", readonly=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    sales_type = fields.Selection(SALES_TYPES, string="Vendita", readonly=True)
    channel = fields.Selection(CHANNELS, string="Canale", readonly=True)
    family_id = fields.Many2one("tw.littleinka.kpi.family", string="Famiglia", readonly=True)
    category_name = fields.Char("Categoria", readonly=True)
    product_name = fields.Char("Prodotto", readonly=True)
    quantity = fields.Float("Pezzi", readonly=True, aggregator="sum")
    amount_total = fields.Monetary("Fatturato (IVA incl.)", readonly=True, aggregator="sum")

    def _query(self):
        return SQL(
            """
            SELECT l.id * 2 AS id, o.date_order AS date, o.sede_id, o.company_id,
                   'online' AS sales_type, o.channel, c.family_id,
                   COALESCE(c.name, l.category_name) AS category_name, l.name AS product_name,
                   l.quantity, l.amount_total
              FROM tw_littleinka_kpi_order_line l
              JOIN tw_littleinka_kpi_order o ON o.id = l.order_id
              LEFT JOIN tw_littleinka_kpi_category c ON c.key = l.category_key
             WHERE o.is_counted
            UNION ALL
            SELECT pl.id * 2 + 1, po.date_order, rel.sede_id, po.company_id,
                   'pos', 'pos', COALESCE(pcat.family_id, ccat.family_id),
                   COALESCE(pcat.name, ccat.name),
                   COALESCE(pt.name->>%(lang)s, pt.name->>'en_US'),
                   CASE WHEN EXISTS (SELECT 1 FROM pos_order_line ch WHERE ch.combo_parent_id = pl.id)
                        THEN 0 ELSE pl.qty END,
                   pl.price_subtotal_incl
              FROM pos_order_line pl
              JOIN pos_order po ON po.id = pl.order_id
              JOIN product_product pp ON pp.id = pl.product_id
              JOIN product_template pt ON pt.id = pp.product_tmpl_id
              LEFT JOIN tw_littleinka_kpi_sede_pos_config_rel rel ON rel.pos_config_id = po.config_id
              LEFT JOIN LATERAL (
                    SELECT c.family_id, c.name
                      FROM pos_category_product_template_rel r
                      JOIN tw_littleinka_kpi_category_pos_rel cr ON cr.pos_category_id = r.pos_category_id
                      JOIN tw_littleinka_kpi_category c ON c.id = cr.kpi_category_id
                     WHERE r.product_template_id = pt.id
                     ORDER BY c.family_id IS NULL, r.pos_category_id
                     LIMIT 1) pcat ON TRUE
              LEFT JOIN LATERAL (
                    SELECT c.family_id, c.name
                      FROM tw_littleinka_kpi_category_product_rel cr
                      JOIN tw_littleinka_kpi_category c ON c.id = cr.kpi_category_id
                     WHERE cr.product_category_id = pt.categ_id
                     LIMIT 1) ccat ON TRUE
             WHERE po.state IN %(states)s
            """,
            lang=_lang(self.env),
            states=POS_DONE_STATES,
        )

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(SQL("CREATE OR REPLACE VIEW %s AS (%s)", SQL.identifier(self._table), self._query()))
