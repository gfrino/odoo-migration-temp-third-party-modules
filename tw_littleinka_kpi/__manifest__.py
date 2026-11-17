{
    "name": "Little Inka KPI",
    "summary": "Vendite di tutte le sedi in un'unica dashboard: online (sito e app) e cassa, anche dal telefono",
    "description": """
Little Inka KPI
===============

Ogni sede WooCommerce (child theme Little Inka) invia i suoi ordini a Odoo con una
chiave propria; le vendite in cassa arrivano dal Punto vendita. La dashboard le mette
insieme sede per sede: pezzi venduti per famiglia (Poké, Sushi, Bevande, Dessert…),
fatturato, ordini, scontrino medio, online contro cassa, sito/app, consegna
e ritiro. Ogni riquadro si tocca per vedere i dettagli.

Version History
---------------
* 20.0.1.0.0: prima versione (sedi con chiave, ricezione ordini, famiglie e categorie,
  analisi vendite e prodotti, dashboard per telefono e computer).
* 20.0.1.0.1: tolto il canale «Telefono»: gli ordini al telefono si battono in cassa.
* 20.0.1.1.0: le aggiunte (extra) restano nella loro famiglia ma non contano nei pezzi; famiglia
  «Accessori» che raccoglie le categorie non riconosciute, così niente resta «Da assegnare»;
  prodotti con famiglia propria (sacchetti e posate venduti dal tasto «Extras»); una categoria
  nuova della cassa prende la famiglia della categoria madre.
* 20.0.1.2.0: filtro delle sedi a scelta multipla (una, alcune o tutte) al posto del menù a tendina.
* 20.0.1.3.0: percentuale di ogni canale e di ogni sede sul totale a schermo (segue periodo e sedi scelte);
  periodo e sedi restano come l'utente li ha lasciati, anche uscendo dalla dashboard; filtro delle sedi
  in alto a destra, sulla riga del titolo.
""",
    "version": "20.0.1.3.0",
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
