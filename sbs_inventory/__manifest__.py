# -*- coding: utf-8 -*-
{
    'name': 'SBS Inventory',
    'version': '19.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': 'Notify configured people before a product lot expires',
    'description': """
SBS Inventory
=============
* Expiry notification is set per company: how many days before the lot expiry date, and who is notified
* A daily check notifies those people when a lot of that company's product is about to expire
* A product with no company follows the company of the stock location
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
        'views/sbs_expiry_notify_config_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
