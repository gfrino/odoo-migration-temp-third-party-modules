"""Display preserved pre-20 tracking without rewriting original message bodies."""
from odoo import fields, models
from odoo.tools import format_amount, format_date, format_datetime, formatLang


class MailMessage(models.Model):
    _inherit = 'mail.message'

    pons_legacy_tracking = fields.Boolean(readonly=True, copy=False)

    def _pons_tracking_body(self, viewer=None, free_access=False):
        self.ensure_one()
        if not self.pons_legacy_tracking:
            return self.body
        # Tracking is admin-only storage. The native filter enforces access to
        # each original field before its old/new values reach the client.
        trackings = self.sudo().tracking_value_ids
        if free_access:
            trackings = trackings._filter_free_field_access()
        else:
            trackings = trackings._filter_has_field_access(self.with_user(viewer).env if viewer else self.env)
        values = []
        for tracking in trackings:
            info = tracking.field_info or {}
            field = tracking.field_id
            kind = info.get('type') or field.ttype
            def display(prefix):
                if kind in ('many2one', 'selection', 'char', 'many2many', 'one2many'):
                    return tracking[prefix + '_value_char'] or ''
                if kind in ('text', 'html'):
                    return tracking[prefix + '_value_text'] or ''
                if kind == 'boolean':
                    return self.env._('Yes') if tracking[prefix + '_value_integer'] else self.env._('No')
                if kind in ('date', 'datetime'):
                    value = tracking[prefix + '_value_datetime']
                    return (format_date(self.env, value.date()) if kind == 'date' else format_datetime(self.env, value)) if value else ''
                if kind == 'integer':
                    return formatLang(self.env, tracking[prefix + '_value_integer'], digits=0)
                value = tracking[prefix + '_value_float']
                if kind == 'monetary':
                    currency = self.env['res.currency'].browse(info.get('currency_id')).exists() or self.env.company.currency_id
                    return format_amount(self.env, value, currency)
                return formatLang(self.env, value)
            values.append({'field_label': info.get('desc') or field.field_description or '',
                           'old_value': display('old'), 'new_value': display('new')})
        return self.env['mail.thread']._message_compute_body_with_trackings(self.body, values) if values else self.body

    def _store_message_fields(self, res, **kwargs):
        super()._store_message_fields(res, **kwargs)
        res.remove('body')
        viewer = res.target_user()
        res.attr('body', value=lambda message: message._pons_tracking_body(
            viewer=viewer, free_access=not viewer,
        ))
