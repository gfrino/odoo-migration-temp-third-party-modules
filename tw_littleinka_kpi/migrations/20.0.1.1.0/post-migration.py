from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Additions stop counting as pieces, «Accessori» collects the rest: nothing stays «Da assegnare»."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    families = env["tw.littleinka.kpi.family"]
    categories = env["tw.littleinka.kpi.category"]

    accessories = env.ref("tw_littleinka_kpi.family_accessories", raise_if_not_found=False)
    if accessories and not families._fallback():
        accessories.is_fallback = True

    # The «Extras» of the till are additions to a poké (base, topping, proteins…).
    additions = categories.search(["|", "|", ("key", "like", "extra"), ("key", "like", "supplement"), ("key", "like", "aggiunt")])
    additions.count_pieces = False
    poke = env.ref("tw_littleinka_kpi.family_poke", raise_if_not_found=False)
    if poke:
        additions.filtered(lambda category: not category.family_id).family_id = poke

    categories.search([("family_id", "=", False)]).action_apply_keywords()
    # Bags and cutlery sold from the «Extras» button go to their own family.
    env["tw.littleinka.kpi.product"]._refresh()
