# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    is_pdc = fields.Boolean(
        string='PDC Journal',
        help='If enabled, payments registered with this journal create a PDC '
             'instead of a normal payment. Customer invoices go to PDC Receivable; '
             'vendor bills go to PDC Payable.',
    )

    @api.onchange('type')
    def _onchange_type_clear_is_pdc(self):
        if self.type not in ('bank', 'cash'):
            self.is_pdc = False
