{
    'name': 'Offerta light',
    'summary': 'Preventivi standard accanto alle offerte Solare',
    'version': '20.0.1.0.6',
    'author': 'ticinoWEB',
    'license': 'LGPL-3',
    'depends': ['tw_extend', 'sale_management'],
    'data': ['views/sale_order_views.xml', 'views/light_templates.xml', 'views/mail_offer_report.xml'],
    'assets': {'web.assets_backend': ['tw_sale_offer_light/static/src/js/light_templates.js']},
    'installable': True,
    'application': False,
}
