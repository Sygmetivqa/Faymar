# -*- coding: utf-8 -*-
from odoo import models, fields, Command, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    pdc_id = fields.Many2one('pdc.payment', string='PDC Id')

    def js_assign_outstanding_line(self, line_id):
        lines = self.env['account.move.line'].browse(line_id)
        pdc = lines.move_id.pdc_id
        if pdc:
            pdc.write({'invoice_ids': [Command.link(move_id) for move_id in self.ids]})
        return super().js_assign_outstanding_line(line_id)

    def action_see_pdc_entry(self):
        self.ensure_one()
        return {
            'name': _('PDC Entries'),
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'res_model': 'pdc.payment',
            'domain': ['|', ('invoice_ids', 'in', self.id), ('id', '=', self.pdc_id.id)],
            'target': 'current',
        }

    def button_draft(self):
        for rec in self:
            if rec.move_type == 'entry' and rec.pdc_id and not self.env.context.get('from_pdc_bounce'):
                raise UserError(_('Kindly cancel the entry from PDC record'))
        return super().button_draft()
