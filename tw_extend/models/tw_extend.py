# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from datetime import date, datetime
from odoo.exceptions import UserError, ValidationError



def _pons_total_tax(taxes, amount, currency, partner):
    if not taxes:
        return 0.0
    values = taxes.compute_all(amount, currency=currency, quantity=1.0, partner=partner)
    return values['total_included'] - values['total_excluded']


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _prepare_invoice_line(self, **optional_values):
        self.ensure_one()
        res = super()._prepare_invoice_line(**optional_values)
        if self.category_id:
            res.update({"category_id": self.category_id.id})
        return res

    category_id = fields.Many2one("product.category")
    pons_optional_quantity = fields.Float(
        string="Quantità proposta", digits="Product Unit", default=1.0, copy=True,
        help="Quantità proposta per una prestazione opzionale non ancora selezionata.",
    )

    def _pons_is_unselected_optional(self):
        self.ensure_one()
        return bool(self.is_optional or (self._is_line_optional() and not self.product_uom_qty))


class SaleOrderTemplateLine(models.Model):
    _inherit = "sale.order.template.line"

    def _prepare_order_line_values(self, fiscal_position, currency):
        res = super()._prepare_order_line_values(fiscal_position, currency)
        res['category_id'] = self.category_id.id or False
        return res

    category_id = fields.Many2one("product.category")


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_quotation_send(self):
        self.ensure_one()
        action = super().action_quotation_send()
        templates = self.order_line.filtered(lambda line: not line._pons_is_unselected_optional() and line.product_id.is_add_attachement).mapped('product_template_id')
        if templates:
            attachments = self.env['ir.attachment'].search([('res_model', '=', 'product.template'), ('res_id', 'in', templates.ids)])
            context = dict(action.get('context') or {})
            context['default_attachment_ids'] = [(4, attachment.id) for attachment in attachments]
            action['context'] = context
        return action

    def action_cancel(self):
        return self._action_cancel()

    def get_category_detail_data(self, category):
        res = {}
        for data in self:
            prod_res_list = []
            for ol in data.order_line.filtered(lambda item: not item._pons_is_unselected_optional()):
                if category.id == ol.product_id.categ_id.id:
                    att_val = {}
                    for av in ol.product_id.product_tmpl_id.attribute_line_ids:
                        if av.attribute_id.name == 'Origine':
                            origin_val = ''
                            for v in av.value_ids:
                                origin_val += str(v.name) + ' '
                            att_val.update({'origin': origin_val})
                        if av.attribute_id.name == 'Garanzia fabbricazione':
                            gf_val = ''
                            for v in av.value_ids:
                                gf_val += str(v.name) + ' '
                            att_val.update({'g_f': gf_val})
                        if av.attribute_id.name == 'Garanzia produzione':
                            gp_val = ''
                            for v in av.value_ids:
                                gp_val += str(v.name) + ' '
                            att_val.update({'g_p': gp_val})
                        if av.attribute_id.name == 'Capacità':
                            cap_val = ''
                            for v in av.value_ids:
                                cap_val += str(v.name) + ' '
                            att_val.update({'cap': cap_val})
                        if av.attribute_id.name == 'kVA':
                            kva_val = ''
                            for v in av.value_ids:
                                kva_val += str(v.name) + ' '
                            att_val.update({'kva': kva_val})
                    if att_val:
                        att_val.update({'prod_name': ol.product_id.name})
                        prod_res_list.append(att_val)
        return prod_res_list


    def get_category_data(self, category):
        categ_list = []
        have_to_add = False
        # categ_list.append({'categ_name':category.name})
        # categ_list.append({'origin': 'Origine'})
        for data in self:
            g_f_add = False
            g_p_add = False
            cap_add = False
            kva_add = False
            for line in data.order_line.filtered(lambda item: not item._pons_is_unselected_optional()):
                if line.category_id.id == category.id:
                    for av in line.product_id.product_tmpl_id.attribute_line_ids:
                        if av.attribute_id.name == 'Garanzia fabbricazione':
                            if not g_f_add:
                                categ_list.append({'g_f': 'Gar. fabbricazione'})
                            g_f_add = True
                            have_to_add = True
                        if av.attribute_id.name == 'Garanzia produzione':
                            if not g_p_add:
                                categ_list.append({'g_p': 'Gar. Produzione'})
                            g_p_add = True
                            have_to_add = True
                        if av.attribute_id.name == 'Capacità':
                            if not cap_add:
                                categ_list.append({'cap': 'Capacità'})
                            cap_add = True
                        if line.category_id.name in ['Inverter','Wechselrichter']:
                            if not kva_add:
                                categ_list.append({'kva': 'kVA'})
                            kva_add = True
            if have_to_add:
                categ_list.append({'categ_name': category.name})
                categ_list.append({'origin': 'Origine'})
        return categ_list

    def get_category_attribute(self):
        res = {}
        for data in self:
            categ_ids = []
            for l in data.order_line.filtered(lambda item: not item._pons_is_unselected_optional()):
                if l.product_id.categ_id.id not in categ_ids:
                    categ_ids.append(l.product_id.categ_id.id)
            for c in categ_ids:
                prod_res_list = []
                for ol in data.order_line.filtered(lambda item: not item._pons_is_unselected_optional()):
                    if c == ol.product_id.categ_id.id:
                        add_att_value = False
                        for av in ol.product_id.product_tmpl_id.attribute_line_ids:
                            if av.attribute_id.name in ['Garanzia fabbricazione', 'Garanzia produzione']:
                                add_att_value = True
                        att_val = {}
                        if add_att_value:
                            for av in ol.product_id.product_tmpl_id.attribute_line_ids:
                                if av.attribute_id.name == 'Origine':
                                    origin_val = ''
                                    for v in av.value_ids:
                                        origin_val += str(v.name) + ' '
                                    att_val.update({'origin': origin_val})
                                if av.attribute_id.name == 'Garanzia fabbricazione':
                                    gf_val = ''
                                    for v in av.value_ids:
                                        gf_val += str(v.name) + ' '
                                    att_val.update({'g_f': gf_val})
                                if av.attribute_id.name == 'Garanzia produzione':
                                    gp_val = ''
                                    for v in av.value_ids:
                                        gp_val += str(v.name) + ' '
                                    att_val.update({'g_p': gp_val})
                                if av.attribute_id.name == 'kVA':
                                    kva_val = ''
                                    for v in av.value_ids:
                                        kva_val += str(v.name) + ' '
                                    att_val.update({'kva': kva_val})
                        if att_val:
                            att_val.update({'prod_name': ol.product_id.name})
                        if att_val:
                            prod_res_list.append(att_val)
                        if prod_res_list:
                            res[ol.product_id.categ_id.name] = prod_res_list
        return res

    # def get_category_attribute(self):
    #   res = {}
    #   for data in self:
    #       categ_ids = []
    #       for l in data.order_line:
    #           if l.product_id.categ_id.id not in categ_ids:
    #               categ_ids.append(l.product_id.categ_id.id)
    #       for c in categ_ids:
    #           prod_res_list = []
    #           for ol in data.order_line:
    #               if c == ol.product_id.categ_id.id:
    #                   add_att_value = False
    #                   for av in ol.product_id.product_tmpl_id.attribute_line_ids:
    #                       if av.attribute_id.name in ['Garanzia fabbricazione', 'Garanzia produzione']:
    #                           add_att_value = True
    #                   att_val = {}
    #                   if add_att_value:
    #                       for av in ol.product_id.product_tmpl_id.attribute_line_ids:
    #                           if av.attribute_id.name == 'Origine':
    #                               origin_val = ''
    #                               for v in av.value_ids:
    #                                   origin_val += str(v.name) + ' '
    #                               att_val.update({'origin': origin_val})
    #                           if av.attribute_id.name == 'Garanzia fabbricazione':
    #                               gf_val = ''
    #                               for v in av.value_ids:
    #                                   gf_val += str(v.name) + ' '
    #                               att_val.update({'g_f': gf_val})
    #                           if av.attribute_id.name == 'Garanzia produzione':
    #                               gp_val = ''
    #                               for v in av.value_ids:
    #                                   gp_val += str(v.name) + ' '
    #                               att_val.update({'g_p': gp_val})
    #                   if att_val:
    #                       att_val.update({'prod_name': ol.product_id.name})
    #                   if att_val:
    #                       prod_res_list.append(att_val)
    #                   if prod_res_list:
    #                       res[ol.product_id.categ_id.name] = prod_res_list
    #   return res

    @api.depends('order_line.price_subtotal', 'order_line.price_tax', 'order_line.price_total', 'sconto_tax', 'so_taxes_id', 'tw_disc', 'sconto_dis_type', 'tw_dis_type')
    def _compute_amounts(self):
        super()._compute_amounts()
        for order in self:
            untaxed = order.amount_untaxed
            tax = order.amount_tax
            total = untaxed + tax
            first = order.sconto_tax if order.sconto_dis_type == 'fixed' else total * order.sconto_tax / 100.0
            total -= first
            second = order.tw_disc if order.tw_dis_type == 'fixed' else total * order.tw_disc / 100.0
            total -= second
            extra_tax = _pons_total_tax(order.so_taxes_id, total, order.currency_id, order.partner_id)
            order.amount_untaxed = untaxed
            order.amount_tax = tax
            order.amount_total = total + extra_tax
            order.sconto_amount = first
            order.tw_disc_amt = second
            order.after_sconto_amt = untaxed - first
            order.after_tw_amt = untaxed - first - second
            order.so_tax_after_discount = extra_tax


    def button_dummy(self):
        self._compute_amounts()


    @api.depends('order_line.product_id', 'order_line.category_id', 'order_line.product_uom_qty', 'order_line.is_optional', 'order_line.sequence')
    def _compute_data(self):
        for data in self:
            potenza_amt = 0.0
            superficie_amt = 0.0
            for line in data.order_line.filtered(lambda item: not item._pons_is_unselected_optional()):
                if line.category_id and line.category_id.name in ['PV Modules','PV Module','Moduli']:
                    wp_att_price = 0.0
                    base_att_price = 0.0
                    altezza_att_price = 0.0
                    for att in line.product_id.product_tmpl_id.attribute_line_ids:
                        if att.attribute_id.name == 'Wp':
                            for v in att.value_ids:
                                wp_att_price = int(v.name)
                        if att.attribute_id.name == 'Base':
                            for v in att.value_ids:
                                base_att_price = int(v.name)
                        if att.attribute_id.name == 'Altezza':
                            for v in att.value_ids:
                                altezza_att_price = int(v.name)
                    potenza_amt += (wp_att_price * line.product_uom_qty) / 1000
                    superficie_amt += (base_att_price * altezza_att_price * line.product_uom_qty) / 1000000
            data.potenza_totale = str(round(potenza_amt,3)) + ' kWp'
            data.superficie_dei_moduli = str(round(superficie_amt,2)) + ' m2'

    def get_potenza_totale_val(self):
        for data in self:
            potenza_amt = 0.0
            for line in data.order_line.filtered(lambda item: not item._pons_is_unselected_optional()):
                if line.category_id and line.category_id.name in ['PV Modules','PV Module','Moduli']:
                    wp_att_price = 0.0
                    for att in line.product_id.product_tmpl_id.attribute_line_ids:
                        if att.attribute_id.name == 'Wp':
                            for v in att.value_ids:
                                wp_att_price = int(v.name)
                    potenza_amt += (wp_att_price * line.product_uom_qty) / 1000
            return potenza_amt

    def get_cont_pot_less_30(self):
        for data in self:
            amt = 0.0
            if data.incentivo_id:
                incentivo_line_obj = self.env['tw.incentivo.line']
                line_id = incentivo_line_obj.search([
                    ('tipo_di_installazione', '=', data.tipo_di_installazione),
                    ('autoconsumo','=',data.autoconsumo),
                    ('facciata','=',data.facciata),
                    ('incentivo_id','=',data.incentivo_id.id)
                ], limit=1)
                if line_id:
                    if data.get_potenza_totale_val() > 30:
                        amt = line_id.less_30 * 30
                    else:
                        amt = line_id.less_30 * data.get_potenza_totale_val()
            return amt

    def get_cont_pot_gre_30(self):
        for data in self:
            amt = 0.0
            if data.incentivo_id:
                incentivo_line_obj = self.env['tw.incentivo.line']
                line_id = incentivo_line_obj.search([
                    ('tipo_di_installazione', '=', data.tipo_di_installazione),
                    ('autoconsumo','=',data.autoconsumo),
                    ('facciata','=',data.facciata),
                    ('incentivo_id','=',data.incentivo_id.id)
                ], limit=1)
                if line_id:
                    if data.get_potenza_totale_val() > 30:
                        amt = line_id.great_30 * (data.get_potenza_totale_val() - 30)
            return amt

    def action_confirm(self):
        for data in self:
            if not data.solare_project_id:
                project_id = self.env['project.project'].create({
                    'name': data.name,
                    'sale_order_id': data.id
                })
                data.solare_project_id = project_id
            # if data.solare_project_id and not data.solare_task_id:
            #   task_id = self.env['project.task'].create({
            #       'name': data.name,
            #       'project_id': data.solare_project_id.id,
            #       'sale_order_id': data.id,
            #   })
            #   data.solare_task_id = task_id
        return super(SaleOrder, self).action_confirm()

    def action_calculate_data(self):
        for data in self:
            pronovo_federale = data.get_cont_pot_gre_30() + data.get_cont_pot_less_30() + data.contributo_base
            rimunerazione_federale = (data.get_cont_pot_gre_30() / 3) + (data.get_cont_pot_less_30() / 2) + (data.contributo_base / 2)
            data.with_context(pons_calculating_incentives=True).write({
                "pronovo_federale": pronovo_federale,
                "rimunerazione_federale": rimunerazione_federale,
                "pronovo_manual": False,
                "fer_manual": False,
            })
        return True

    def write(self, vals):
        vals = dict(vals)
        if not self.env.context.get('pons_calculating_incentives'):
            if 'pronovo_federale' in vals:
                vals['pronovo_manual'] = True
            if 'rimunerazione_federale' in vals:
                vals['fer_manual'] = True
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for values in vals_list:
            values = dict(values)
            for field, flag in [('pronovo_federale', 'pronovo_manual'),
                                ('rimunerazione_federale', 'fer_manual')]:
                if field in values:
                    values.setdefault(flag, True)
            prepared.append(values)
        return super().create(prepared)

    hide_prices = fields.Boolean(
        string="Nascondi prezzi", copy=True,
        help="Nell'offerta completa mostra gli importi solo per categoria, "
             "mantenendo descrizione, quantità e unità dei prodotti.")

    pronovo_manual = fields.Boolean(copy=True)
    fer_manual = fields.Boolean(copy=True)

    def _get_inv_taxes(self):
        return self.env['account.tax'].search([
            ('amount', '=', 8.1), ('amount_type', '=', 'percent'),
            ('type_tax_use', '=', 'sale'), ('company_id', '=', self.env.company.id),
        ], limit=1)

    CH1903_LV03 = fields.Char(string="CH1903 / LV03")
    wgs_84 = fields.Char(string="WGS 84 (long/lat)")
    altitudine = fields.Char(string="Altitudine")
    mappale = fields.Char(string="Mappale")
    azimuth = fields.Char(string="Azimuth")
    pendenza_tetto = fields.Char(string="Pendenza tetto")
    potenza_totale = fields.Char(string="Potenza totale", compute='_compute_data')
    superficie_dei_moduli = fields.Char(string="Superficie dei moduli", compute='_compute_data')
    produzione_annua_stimata = fields.Char(string="Produzione annua stimata")
    tipo_di_installazione = fields.Selection([
        ("Annesso", "Annesso/Isolato"),
        ("Integrato", "Integrato"),
    ], string="Tipo di installazione")
    img1 = fields.Image()
    img2 = fields.Image()
    img3 = fields.Image()
    sconto_tax = fields.Float(string="Sconto %")
    sconto_dis_type = fields.Selection([('fixed', 'Fisso'),('percent', 'Percentuale')], string="Discount Type", default="percent")
    sconto_amount = fields.Float(compute='_compute_amounts', store=True, string="Importo sconto")
    after_sconto_amt = fields.Float(compute='_compute_amounts', store=True, string="Amount")
    tw_disc = fields.Float(string="Disc. %")
    tw_dis_type = fields.Selection([('fixed', 'Fisso'), ('percent', 'Percentuale')], string="Discount Type",default="percent")
    tw_disc_amt = fields.Float(compute='_compute_amounts', store=True, )
    after_tw_amt = fields.Float(compute='_compute_amounts', store=True, string="Amount")
    so_taxes_id = fields.Many2many('account.tax', 'sale_order_total_taxes', 'so_id', 'tax_id',
                                   string='Taxes',
                                   domain=['|', ('active', '=', False), ('active', '=', True)])
    so_tax_after_discount = fields.Float(compute='_compute_amounts', store=True, string='Importo IVA',
                                         default=0.0)
    autoconsumo = fields.Selection([
        ("si", "Si"),
        ("no", "No")
    ])
    facciata = fields.Selection([
        ("si", "Si"),
        ("no", "No")
    ])
    contributo_base = fields.Float()
    incentivo_id = fields.Many2one('tw.incentivo')
    contributo_comunale = fields.Float()
    validita_offerta_id = fields.Many2one("validita.offerta", string="Validità offerta")
    fornitura_id = fields.Many2one("sale.fornitura", string="Fornitura")
    solare_project_id = fields.Many2one('project.project')
    solare_task_id = fields.Many2one('project.task')
    ubicazione_impianto = fields.Char()
    pronovo_federale = fields.Float(string="Pronovo(Federale)")
    rimunerazione_federale = fields.Float(string="Rimunerazione FER (Cantonale) ")

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        for data in self:
            if data.partner_id:
                data.ubicazione_impianto = str(data.partner_id.street or '') + ' ' + str(data.partner_id.street2 or '') + ' ' + str(data.partner_id.zip or '') + ' ' + str(data.partner_id.city or '')

    def _prepare_invoice(self):
        values = super()._prepare_invoice()
        values.update({
            'solare_id': self.id,
            'sconto_dis_type': self.sconto_dis_type,
            'sconto_tax': self.sconto_tax,
            'tw_dis_type': self.tw_dis_type,
            'tw_disc': self.tw_disc,
            'so_taxes_id': [(6, 0, self.so_taxes_id.ids)],
        })
        return values

class validita_offerta(models.Model):
    _name = "validita.offerta"
    _description = "Quotation Validity"

    name = fields.Char()


class sale_fornitura(models.Model):
    _name = "sale.fornitura"
    _description = "Quotation Supply"

    name = fields.Char()


class AccountMove(models.Model):
    _inherit = "account.move"

    def button_dummy(self):
        self._compute_amount()
        self.write({})

    @api.depends('line_ids.balance', 'line_ids.amount_currency', 'line_ids.amount_residual', 'line_ids.amount_residual_currency', 'state', 'sconto_tax', 'so_taxes_id', 'tw_disc', 'sconto_dis_type', 'tw_dis_type', 'disc_after_iva')
    def _compute_amount(self):
        res = super(AccountMove, self)._compute_amount()
        for move in self:
            total_untaxed, total_untaxed_currency = 0.0, 0.0
            total_tax, total_tax_currency = 0.0, 0.0
            total_residual, total_residual_currency = 0.0, 0.0
            total, total_currency = 0.0, 0.0
            after_tw_amt = 0.0
            sign = move.direction_sign
            for line in move.line_ids:
                if move.is_invoice(True):
                    # === Invoices ===
                    if line.display_type == 'tax' or (line.display_type == 'rounding' and line.tax_repartition_line_id):
                        # Tax amount.
                        total_tax += line.balance
                        total_tax_currency += line.amount_currency
                        total += line.balance
                        total_currency += line.amount_currency
                    elif line.display_type in ('product', 'rounding'):
                        # Untaxed amount.
                        total_untaxed += line.balance
                        total_untaxed_currency += line.amount_currency
                        total += line.balance
                        total_currency += line.amount_currency
                    elif line.display_type == 'payment_term':
                        # Residual amount.
                        total_residual += line.amount_residual
                        total_residual_currency += line.amount_residual_currency
                else:
                    # === Miscellaneous journal entry ===
                    if line.debit:
                        total += line.balance
                        total_currency += line.amount_currency
            # amt_tot = (sign * total_untaxed_currency) + (sign * total_tax_currency)
            amt_tot = sign * total_untaxed_currency
            # amt_res = total_residual_currency
            amt_res = total_residual_currency  - move.amount_tax
            main_amt_res = amt_res
            if move.move_type == 'out_refund':
                amt_res = total_residual_currency * -1

            amt_sconto = 0.0
            after_tw_amt = move.amount_untaxed
            if move.sconto_tax and move.sconto_dis_type:
                # amt_sconto = (amt_tot * move.sconto_tax) / 100
                if move.sconto_dis_type == 'fixed':
                    amt_sconto = move.sconto_tax
                else:
                    amt_sconto = round((amt_tot * move.sconto_tax) / 100,2)
                amt_tot = amt_tot - amt_sconto
                amt_res = amt_res - amt_sconto
                after_tw_amt = after_tw_amt - amt_sconto
            tw_disc_amt = 0.0
            if move.tw_disc and move.tw_dis_type:
                # tw_disc_amt = (amt_tot * move.tw_disc) / 100
                if move.tw_dis_type == 'fixed':
                    tw_disc_amt = move.tw_disc
                else:
                    tw_disc_amt = round((amt_tot * move.tw_disc) / 100,2)
                amt_tot = amt_tot - tw_disc_amt
                amt_res = amt_res - tw_disc_amt
                after_tw_amt = after_tw_amt - tw_disc_amt
            amt_taxes = 0.0
            if move.so_taxes_id:
                amt_taxes = _pons_total_tax(move.so_taxes_id, amt_tot, move.currency_id, move.partner_id)
                if amt_taxes:
                    amt_tot += amt_taxes
                    amt_res += amt_taxes
            amt_tot = amt_tot - move.disc_after_iva
            amt_res = round(amt_res,2) - round(move.disc_after_iva,2)
            if main_amt_res == 0.0:
                amt_res = move.amount_residual
            move.amount_total = amt_tot #sign * total_currency
            move.amount_residual = amt_res
            move.sconto_amount = amt_sconto
            move.so_tax_after_discount = amt_taxes
            move.tw_disc_amt = tw_disc_amt
            move.after_tw_amt = after_tw_amt
        return res

    # def button_draft(self):
    #   already_exists = self.line_ids.filtered(
    #       lambda line: line.name and line.name.find('TwSconto'))
    #   print ("already_existsalready_exists:,already_exists",already_exists)
    #   already_exists.unlink()
    #   if already_exists:
    #       already_exists.update({
    #           'name': 'TwSconto',
    #           'debit': 0.0,
    #           'credit': 0.0,
    #       })
    #       terms_lines = self.line_ids.filtered(
    #           lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable'))
    #       other_lines = self.line_ids.filtered(
    #           lambda line: line.account_id.account_type not in ('asset_receivable', 'liability_payable'))
    #       already_exists = self.line_ids.filtered(
    #           lambda line: line.name and line.name.find('TwSconto') == 0)
    #       total_balance = sum(other_lines.mapped('balance'))
    #       total_balance = total_balance
    #       total_amount_currency = sum(other_lines.mapped('amount_currency'))
    #       dict1 = {
    #           'credit': total_balance < 0.0 and -total_balance or 0.0,
    #           'debit': total_balance > 0.0 and total_balance or 0.0,
    #       }
    #       dict2 = {
    #           'debit': total_balance < 0.0 and -total_balance or 0.0,
    #           'credit': total_balance > 0.0 and total_balance or 0.0,
    #       }
    #       self.line_ids = [(1, already_exists.id, dict1), (1, terms_lines[0].id, dict2)]
    #   # print(sssssss)
    #   res = super().button_draft()
    #   return res

    def action_post(self):
        for r in self:
            already_exists = r.line_ids.filtered(
                lambda line: line.is_tw_sconto)
            disc = r.so_tax_after_discount - r.sconto_amount - r.tw_disc_amt - r.disc_after_iva - r.amount_tax
            amount = disc * -1
            if r.move_type == 'out_refund':
                amount = disc
            in_draft_mode = r != r._origin
            # if already_exists and already_exists[0].name == 'TwSconto':
            if already_exists:
                already_exists[0].name = 'TwSconto'
                # already_exists.update({
                #   'name': 'TwSconto',
                #   'debit': amount > 0.0 and amount or 0.0,
                #   'credit': amount < 0.0 and -amount or 0.0,
                # })
            else:
                if already_exists:
                    already_exists[0].is_tw_sconto = False
                new_tax_line = self.env['account.move.line']
                create_method = in_draft_mode and \
                                self.env['account.move.line'].new or \
                                self.env['account.move.line'].create
                dict = {
                    'move_name': r.name,
                    'name': 'TwSconto',
                    'is_tw_sconto': True,
                    'price_unit': amount,
                    'quantity': 1,
                    'account_id': r.company_id.partner_id.property_account_receivable_id.id,
                    'move_id': r.id,
                    'date': r.date,
                    'sequence': True,
                    'partner_id': r.partner_id.id,
                    'company_id': r.company_id.id,
                    'company_currency_id': r.currency_id.id,
                    'debit': amount > 0.0 and amount or 0.0,
                    'credit': amount < 0.0 and -amount or 0.0,
                }
                # r.line_ids += create_method(dict)
                # r.line_ids = [(0, 0, dict)]
            terms_lines = r.line_ids.filtered(
                lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable'))
            other_lines = r.line_ids.filtered(
                lambda line: line.account_id.account_type not in ('asset_receivable', 'liability_payable'))
            already_exists = r.line_ids.filtered(
                lambda line: line.is_tw_sconto)
            total_balance = sum(other_lines.mapped('balance'))
            total_balance = total_balance + amount
            total_amount_currency = sum(other_lines.mapped('amount_currency'))
            dict1 = {
                'credit': amount < 0.0 and -amount or 0.0,
                'debit': amount > 0.0 and amount or 0.0,
                'name': 'TwSconto',
                'is_tw_sconto': True,
            }
            dict2 = {
                'debit': total_balance < 0.0 and -total_balance or 0.0,
                'credit': total_balance > 0.0 and total_balance or 0.0,
            }
            if terms_lines:
                if already_exists:
                    r.line_ids = [(1, already_exists.id, dict1), (1, terms_lines[0].id, dict2)]
                else:
                    r.line_ids = [(0, 0, dict), (1, terms_lines[0].id, dict2)]
        return super().action_post()


    solare_id = fields.Many2one('sale.order')
    data_fine_lavori = fields.Date()
    data_fine_lavori_text = fields.Char(string="Testo per data fine lavori")
    sconto_tax = fields.Float(string="Sconto %")
    sconto_dis_type = fields.Selection([('fixed', 'Fisso'), ('percent', 'Percentuale')], string="Discount Type",
                                       default="percent")
    sconto_amount = fields.Float(compute='_compute_amount', store=True, string="Importo sconto")
    tw_disc = fields.Float(string="Disc. %")
    tw_dis_type = fields.Selection([('fixed', 'Fisso'), ('percent', 'Percentuale')], string="Discount Type",
                                   default="percent")
    tw_disc_amt = fields.Float(compute='_compute_amount', store=True, )
    after_tw_amt = fields.Float(compute='_compute_amount', store=True, string="Amount")
    so_taxes_id = fields.Many2many('account.tax', 'account_move_total_taxes', 'so_id', 'tax_id',
                                   string='Taxes',
                                   domain=['|', ('active', '=', False), ('active', '=', True)])
    so_tax_after_discount = fields.Float(compute='_compute_amount', store=True, string='Importo IVA',
                                         default=0.0)
    disc_declaration = fields.Char(string="Declaration")
    disc_after_iva = fields.Float(string='Sconto', default=0.0)




class ProductCategory(models.Model):
    _inherit = "product.category"

    name = fields.Char('Name', index='trigram', required=True, translate=True)


class AccountMoaveLine(models.Model):
    _inherit = "account.move.line"

    category_id = fields.Many2one("product.category")
    is_tw_sconto = fields.Boolean(copy=False)


class ProductProduct(models.Model):
    _inherit = "product.template"

    is_add_attachement = fields.Boolean()


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    @api.depends('can_edit_wizard', 'amount', 'line_ids.move_id.amount_residual')
    def _compute_payment_difference(self):
        super()._compute_payment_difference()
        for wizard in self:
            moves = wizard.line_ids.move_id
            if wizard.can_edit_wizard and len(moves) == 1 and wizard.currency_id == moves.currency_id:
                wizard.payment_difference = moves.amount_residual - wizard.amount

    @api.depends('can_edit_wizard', 'source_amount', 'source_amount_currency', 'source_currency_id', 'company_id',
                 'currency_id', 'payment_date', 'line_ids.move_id.amount_residual')
    def _compute_amount(self):
        super()._compute_amount()
        for wizard in self:
            moves = wizard.line_ids.move_id
            if wizard.can_edit_wizard and len(moves) == 1 and wizard.currency_id == moves.currency_id:
                wizard.amount = moves.amount_residual
