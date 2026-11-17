import re
import unicodedata

from odoo import api, fields, models


def normalize_name(value):
    """Category name as a matching key: lower case, no accents, no leading «01. », single spaces."""
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    text = re.sub(r"^\s*\d+\s*[.)-]\s*", "", text)
    return re.sub(r"\s+", " ", text).strip()


class LittleInkaKpiFamily(models.Model):
    _name = "tw.littleinka.kpi.family"
    _description = "Little Inka KPI: famiglia di prodotti"
    _order = "sequence, id"

    name = fields.Char("Famiglia", required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    color = fields.Integer("Colore", default=0)
    keywords = fields.Char(
        "Parole chiave",
        help="Parole separate da virgola. Una categoria nuova (del sito o della cassa) che contiene "
        "una di queste parole va in questa famiglia da sola; si può sempre cambiare a mano.",
    )
    category_ids = fields.One2many("tw.littleinka.kpi.category", "family_id", string="Categorie")
    category_count = fields.Integer("N. categorie", compute="_compute_category_count")

    @api.depends("category_ids")
    def _compute_category_count(self):
        groups = dict(
            self.env["tw.littleinka.kpi.category"]._read_group(
                [("family_id", "in", self.ids)], ["family_id"], ["__count"]
            )
        )
        for family in self:
            family.category_count = groups.get(family, 0)

    def _keyword_list(self):
        self.ensure_one()
        return [normalize_name(k) for k in (self.keywords or "").split(",") if normalize_name(k)]

    @api.model
    def _guess(self, category_key):
        for family in self.search([]):
            if any(word in category_key for word in family._keyword_list()):
                return family
        return self.browse()


class LittleInkaKpiCategory(models.Model):
    """One row per category name seen online or in the POS, assigned to a family."""

    _name = "tw.littleinka.kpi.category"
    _description = "Little Inka KPI: categoria → famiglia"
    _order = "family_id, name"

    name = fields.Char("Categoria", required=True)
    key = fields.Char("Chiave", required=True, index=True, readonly=True)
    family_id = fields.Many2one("tw.littleinka.kpi.family", string="Famiglia", index=True, ondelete="set null")
    source = fields.Selection(
        [("online", "Sito e app"), ("pos", "Cassa"), ("both", "Sito, app e cassa")],
        string="Dove si usa",
        readonly=True,
    )

    _key_uniq = models.Constraint("unique(key)", "Questa categoria esiste già.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals["key"] = normalize_name(vals.get("key") or vals.get("name"))
            if not vals.get("family_id"):
                vals["family_id"] = self.env["tw.littleinka.kpi.family"]._guess(vals["key"]).id or False
        return super().create(vals_list)

    pos_category_ids = fields.Many2many(
        "pos.category", "tw_littleinka_kpi_category_pos_rel", "kpi_category_id", "pos_category_id",
        string="Categorie della cassa", readonly=True,
    )
    product_category_ids = fields.Many2many(
        "product.category", "tw_littleinka_kpi_category_product_rel", "kpi_category_id", "product_category_id",
        string="Categorie prodotto", readonly=True,
    )

    @api.model
    def _ensure(self, names, source):
        """Create the missing categories (names as they arrive), mark where they are used.

        Returns {key: category}.
        """
        wanted = {}
        for name in names:
            key = normalize_name(name)
            if key:
                # Shown without the sort number of WooCommerce («01. Poké Bowl» → «Poké Bowl»).
                wanted.setdefault(key, re.sub(r"^\s*\d+\s*[.)-]\s*", "", name).strip())
        if not wanted:
            return {}
        existing = self.search([("key", "in", list(wanted))])
        for category in existing:
            if category.source not in (source, "both"):
                category.source = "both" if category.source else source
        missing = sorted(set(wanted) - set(existing.mapped("key")))
        if missing:
            existing |= self.create([{"name": wanted[key], "key": key, "source": source} for key in missing])
        return {category.key: category for category in existing}

    @api.model
    def _refresh_pos(self):
        """Link the POS categories (and the product categories of POS products) to the rows of this table.

        The POS lines of the reports find their family through these links.
        """
        pos_categories = self.env["pos.category"].search([])
        # Product categories («All»…) only matter for POS products without a POS category.
        product_categories = self.env["product.template"].search(
            [("available_in_pos", "=", True), ("pos_categ_ids", "=", False)]
        ).categ_id
        by_key = self._ensure(pos_categories.mapped("name") + product_categories.mapped("name"), "pos")
        for records, field in ((pos_categories, "pos_category_ids"), (product_categories, "product_category_ids")):
            for record in records:
                category = by_key.get(normalize_name(record.name))
                if category and record not in category[field]:
                    category[field] = [fields.Command.link(record.id)]
        return True

    def action_refresh_pos(self):
        self.sudo()._refresh_pos()
        return True

    def action_apply_keywords(self):
        families = self.env["tw.littleinka.kpi.family"]
        for category in self or self.search([("family_id", "=", False)]):
            family = families._guess(category.key)
            if family:
                category.family_id = family
        return True
