# -*- coding: utf-8 -*-
{
    'name': 'SBS Inventory',
    'version': '19.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': 'Product brand, country of origin, and lot expiry notices',
    'description': """
SBS Inventory
=============
* Product brand (many2one) and country of origin on the product
* Expiry notification is set per company and per branch: how many days before the lot expiry date, and who is notified
* A daily check notifies those people when stock in that company or branch is about to expire
* A branch uses products and lots of its parent company, and only counts stock in its own locations
    """,
    'author': 'Sygmetiv Business Solutions',
    'website': 'https://sygmetiv.qa',
    'license': 'LGPL-3',
    'depends': [
        'stock',
        'mail',
        'product_expiry',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'data/ir_cron_data.xml',
        'views/product_brand_views.xml',
        'views/product_template_views.xml',
        'views/sbs_expiry_notify_config_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
