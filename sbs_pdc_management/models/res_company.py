# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    pdc_receivable_account_id = fields.Many2one(
        'account.account',
        string='PDC Receivable Account',
        domain="[('company_ids', 'in', id)]",
    )
    pdc_payable_account_id = fields.Many2one(
        'account.account',
        string='PDC Payable Account',
        domain="[('company_ids', 'in', id)]",
    )
