# Copyright 2019 Creu Blanca
# Copyright 2026 ticinoWEB
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import models
from odoo.exceptions import ValidationError


class Base(models.AbstractModel):
    _inherit = 'base'

    def get_record_direct_childs_parents(self, options, domain=None):
        """Navigate a hierarchy without elevating access or exposing private fields."""
        field = options.get('child_selection_field', 'display_name')
        if not isinstance(field, str) or field.startswith('_') or field not in self._fields:
            raise ValidationError(self.env._('Invalid hierarchy label field.'))
        if self._parent_name not in self._fields:
            return {'childs': [], 'parents': []}
        if self:
            self.ensure_one()
            self.check_access('read')
        parents, seen = [], set()
        parent = self
        while parent and parent.id not in seen:
            parent.check_access('read')
            seen.add(parent.id)
            parents.append((parent.id, str(parent[field] or '')))
            parent = parent[self._parent_name]
        children = self.search([(self._parent_name, '=', self.id or False)] + (domain or []), limit=100)
        return {
            'childs': [(child.id, str(child[field] or '')) for child in children],
            'parents': list(reversed(parents)),
        }
