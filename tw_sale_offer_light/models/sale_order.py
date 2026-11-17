from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.addons.tw_extend.models.tw_extend import SaleOrder as SolarSaleOrder


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    is_light_offer = fields.Boolean(string='Offerta light', default=False, index=True, copy=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('is_light_offer', self.env.context.get('default_is_light_offer')):
                # A company-wide solar template must not populate a standard quotation.
                vals.setdefault('sale_order_template_id', False)
                vals.setdefault('sconto_tax', 0.0)
                vals.setdefault('tw_disc', 0.0)
                vals.setdefault('so_taxes_id', [fields.Command.clear()])
        return super().create(vals_list)

    @api.constrains('is_light_offer', 'sconto_tax', 'tw_disc', 'so_taxes_id')
    def _check_light_adjustments(self):
        if any(o.is_light_offer and (o.sconto_tax or o.tw_disc or o.so_taxes_id) for o in self):
            raise ValidationError(self.env._(
                'Per Offerta light, imposta sconti e imposte sulle righe del preventivo.'
            ))

    def action_confirm(self):
        light = self.filtered('is_light_offer')
        solar = self - light
        result = super(SaleOrder, solar).action_confirm() if solar else True
        if light:
            # Skip only the solar layer's unconditional project creation; keep the
            # native sale/project/stock confirmation chain and its access checks.
            result = super(SolarSaleOrder, light).action_confirm()
        return result

    def _prepare_invoice(self):
        if not self.is_light_offer:
            return super()._prepare_invoice()
        vals = super(SolarSaleOrder, self)._prepare_invoice()
        vals.update(solare_id=False, sconto_tax=0.0, tw_disc=0.0,
                    so_taxes_id=[fields.Command.clear()])
        return vals

    def action_quotation_send(self):
        self.ensure_one()
        if self.is_light_offer:
            return super(SolarSaleOrder, self).action_quotation_send()
        action = super().action_quotation_send()
        context = dict(action.get('context') or {})
        commands = context.pop('default_attachment_ids', [])
        context['pons_product_attachment_ids'] = [c[1] for c in commands if c[0] == 4]
        action['context'] = context
        return action

    @api.model
    def get_views(self, views, options=None):
        result = super().get_views(views, options=options)
        options = options or {}
        light_action = self.env.ref('tw_sale_offer_light.action_light_offers')
        light_form = self.env.ref('tw_sale_offer_light.view_order_form_light')
        is_light = options.get('action_id') == light_action.id or any(
            view_id == light_form.id for view_id, view_type in views
        )
        if is_light and options.get('toolbar'):
            report = self.env.ref('sale.action_report_saleorder')
            for view in result['views'].values():
                view.setdefault('toolbar', {})['print'] = [{
                    'id': report.id,
                    'name': 'Offerta light',
                    'type': 'ir.actions.report',
                }]
        return result

    def action_print_light_offer(self):
        return self.env.ref('sale.action_report_saleorder').report_action(self)

    def _prepare_template_order_values(self):
        vals = super()._prepare_template_order_values()
        vals['is_light_offer'] = self.is_light_offer
        return vals

    @api.constrains('sale_order_template_id', 'is_light_offer')
    def _check_template_scope(self):
        for order in self:
            if order.sale_order_template_id and order.sale_order_template_id.is_light_offer != order.is_light_offer:
                raise ValidationError('Il modello deve appartenere allo stesso tipo di offerta: Light o Solare.')


class SaleOrderTemplate(models.Model):
    _inherit = 'sale.order.template'

    is_light_offer = fields.Boolean(string='Solo Offerte light', default=False, index=True)

    def _search(self, domain, *args, **kwargs):
        if 'light_template_scope' in self.env.context:
            domain = fields.Domain(domain) & fields.Domain('is_light_offer', '=', bool(self.env.context['light_template_scope']))
        return super()._search(domain, *args, **kwargs)

    @api.model
    def get_section_templates(self, company_id):
        scoped = self.with_context(light_template_scope=bool(self.env.context.get('light_template_scope')))
        return super(SaleOrderTemplate, scoped).get_section_templates(company_id)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def save_section_template(self):
        self.ensure_one()
        scoped = self.with_context(light_template_scope=self.order_id.is_light_offer,
                                  default_is_light_offer=self.order_id.is_light_offer)
        return super(SaleOrderLine, scoped).save_section_template()


class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    def _compute_attachment_ids(self):
        super()._compute_attachment_ids()
        extra_ids = self.env.context.get('pons_product_attachment_ids', [])
        if extra_ids:
            extras = self.env['ir.attachment'].browse(extra_ids).exists()
            extras.check_access('read')
            for composer in self.filtered(lambda c: c.model == 'sale.order'):
                composer.attachment_ids |= extras
