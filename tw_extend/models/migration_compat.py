"""Retain business data for fields retired by the Odoo 20 core."""
from odoo import fields, models
from odoo.fields import Domain
from odoo.exceptions import AccessError


class ContactTitle(models.Model):
    _name = 'res.partner.title'
    _description = 'Contact Title'
    _order = 'name'

    name = fields.Char(required=True, translate=True)
    shortcut = fields.Char(translate=True)


class Partner(models.Model):
    _inherit = 'res.partner'

    title = fields.Many2one('res.partner.title', ondelete='restrict')
    mobile = fields.Char(string='Mobile')
    type = fields.Selection(selection_add=[('private', 'Private Address')], ondelete={'private': 'set default'})


class Company(models.Model):
    _inherit = 'res.company'

    mobile = fields.Char(related='partner_id.mobile', readonly=False)


class PartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    acc_number = fields.Char(related='account_number', readonly=False)
    acc_holder_name = fields.Char(related='holder_name', readonly=False)
    sanitized_acc_number = fields.Char(related='sanitized_account_number')


class User(models.Model):
    _inherit = 'res.users'

    pons_private_address_access = fields.Boolean(
        string='Access to private addresses', readonly=True, copy=False,
    )

    def pons_legacy_domain_union(self, domains):
        return list(Domain.OR(Domain(domain) for domain in domains))

    def write(self, values):
        if 'pons_private_address_access' in values and not (
            self.env.su or self.env.user.has_group('base.group_system')
        ):
            raise AccessError('Only administrators can change private address permissions.')
        result = super().write(values)
        if 'pons_private_address_access' in values:
            self.env['ir.access']._clear_caches()
        return result


class WorkEntryType(models.Model):
    _inherit = 'hr.work.entry.type'

    # The source leave types were scoped to a company; Odoo20 merges these
    # types into work-entry types. Keep the original scope and record rules.
    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company,
        ondelete='restrict',
    )


class JournalGroup(models.Model):
    _inherit = 'account.journal.group'

    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company,
        ondelete='restrict',
    )
