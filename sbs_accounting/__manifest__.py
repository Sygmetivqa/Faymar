# -*- coding: utf-8 -*-
{
    'name': 'SBS Accounting',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Customer receivable on the customer invoice',
    'description': """
SBS Accounting
==============
* A customer invoice shows the receivable amount still open for that customer in the invoice company
    """,
    'author': 'Sygmetiv Business Solutions',
    'website': 'https://sygmetiv.qa',
    'license': 'LGPL-3',
    'depends': ['account'],
    'data': [
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
