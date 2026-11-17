import hashlib
import secrets

from odoo import api, fields, models
from odoo.exceptions import ValidationError


def hash_key(key):
    return hashlib.sha256((key or "").encode()).hexdigest()


class LittleInkaKpiSede(models.Model):
    _name = "tw.littleinka.kpi.sede"
    _description = "Little Inka KPI: sede"
    _order = "sequence, name"

    name = fields.Char("Sede", required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    color = fields.Integer("Colore")
    company_id = fields.Many2one("res.company", string="Azienda", required=True, default=lambda self: self.env.company)
    website_url = fields.Char("Sito della sede", readonly=True, help="Arriva da solo con il primo ordine inviato dal sito.")
    pos_config_ids = fields.Many2many(
        "pos.config", "tw_littleinka_kpi_sede_pos_config_rel", "sede_id", "pos_config_id",
        string="Casse",
        help="Le casse del Punto vendita di questa sede: le loro vendite entrano nella dashboard come «Cassa».",
    )
    key_hash = fields.Char(readonly=True, copy=False, index=True, groups="base.group_system")
    key_hint = fields.Char("Chiave", readonly=True, copy=False, help="Solo le ultime cifre: la chiave intera si vede una volta sola, quando si crea.")
    key_date = fields.Datetime("Chiave creata il", readonly=True, copy=False)
    last_sync = fields.Datetime("Ultimo ordine ricevuto", readonly=True, copy=False)
    order_count = fields.Integer("Ordini online", compute="_compute_order_count")

    _key_hash_uniq = models.Constraint("unique(key_hash)", "Questa chiave è già usata da un'altra sede.")

    @api.constrains("pos_config_ids")
    def _check_pos_config_once(self):
        for sede in self:
            other = self.search([("id", "!=", sede.id), ("pos_config_ids", "in", sede.pos_config_ids.ids)], limit=1)
            if other:
                raise ValidationError(
                    self.env._("Una cassa può stare in una sola sede: è già in «%(sede)s».", sede=other.name)
                )

    def _compute_order_count(self):
        groups = dict(self.env["tw.littleinka.kpi.order"]._read_group([("sede_id", "in", self.ids)], ["sede_id"], ["__count"]))
        for sede in self:
            sede.order_count = groups.get(sede, 0)

    @api.model
    def _from_key(self, key):
        """The active sede that owns this key, or an empty recordset."""
        if not key or len(key) < 32:
            return self.browse()
        return self.sudo().search([("key_hash", "=", hash_key(key)), ("active", "=", True)], limit=1)

    def action_generate_key(self):
        """New key for the website of the sede. The old one stops working at once."""
        self.ensure_one()
        key = "lik_" + secrets.token_urlsafe(32)
        self.sudo().write({"key_hash": hash_key(key), "key_hint": "…" + key[-4:], "key_date": fields.Datetime.now()})
        wizard = self.env["tw.littleinka.kpi.key.wizard"].create({"sede_id": self.id, "key": key})
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Chiave per il sito"),
            "res_model": wizard._name,
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_revoke_key(self):
        self.sudo().write({"key_hash": False, "key_hint": False, "key_date": False})
        return True

    def action_open_orders(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("tw_littleinka_kpi.action_kpi_order")
        action["domain"] = [("sede_id", "=", self.id)]
        return action


class LittleInkaKpiKeyWizard(models.TransientModel):
    """Shows the new key once, to copy into the website (WooCommerce → Odoo KPI)."""

    _name = "tw.littleinka.kpi.key.wizard"
    _description = "Little Inka KPI: nuova chiave"
    _transient_max_hours = 0.1

    sede_id = fields.Many2one("tw.littleinka.kpi.sede", required=True, readonly=True)
    key = fields.Char("Chiave", readonly=True)
    odoo_url = fields.Char("Indirizzo di Odoo", compute="_compute_odoo_url")

    def _compute_odoo_url(self):
        url = self.env["ir.config_parameter"].sudo().get_str("web.base.url")
        for wizard in self:
            wizard.odoo_url = url

    def action_done(self):
        """Forget the plain key as soon as it has been copied (only its hash stays on the sede)."""
        self.write({"key": False})
        return {"type": "ir.actions.act_window_close"}
