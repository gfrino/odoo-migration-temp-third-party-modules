from odoo import api, fields, models
from odoo.tools.float_utils import float_compare


class ProductProduct(models.Model):
    _inherit = 'product.product'

    tw_cost_updated_on = fields.Date(
        string='Aggiornamento costo', readonly=True, copy=False, company_dependent=True,
        help="Data dell'ultima variazione effettiva del costo nella società corrente.")

    def write(self, vals):
        old = {p.id: p.standard_price for p in self} if 'standard_price' in vals else {}
        result = super().write(vals)
        if old:
            precision = self.env['decimal.precision'].precision_get('Product Price')
            changed = self.filtered(lambda p: float_compare(old[p.id], p.standard_price, precision_digits=precision))
            if changed:
                super(ProductProduct, changed).write({'tw_cost_updated_on': fields.Date.context_today(self)})
        return result

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        initialized = records.filtered(lambda p: p.standard_price and not p.tw_cost_updated_on)
        if initialized:
            initialized.write({'tw_cost_updated_on': fields.Date.context_today(self)})
        return records


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    tw_cost_updated_on = fields.Date(string='Aggiornamento costo', compute='_compute_cost_updated_on')

    @api.depends('product_variant_ids.tw_cost_updated_on')
    @api.depends_context('company')
    def _compute_cost_updated_on(self):
        for product in self:
            dates = product.product_variant_ids.mapped('tw_cost_updated_on')
            product.tw_cost_updated_on = max(filter(None, dates), default=False)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    tw_cost_updated_on = fields.Date(string='Aggiornamento costo', compute='_compute_cost_updated_on')

    @api.depends('product_id.tw_cost_updated_on', 'company_id')
    def _compute_cost_updated_on(self):
        for line in self:
            line.tw_cost_updated_on = line.product_id.with_company(line.company_id or self.env.company).tw_cost_updated_on


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    tw_cost_updated_on = fields.Date(string='Aggiornamento costo', compute='_compute_cost_updated_on')

    @api.depends('product_id.tw_cost_updated_on', 'company_id')
    def _compute_cost_updated_on(self):
        for line in self:
            line.tw_cost_updated_on = line.product_id.with_company(line.company_id or self.env.company).tw_cost_updated_on
