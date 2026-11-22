# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import UserError


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    is_pdc = fields.Boolean(related='journal_id.is_pdc')
    cheque_reference = fields.Char(string='Cheque Number')
    cheque_date = fields.Date(string='Cheque Date')
    cheque_bank = fields.Char(string='Cheque Bank')
    pdc_agent = fields.Char(string='Agent')

    def action_create_payments(self):
        if any(wizard.journal_id.is_pdc for wizard in self):
            return self._action_create_pdc_payments()
        return super().action_create_payments()

    def _action_create_pdc_payments(self):
        """Create draft PDC records; Submit then Issue complete the payment."""
        pdc_payments = self.env['pdc.payment']
        for wizard in self:
            if not wizard.journal_id.is_pdc:
                raise UserError(_('Mixed PDC and non-PDC journals are not supported in one payment.'))
            pdc_payments |= wizard._create_pdc_payment_from_wizard()
        return pdc_payments._get_records_action(name=_('PDC Payments'))

    def _create_pdc_payment_from_wizard(self):
        self.ensure_one()
        if not self.cheque_reference:
            raise UserError(_('Please enter the Cheque Number.'))
        if not self.cheque_date:
            raise UserError(_('Please enter the Cheque Date.'))
        if not self.cheque_bank:
            raise UserError(_('Please enter the Cheque Bank.'))

        moves = self.line_ids.move_id
        invoice_moves = moves.filtered(
            lambda m: m.is_invoice(include_receipts=True)
        )
        if not invoice_moves:
            raise UserError(_('PDC payment is only allowed for invoices and bills.'))
        if len(invoice_moves) > 1:
            raise UserError(_('Register a PDC payment for one invoice or bill at a time.'))

        if self.partner_type == 'customer':
            partner_type = 'customer'
            payment_type = 'receive'
        elif self.partner_type == 'supplier':
            partner_type = 'supplier'
            payment_type = 'send'
        else:
            raise UserError(_('PDC payment requires a customer or vendor.'))

        company = self.company_id
        if payment_type == 'receive' and not company.pdc_receivable_account_id:
            raise UserError(_('Configure the PDC Receivable Account on the company.'))
        if payment_type == 'send' and not company.pdc_payable_account_id:
            raise UserError(_('Configure the PDC Payable Account on the company.'))

        # Draft only — user must enter Submit Date / Issue Date and click the buttons
        pdc_payment = self.env['pdc.payment'].create({
            'partner_id': self.partner_id.id,
            'amount': self.amount,
            'journal_id': self.journal_id.id,
            'bank_id': self.cheque_bank,
            'due_date': self.cheque_date,
            'cheque_reference': self.cheque_reference,
            'agent_id': self.pdc_agent,
            'memo': self.communication,
            'invoice_reference': self.communication,
            'date': self.payment_date or fields.Date.context_today(self),
            'partner_type': partner_type,
            'payment_type': payment_type,
            'company_id': company.id,
            'invoice_ids': [(6, 0, invoice_moves.ids)],
            'status': 'draft',
            'from_payment_register': True,
        })
        invoice_moves.write({'pdc_id': pdc_payment.id})
        return pdc_payment
