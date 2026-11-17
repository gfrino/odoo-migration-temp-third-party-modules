from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.addons.tw_extend.models.tw_extend import AccountMove as SolarAccountMove


class AccountMove(models.Model):
    _inherit = 'account.move'

    is_light_invoice = fields.Boolean(string='Fattura light', default=False, index=True, copy=True)

    @api.constrains('is_light_invoice', 'sconto_tax', 'tw_disc', 'so_taxes_id', 'disc_after_iva', 'solare_id')
    def _check_light_adjustments(self):
        if any(m.is_light_invoice and (m.sconto_tax or m.tw_disc or m.so_taxes_id or m.disc_after_iva or m.solare_id) for m in self):
            raise ValidationError(self.env._('Per le fatture light, imposta sconti e IVA sulle righe della fattura.'))

    @api.depends('is_light_invoice')
    def _compute_amount(self):
        light = self.filtered('is_light_invoice')
        solar = self - light
        if solar:
            super(AccountMove, solar)._compute_amount()
        if light:
            super(SolarAccountMove, light)._compute_amount()
            for move in light:
                move.sconto_amount = 0.0
                move.so_tax_after_discount = 0.0
                move.tw_disc_amt = 0.0
                move.after_tw_amt = move.amount_untaxed

    def action_post(self):
        light = self.filtered('is_light_invoice')
        solar = self - light
        result = super(AccountMove, solar).action_post() if solar else True
        if light:
            result = super(SolarAccountMove, light).action_post()
        return result

    def action_print_light_invoice(self):
        return self.env.ref('account.account_invoices').report_action(self)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _prepare_invoice(self):
        vals = super()._prepare_invoice()
        vals['is_light_invoice'] = bool(self.is_light_offer)
        return vals

    def _get_invoice_grouping_keys(self):
        return super()._get_invoice_grouping_keys() + ['is_light_invoice']

    def action_view_invoice(self, invoices=False):
        action = super().action_view_invoice(invoices=invoices)
        if self and all(self.mapped('is_light_offer')):
            view = self.env.ref('tw_invoice_light.view_move_form_light')
            action['views'] = [(vid, mode) for vid, mode in action.get('views', []) if mode != 'form'] + [(view.id, 'form')]
        return action
