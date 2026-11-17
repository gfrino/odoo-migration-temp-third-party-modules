import re
import unicodedata

from odoo import api, fields, models
from odoo.exceptions import ValidationError

# A category with one of these words holds additions (extra topping, extra protein…): its lines stay
# in the family with their revenue but are not pieces, the piece is the product they are added to.
ADDITION_WORDS = ("extra", "supplement", "aggiunt")


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
    is_fallback = fields.Boolean(
        "Raccoglie il resto",
        help="Le categorie nuove che nessuna parola chiave riconosce vanno in questa famiglia, "
        "così niente resta «Da assegnare». Una sola famiglia può farlo.",
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

    @api.constrains("is_fallback")
    def _check_single_fallback(self):
        if self.search_count([("is_fallback", "=", True)]) > 1:
            raise ValidationError(self.env._("Solo una famiglia può raccogliere il resto."))

    def _keyword_list(self):
        self.ensure_one()
        return [normalize_name(k) for k in (self.keywords or "").split(",") if normalize_name(k)]

    @api.model
    def _guess(self, category_key):
        for family in self.search([]):
            if any(word in category_key for word in family._keyword_list()):
                return family
        return self.browse()

    @api.model
    def _fallback(self):
        return self.search([("is_fallback", "=", True)], limit=1)


class LittleInkaKpiCategory(models.Model):
    """One row per category name seen online or in the POS, assigned to a family."""

    _name = "tw.littleinka.kpi.category"
    _description = "Little Inka KPI: categoria → famiglia"
    _order = "family_id, name"

    name = fields.Char("Categoria", required=True)
    key = fields.Char("Chiave", required=True, index=True, readonly=True)
    family_id = fields.Many2one("tw.littleinka.kpi.family", string="Famiglia", index=True, ondelete="set null")
    count_pieces = fields.Boolean(
        "Conta nei pezzi",
        default=True,
        help="Spento per le aggiunte (extra, supplementi): il loro incasso resta nella famiglia, "
        "ma non contano come pezzi, perché il pezzo è il prodotto a cui si aggiungono.",
    )
    source = fields.Selection(
        [("online", "Sito e app"), ("pos", "Cassa"), ("both", "Sito, app e cassa")],
        string="Dove si usa",
        readonly=True,
    )

    _key_uniq = models.Constraint("unique(key)", "Questa categoria esiste già.")

    @api.model_create_multi
    def create(self, vals_list):
        families = self.env["tw.littleinka.kpi.family"]
        for vals in vals_list:
            vals["key"] = normalize_name(vals.get("key") or vals.get("name"))
            if "count_pieces" not in vals:
                vals["count_pieces"] = not any(word in vals["key"] for word in ADDITION_WORDS)
            if not vals.get("family_id"):
                vals["family_id"] = (families._guess(vals["key"]) or families._fallback()).id or False
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
    def _ensure(self, names, source, hints=None):
        """Create the missing categories (names as they arrive), mark where they are used.

        `hints` is {key: family id} for the names no keyword recognises (the family of the parent
        category in the POS). Returns {key: category}.
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
            families = self.env["tw.littleinka.kpi.family"]
            existing |= self.create([
                {"name": wanted[key], "key": key, "source": source,
                 "family_id": families._guess(key).id or (hints or {}).get(key) or False}
                for key in missing
            ])
        return {category.key: category for category in existing}

    @api.model
    def _parent_hints(self, pos_categories):
        """{key: family id} from the parent POS category: «M» under «Crea la tua Poke» is a poké."""
        families = self.env["tw.littleinka.kpi.family"]
        known = {category.key: category.family_id for category in self.search([])}
        hints = {}
        for record in pos_categories:
            key = normalize_name(record.name)
            if key in known:
                continue
            parent = record.parent_id
            while parent:
                parent_key = normalize_name(parent.name)
                family = known.get(parent_key) or families._guess(parent_key)
                if family:
                    hints[key] = family.id
                    break
                parent = parent.parent_id
        return hints

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
        by_key = self._ensure(
            pos_categories.mapped("name") + product_categories.mapped("name"), "pos",
            hints=self._parent_hints(pos_categories),
        )
        for records, field in ((pos_categories, "pos_category_ids"), (product_categories, "product_category_ids")):
            for record in records:
                category = by_key.get(normalize_name(record.name))
                if category and record not in category[field]:
                    category[field] = [fields.Command.link(record.id)]
        self.env["tw.littleinka.kpi.product"]._refresh()
        return True

    def action_refresh_pos(self):
        self.sudo()._refresh_pos()
        return True

    def action_apply_keywords(self):
        families = self.env["tw.littleinka.kpi.family"]
        fallback = families._fallback()
        for category in self or self.search([("family_id", "=", False)]):
            family = families._guess(category.key) or (not category.family_id and fallback)
            if family:
                category.family_id = family
        return True


class LittleInkaKpiProduct(models.Model):
    """A POS product that does not follow its category: bags and cutlery sold from the «Extras» button…"""

    _name = "tw.littleinka.kpi.product"
    _description = "Little Inka KPI: prodotto con famiglia propria"
    _order = "family_id, product_tmpl_id"
    _rec_name = "product_tmpl_id"

    product_tmpl_id = fields.Many2one(
        "product.template", string="Prodotto", required=True, index=True, ondelete="cascade",
        domain=[("available_in_pos", "=", True)],
    )
    family_id = fields.Many2one("tw.littleinka.kpi.family", string="Famiglia", required=True, ondelete="cascade")
    count_pieces = fields.Boolean("Conta nei pezzi", default=True)

    _product_uniq = models.Constraint("unique(product_tmpl_id)", "Questo prodotto ha già una regola.")

    @api.model
    def _refresh(self):
        """Products of an additions category whose name belongs to another family get their own rule.

        «Sacchetti piccoli» and «Posate» live under the «Extras» button of the till, but they are
        accessories, not additions to a poké.
        """
        additions = self.env["tw.littleinka.kpi.category"].search(
            [("count_pieces", "=", False), ("pos_category_ids", "!=", False)]
        )
        if not additions:
            return
        products = self.env["product.template"].search([("pos_categ_ids", "in", additions.pos_category_ids.ids)])
        products -= self.search([("product_tmpl_id", "in", products.ids)]).product_tmpl_id
        families = self.env["tw.littleinka.kpi.family"]
        vals_list = []
        for product in products:
            family = families._guess(normalize_name(product.name))
            if family and family not in additions.family_id:
                vals_list.append({"product_tmpl_id": product.id, "family_id": family.id})
        if vals_list:
            self.create(vals_list)
