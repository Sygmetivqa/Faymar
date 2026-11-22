# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    sbs_receivable_amount = fields.Monetary(
        string='Receivable Amount',
        compute='_compute_sbs_receivable_amount',
        currency_field='company_currency_id',
        help='Open receivable of this customer in the invoice company: '
             'posted unpaid invoices, minus credit notes and payments.',
    )

    @api.depends('commercial_partner_id', 'company_id', 'move_type')
    def _compute_sbs_receivable_amount(self):
        invoices = self.filtered(
            lambda move: move.move_type == 'out_invoice' and move.commercial_partner_id and move.company_id
        )
        (self - invoices).sbs_receivable_amount = 0.0
        if not invoices:
            return
        amounts = {}
        MoveLine = self.env['account.move.line'].sudo()
        for company in invoices.company_id:
            company_invoices = invoices.filtered(lambda move, company=company: move.company_id == company)
            grouped = MoveLine._read_group(
                domain=[
                    ('partner_id', 'in', company_invoices.commercial_partner_id.ids),
                    ('parent_state', '=', 'posted'),
                    ('company_id', '=', company.id),
                    ('account_id.account_type', '=', 'asset_receivable'),
                    ('reconciled', '=', False),
                ],
                groupby=['partner_id'],
                aggregates=['amount_residual:sum'],
            )
            for partner, residual in grouped:
                if partner:
                    amounts[(company.id, partner.id)] = residual or 0.0
        for move in invoices:
            move.sbs_receivable_amount = amounts.get(
                (move.company_id.id, move.commercial_partner_id.id),
                0.0,
            )
