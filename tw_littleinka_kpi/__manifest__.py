{
    "name": "Little Inka KPI",
    "summary": "Vendite di tutte le sedi in un'unica dashboard: online (sito e app) e cassa, anche dal telefono",
    "description": """
Little Inka KPI
===============

Ogni sede WooCommerce (child theme Little Inka) invia i suoi ordini a Odoo con una
chiave propria; le vendite in cassa arrivano dal Punto vendita. La dashboard le mette
insieme sede per sede: pezzi venduti per famiglia (Poké, Sushi, Bevande, Dessert…),
fatturato, ordini, scontrino medio, online contro cassa, sito/app/telefono, consegna
e ritiro. Ogni riquadro si tocca per vedere i dettagli.

Version History
---------------
* 20.0.1.0.0: prima versione (sedi con chiave, ricezione ordini, famiglie e categorie,
  analisi vendite e prodotti, dashboard per telefono e computer).
""",
    "version": "20.0.1.0.0",
    "category": "Sales/Point of Sale",
    "author": "ticinoWEB",
    "website": "https://www.ticinoweb.com",
    "license": "LGPL-3",
    "depends": ["point_of_sale"],
    "data": [
        "security/security.xml",
        "security/ir.access.csv",
        "data/family_data.xml",
        "views/kpi_family_views.xml",
        "views/kpi_sede_views.xml",
        "views/kpi_order_views.xml",
        "views/kpi_report_views.xml",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "tw_littleinka_kpi/static/src/dashboard/**/*",
        ],
    },
    "installable": True,
    "application": True,
}
