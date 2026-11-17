"""Keep pre-20 tracking readable while retaining original message bodies."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    cr.execute("""SELECT column_name FROM information_schema.columns
                  WHERE table_schema='public' AND table_name='mail_tracking_value'""")
    columns = {row[0] for row in cr.fetchall()}
    if {'field_type', 'field_desc', 'currency_id'} <= columns:
        cr.execute("""UPDATE mail_tracking_value
                      SET field_info = COALESCE(field_info, '{}'::jsonb)
                          || jsonb_build_object('type', field_type, 'desc', field_desc,
                                                'currency_id', currency_id)
                      WHERE field_type IS NOT NULL""")
        cr.execute("""UPDATE mail_message m SET pons_legacy_tracking=true
                      WHERE EXISTS (SELECT 1 FROM mail_tracking_value t
                                    WHERE t.mail_message_id=m.id AND t.field_type IS NOT NULL)""")
    # Native20 omits child inheritance of a directly rendered inactive root.
    # The Swiss QR layout must be applied to the primary invoice report.
    env = api.Environment(cr, SUPERUSER_ID, {})
    env.ref('account.report_invoice_document').write({'active': True})
