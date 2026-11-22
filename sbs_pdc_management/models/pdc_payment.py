# -*- coding: utf-8 -*-
from odoo import models, fields, api, Command, _
from odoo.exceptions import UserError


class PDCPayment(models.Model):
    _name = 'pdc.payment'
    _inherit = ['mail.thread']
    _description = 'PDC Payment'

    name = fields.Char(string='PDC Payment Name', default='New', tracking=True)
    account_id = fields.Many2one('account.account', string='PDC Account')
    journal_id = fields.Many2one(
        'account.journal',
        string='PDC Journal',
        domain="[('company_id', '=', company_id), ('type', 'in', ['bank', 'cash']), ('is_pdc', '=', True)]",
        help='PDC journal used when registering the cheque against receivable/payable.',
    )
    issue_journal_id = fields.Many2one(
        'account.journal',
        string='Issue Journal',
        domain="[('company_id', '=', company_id), ('type', 'in', ['bank', 'cash']), ('is_pdc', '=', False)]",
        help='Final bank/cash journal. On Issue: Bank vs PDC Receivable (customer) or PDC Payable (vendor).',
    )
    partner_id = fields.Many2one('res.partner', string='Party Name')
    amount = fields.Float(string='Amount')
    due_date = fields.Date(string='Cheque Date')
    date = fields.Date(string='Prepared Date', default=fields.Date.context_today)
    cheque_reference = fields.Char(string='Cheque Number')
    agent_id = fields.Char(string='Agent')
    bank_id = fields.Char(string='Cheque Bank')
    memo = fields.Char(string='Reference')
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
    status = fields.Selection(
        [
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('issued', 'Issued'),
            ('bounced', 'Bounced'),
            ('cancelled', 'Cancelled'),
            # Legacy
            ('collect_cash', 'Collect Cash'),
            ('drawn', 'Drawn'),
            ('posted', 'Submit'),
        ],
        string='Status',
        default='draft',
        tracking=True,
    )
    payment_type = fields.Selection(
        [('receive', 'Receive Money'), ('send', 'Send Money')],
        string='Payment Type',
    )
    partner_type = fields.Selection(
        [('customer', 'Customer'), ('supplier', 'Vendor')],
        string='Partner Type',
    )
    invoice_reference = fields.Char(string='Invoice Reference')
    invoice_ids = fields.Many2many(
        'account.move',
        'sbs_invoices_pdc_rel',
        'sbs_pdc_id',
        'sbs_invoice_id',
        string='Invoices',
    )
    move_reference = fields.Many2one('account.move', string='Move Reference')
    move_type = fields.Char(string='Move Type')
    move_id = fields.Many2one('account.move', string='Journal Entry')
    bank_charge = fields.Float(string='Bank Charge')
    charge_debit_account_id = fields.Many2one('account.account', string='Debit Account')
    charge_credit_account_id = fields.Many2one('account.account', string='Credit Account')
    original_move_id = fields.Many2one('account.move', string='Original Journal Entry')
    bounce_move_id = fields.Many2one('account.move', string='Bounce Journal Entry')
    submit_date = fields.Date(string='Submit Date')
    issued_date = fields.Date(string='Issue Date')
    drawn_date = fields.Date(string='Drawn Date')
    collect_date = fields.Date(string='Collect Date')
    description = fields.Char(string='Description')
    due_date_year = fields.Integer(
        string='Year',
        compute='_compute_due_date_year',
        store=True,
    )
    from_payment_register = fields.Boolean(
        string='Created from Pay',
        default=False,
        copy=False,
        help='When set, cheque details stay readonly (entered on Pay).',
    )

    @api.depends('due_date')
    def _compute_due_date_year(self):
        for record in self:
            record.due_date_year = record.due_date.year if record.due_date else 0

    def _check_required_cheque_fields(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_('Kindly select the Partner'))
        if not self.amount:
            raise UserError(_('Kindly enter the Amount'))
        if not self.journal_id:
            raise UserError(_('Kindly select the PDC Journal'))
        if not self.due_date:
            raise UserError(_('Kindly select the Cheque Date'))
        if not self.cheque_reference:
            raise UserError(_('Kindly enter the Cheque Number'))
        if not self.bank_id:
            raise UserError(_('Kindly enter the Cheque Bank'))

    def _get_partner_pdc_accounts(self):
        """Accounts for PDC vs partner AR/AP entry. Returns debit, credit, pdc_account."""
        self.ensure_one()
        company = self.company_id or self.journal_id.company_id
        pdc_cust = company.pdc_receivable_account_id
        pdc_supp = company.pdc_payable_account_id

        if self.payment_type == 'receive':
            if not pdc_cust:
                raise UserError(_('Configure the PDC Receivable Account on the company.'))
            # Dr PDC Receivable, Cr Partner AR
            return pdc_cust.id, self.partner_id.property_account_receivable_id.id, pdc_cust
        if self.payment_type == 'send':
            if not pdc_supp:
                raise UserError(_('Configure the PDC Payable Account on the company.'))
            # Dr Partner AP, Cr PDC Payable
            return self.partner_id.property_account_payable_id.id, pdc_supp.id, pdc_supp
        raise UserError(_('Invalid payment type.'))

    def _get_bank_pdc_accounts(self):
        """Accounts for final Issue Journal entry: Bank vs PDC Rec/Pay."""
        self.ensure_one()
        company = self.company_id or self.journal_id.company_id
        pdc_cust = company.pdc_receivable_account_id
        pdc_supp = company.pdc_payable_account_id
        bank_account = self.issue_journal_id.default_account_id
        if not bank_account:
            raise UserError(_('Configure the default account on the Issue Journal.'))

        if self.payment_type == 'receive':
            if not pdc_cust:
                raise UserError(_('Configure the PDC Receivable Account on the company.'))
            # Dr Bank, Cr PDC Receivable
            return bank_account.id, pdc_cust.id, pdc_cust
        if self.payment_type == 'send':
            if not pdc_supp:
                raise UserError(_('Configure the PDC Payable Account on the company.'))
            # Dr PDC Payable, Cr Bank
            return pdc_supp.id, bank_account.id, pdc_supp
        raise UserError(_('Invalid payment type.'))

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        pdc_type = self.env.context.get('pdc_type')
        if pdc_type == 'receive':
            res.update({
                'payment_type': 'receive',
                'partner_type': 'customer',
            })
        elif pdc_type == 'payable':
            res.update({
                'payment_type': 'send',
                'partner_type': 'supplier',
            })
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            partner_type = vals.get('partner_type')
            if not partner_type:
                pdc_type = self.env.context.get('pdc_type')
                if pdc_type == 'receive':
                    partner_type = 'customer'
                    vals['partner_type'] = partner_type
                elif pdc_type == 'payable':
                    partner_type = 'supplier'
                    vals['partner_type'] = partner_type

            if not vals.get('name') or vals.get('name') == 'New':
                if partner_type == 'customer':
                    vals['name'] = self.env['ir.sequence'].next_by_code('customer.pdc.payment') or 'New'
                elif partner_type == 'supplier':
                    vals['name'] = self.env['ir.sequence'].next_by_code('supplier.pdc.payment') or 'New'
        return super().create(vals_list)

    def action_pdc_submit(self):
        """
        Submit (create payment entry on PDC journal):
        Customer: Dr PDC Receivable, Cr Account Receivable → reconcile invoice
        Vendor:   Dr Account Payable, Cr PDC Payable → reconcile bill
        """
        for record in self:
            if record.status != 'draft':
                raise UserError(_('Only draft PDC records can be submitted.'))
            record._check_required_cheque_fields()
            if not record.submit_date:
                raise UserError(_('Please enter the Submit Date before clicking Submit.'))

            pdc_debit, pdc_credit, pdc_account = record._get_partner_pdc_accounts()
            record.account_id = pdc_account

            pdc_entry = self.env['account.move'].create({
                'partner_id': record.partner_id.id,
                'journal_id': record.journal_id.id,
                'date': record.submit_date,
                'ref': record.invoice_reference or record.memo or record.name,
                'pdc_id': record.id,
                'move_type': 'entry',
                'line_ids': [
                    Command.create({
                        'account_id': pdc_debit,
                        'name': record.cheque_reference or 'PDC Payment',
                        'debit': record.amount,
                        'credit': 0.0,
                        'partner_id': record.partner_id.id,
                        'date_maturity': record.due_date,
                    }),
                    Command.create({
                        'account_id': pdc_credit,
                        'name': record.cheque_reference or 'PDC Payment',
                        'debit': 0.0,
                        'credit': record.amount,
                        'partner_id': record.partner_id.id,
                        'date_maturity': record.due_date,
                    }),
                ],
            })
            pdc_entry.action_post()
            record.original_move_id = pdc_entry
            record.move_id = pdc_entry

            # Reconcile so invoice/bill becomes paid or in_payment
            partner_account = pdc_credit if record.payment_type == 'receive' else pdc_debit
            for invoice in record.invoice_ids:
                invoice_aml = invoice.line_ids.filtered(
                    lambda r: r.account_id.id == partner_account and not r.reconciled
                )
                pdc_aml = pdc_entry.line_ids.filtered(
                    lambda r: r.account_id.id == partner_account and not r.reconciled
                )
                if invoice_aml and pdc_aml:
                    (invoice_aml + pdc_aml).reconcile()

            record.status = 'submitted'
        return True

    def action_issue(self):
        """
        Issuance on bank (Issue) journal:
        Customer: Dr Bank, Cr PDC Receivable
        Vendor:   Dr PDC Payable, Cr Bank
        Then reconcile PDC receivable/payable with the submit entry.
        """
        for record in self:
            if record.status not in ('submitted', 'posted', 'drawn'):
                raise UserError(_('Submit the cheque before issuing it.'))
            if not record.issued_date:
                raise UserError(_('Please enter the Issue Date before clicking Issue.'))
            if not record.issue_journal_id:
                raise UserError(_('Please select the Issue Journal (bank journal) before clicking Issue.'))
            if record.issue_journal_id.is_pdc:
                raise UserError(_('Issue Journal must be a bank/cash journal, not a PDC journal.'))
            if record.submit_date and record.issued_date < record.submit_date:
                raise UserError(_('Issue Date cannot be before Submit Date.'))
            if not record.original_move_id:
                raise UserError(_('Missing submit journal entry. Submit the cheque first.'))

            bank_debit, bank_credit, pdc_account = record._get_bank_pdc_accounts()
            record.account_id = pdc_account

            bank_entry = self.env['account.move'].create({
                'partner_id': record.partner_id.id,
                'journal_id': record.issue_journal_id.id,
                'date': record.issued_date,
                'ref': record.invoice_reference or record.memo or record.name,
                'pdc_id': record.id,
                'move_type': 'entry',
                'line_ids': [
                    Command.create({
                        'account_id': bank_debit,
                        'name': record.cheque_reference or 'PDC Issue',
                        'debit': record.amount,
                        'credit': 0.0,
                        'partner_id': record.partner_id.id,
                    }),
                    Command.create({
                        'account_id': bank_credit,
                        'name': record.cheque_reference or 'PDC Issue',
                        'debit': 0.0,
                        'credit': record.amount,
                        'partner_id': record.partner_id.id,
                    }),
                ],
            })
            bank_entry.action_post()
            record.move_id = bank_entry

            # Reconcile PDC receivable/payable between submit and issue entries
            pdc_acc_id = pdc_account.id
            submit_pdc_line = record.original_move_id.line_ids.filtered(
                lambda r: r.account_id.id == pdc_acc_id and not r.reconciled
            )
            issue_pdc_line = bank_entry.line_ids.filtered(
                lambda r: r.account_id.id == pdc_acc_id and not r.reconciled
            )
            if submit_pdc_line and issue_pdc_line:
                (submit_pdc_line + issue_pdc_line).reconcile()

            record.status = 'issued'
        return True

    def action_bounced(self):
        for record in self:
            for invoice in record.invoice_ids:
                invoice.line_ids.remove_move_reconcile()

            company = record.journal_id.company_id
            pdc_cust_acc = company.pdc_receivable_account_id
            pdc_supplier_acc = company.pdc_payable_account_id

            if record.payment_type == 'receive':
                debit_account = record.partner_id.property_account_receivable_id.id
                credit_account = pdc_cust_acc.id if pdc_cust_acc else False
                record.account_id = pdc_cust_acc
            else:
                credit_account = record.partner_id.property_account_payable_id.id
                debit_account = pdc_supplier_acc.id if pdc_supplier_acc else False
                record.account_id = pdc_supplier_acc

            if record.bank_charge and (
                not record.charge_credit_account_id or not record.charge_debit_account_id
            ):
                raise UserError(_('Please choose bank charge debit and credit account to continue...'))

            original_entry = record.original_move_id or record.move_id
            line_ids = [
                Command.create({
                    'account_id': debit_account,
                    'name': 'PDC Payment Bounce',
                    'debit': record.amount,
                    'credit': 0.0,
                    'partner_id': record.partner_id.id,
                }),
                Command.create({
                    'account_id': credit_account,
                    'name': 'PDC Payment Bounce',
                    'debit': 0.0,
                    'credit': record.amount,
                    'partner_id': record.partner_id.id,
                }),
            ]
            if record.bank_charge:
                line_ids.extend([
                    Command.create({
                        'account_id': record.charge_debit_account_id.id,
                        'name': 'Bank Charge',
                        'debit': record.bank_charge,
                        'credit': 0.0,
                        'partner_id': record.partner_id.id,
                    }),
                    Command.create({
                        'account_id': record.charge_credit_account_id.id,
                        'name': 'Bank Charge',
                        'debit': 0.0,
                        'credit': record.bank_charge,
                        'partner_id': record.partner_id.id,
                    }),
                ])

            journal = record.issue_journal_id or record.journal_id
            journal_entry = self.env['account.move'].create({
                'partner_id': record.partner_id.id,
                'journal_id': journal.id,
                'ref': _('Reversal of %s') % (original_entry.name or _('PDC Entry')),
                'pdc_id': record.id,
                'reversed_entry_id': original_entry.id if original_entry else False,
                'move_type': 'entry',
                'line_ids': line_ids,
            })
            journal_entry.action_post()
            record.bounce_move_id = journal_entry
            record.status = 'bounced'
        return True

    def action_pdc_cancel(self):
        for record in self:
            journal_entries = self.env['account.move'].search([
                ('pdc_id', '=', record.id),
                ('move_type', '=', 'entry'),
            ])
            if not journal_entries:
                raise UserError(_('No related PDC journal entries found'))

            for journal_entry in journal_entries:
                if journal_entry.state == 'posted':
                    journal_entry.with_context(from_pdc_bounce=True).button_draft()
                    journal_entry.button_cancel()
                elif journal_entry.state == 'draft':
                    journal_entry.button_cancel()
            record.status = 'cancelled'

    def action_see_journal_entry(self):
        self.ensure_one()
        return {
            'name': _('Journal Entries'),
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'res_model': 'account.move',
            'domain': [('pdc_id', '=', self.id)],
            'target': 'current',
        }
