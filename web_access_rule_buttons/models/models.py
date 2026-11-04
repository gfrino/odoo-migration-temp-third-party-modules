# Copyright 2016 Camptocamp SA
# Copyright 2026 ticinoWEB
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import models
from odoo.exceptions import ValidationError


class Base(models.AbstractModel):
    _inherit = 'base'

    def check_access_rule_all(self, operations=None):
        """Evaluate model permissions and record domains as the current user."""
        operations = operations or ['read', 'create', 'write', 'unlink']
        if not isinstance(operations, (list, tuple)) or set(operations) - {'read', 'create', 'write', 'unlink'}:
            raise ValidationError(self.env._('Invalid access operation.'))
        return {operation: bool(self.has_access(operation)) for operation in operations}
