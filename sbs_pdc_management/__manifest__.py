# -*- coding: utf-8 -*-
{
    'name': 'SBS PDC Management',
    'version': '19.0.1.6.0',
    'category': 'Accounting/Accounting',
    'summary': 'Post Dated Cheque (PDC) management',
    'description': """
Post Dated Cheque management for customer and vendor cheques.

* Pay with a PDC journal creates a draft PDC (cheque fields readonly)
* Submit (PDC journal): Account Receivable/Payable vs PDC Receivable/Payable → reconcile invoice
* Issue (bank journal): PDC Receivable/Payable vs Bank account
    """,
    'author': 'Sygmetiv Business Solutions',
    'website': 'https://sygmetiv.qa',
    'license': 'LGPL-3',
    'depends': ['account', 'accountant', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'security/pdc_security.xml',
        'data/sequence.xml',
        'views/account_journal_views.xml',
        'views/pdc_payments.xml',
        'views/pdc_account_config.xml',
        'views/account_move.xml',
        'wizard/account_payment_register_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
