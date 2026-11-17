# Copyright 2026 ticinoWEB
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
from odoo import fields, models


class MailMessage(models.Model):
    _inherit = 'mail.message'

    tw_legacy_tracking_payload = fields.Json(
        string='Imported legacy tracking', copy=False, groups='base.group_system')

    def _tw_legacy_chatter_body(self):
        self.ensure_one()
        self = self.sudo(False)
        self.check_access('read')
        if not self.env.user._is_internal():
            return self.body
        # The native tracking table is also system-only. Read the imported payload
        # only for an accessible message, then apply each field's current access.
        payload = self.sudo().tw_legacy_tracking_payload or []
        visible = []
        for value in payload:
            model_name = value.get('model')
            field_name = value.get('field_name')
            if model_name not in self.env:
                continue
            model = self.env[model_name]
            field = model._fields.get(field_name)
            if field:
                if not model.has_access('read') or not model.has_field_access(field, 'read'):
                    continue
            elif not self.env.is_system():
                continue
            visible.append(value)
        return self.env['mail.thread']._message_compute_body_with_trackings(
            self.body, visible) if visible else self.body

    def _store_message_fields(self, res, **kwargs):
        super()._store_message_fields(res, **kwargs)
        # Do not prepare private tracking for a broadcast or a different user.
        if res.is_for_current_user() and res.is_for_internal_users():
            res.attr('body', value=lambda message: message._tw_legacy_chatter_body(),
                     predicate=lambda message: bool(message.sudo().tw_legacy_tracking_payload))
