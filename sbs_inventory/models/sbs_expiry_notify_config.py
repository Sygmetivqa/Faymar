# -*- coding: utf-8 -*-
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.misc import format_date, formatLang


class SbsExpiryNotifyConfig(models.Model):
    _name = 'sbs.expiry.notify.config'
    _description = 'Expiry Notify Configuration'
    _order = 'company_id, days_before, id'

    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company, ondelete='cascade',
        help='Company or branch this notice applies to. A branch is a company with a parent. '
             'Each company and each branch has its own days and people. '
             'Only stock in that company or branch is checked. '
             'A branch still uses products and lots owned by its parent company.',
    )
    days_before = fields.Integer(
        string='Notify Days Before Expiry', required=True, default=1,
        help='People below are notified this many days before the expiry date on the lot. '
             '1 is the day before expiry. Each person is notified once for that expiry date. '
             'Changing the expiry date sends the notice again.',
    )
    user_ids = fields.Many2many(
        'res.users',
        'sbs_expiry_notify_config_user_rel',
        'config_id',
        'user_id',
        string='Persons to Notify',
        domain="[('share', '=', False), ('company_ids', 'in', company_id)]",
        help='These people receive the expiry notice for lots of this company.',
    )

    @api.depends('company_id', 'days_before', 'user_ids.name')
    def _compute_display_name(self):
        for config in self:
            people = ', '.join(config.user_ids.mapped('name'))
            config.display_name = _(
                '%(company)s — %(days)s day(s) — %(people)s',
                company=config.company_id.name or '',
                days=config.days_before,
                people=people or _('Nobody'),
            )

    @api.constrains('days_before')
    def _check_days_before(self):
        for config in self:
            if config.days_before < 0:
                raise ValidationError(_('Notify days before expiry cannot be negative.'))

    @api.constrains('user_ids')
    def _check_user_ids(self):
        for config in self:
            if not config.user_ids:
                raise ValidationError(_(
                    'Select at least one person to notify for %s.',
                    config.company_id.name or _('this company'),
                ))

    @api.model
    def _cron_notify_product_expiry(self):
        """Notify the people set on a company or branch when its stock reaches the configured day before expiry."""
        configs = self.sudo().search([])
        if not configs:
            return
        Log = self.env['sbs.lot.expiry.notify.log'].sudo()
        Quant = self.env['stock.quant'].sudo()
        Lot = self.env['stock.lot'].sudo()
        for config in configs:
            users = config.user_ids.filtered(lambda user: user.active and not user.share)
            if not users or config.days_before < 0:
                continue
            company = config.company_id
            # A branch stocks products and lots of itself and of its parent companies.
            visible_company_ids = self._sbs_visible_company_ids(company)
            tz_name = self._sbs_tz_name(company)
            today = fields.Date.context_today(self.with_context(tz=tz_name))
            horizon = today + timedelta(days=config.days_before)
            lots = Lot.search([
                ('expiration_date', '>=', self._sbs_utc_bound(tz_name, today, end=False)),
                ('expiration_date', '<=', self._sbs_utc_bound(tz_name, horizon, end=True)),
                ('product_id.company_id', 'in', visible_company_ids),
                ('company_id', 'in', visible_company_ids),
            ])
            if not lots:
                continue
            qty_by_lot = {
                lot.id: qty
                for lot, qty in Quant._read_group(
                    domain=[
                        ('lot_id', 'in', lots.ids),
                        ('quantity', '>', 0),
                        ('location_id.usage', '=', 'internal'),
                        ('location_id.company_id', '=', company.id),
                    ],
                    groupby=['lot_id'],
                    aggregates=['quantity:sum'],
                )
                if lot and qty > 0
            }
            lots = lots.filtered(
                lambda lot: lot.id in qty_by_lot
                and (not lot.product_id.company_id or lot.product_id.company_id.id in visible_company_ids)
            )
            if not lots:
                continue
            existing = Log.search([
                ('config_id', '=', config.id),
                ('lot_id', 'in', lots.ids),
                ('user_id', 'in', users.ids),
            ])
            already = {
                (log.lot_id.id, log.user_id.id)
                for log in existing
                if log.expiration_date == log.lot_id.expiration_date
            }
            for lot in lots:
                expiry_day = self._sbs_expiration_day(lot, tz_name)
                remaining = (expiry_day - today).days
                if remaining < 0 or remaining > config.days_before:
                    continue
                pending = users.filtered(lambda user, lot_id=lot.id: (lot_id, user.id) not in already)
                if not pending:
                    continue
                note = _(
                    '%(company)s: %(product)s, lot %(lot)s, expires on %(date)s. %(days)s day(s) remaining. On hand: %(qty)s %(uom)s.',
                    company=company.display_name,
                    product=lot.product_id.display_name,
                    lot=lot.name,
                    date=format_date(self.env, expiry_day),
                    days=remaining,
                    qty=formatLang(self.env, qty_by_lot[lot.id], dp='Product Unit'),
                    uom=lot.product_uom_id.name or '',
                )
                if remaining == 0:
                    summary = _('Lot %(lot)s expires today', lot=lot.name)
                elif remaining == 1:
                    summary = _('Lot %(lot)s expires tomorrow', lot=lot.name)
                else:
                    summary = _(
                        'Lot %(lot)s expires in %(days)s days',
                        lot=lot.name,
                        days=remaining,
                    )
                for user in pending:
                    activities = lot.activity_schedule(
                        'mail.mail_activity_data_todo',
                        expiry_day,
                        summary,
                        note=note,
                        user_id=user.id,
                    )
                    # Assigning an activity notifies someone else. The scheduler user
                    # still needs the same notice when they are the configured person.
                    if activities and user == self.env.user:
                        activities.action_notify()
                    Log.create({
                        'lot_id': lot.id,
                        'config_id': config.id,
                        'user_id': user.id,
                        'expiration_date': lot.expiration_date,
                        'notified_on': today,
                    })
                    already.add((lot.id, user.id))
                lot.message_post(
                    body=_(
                        '%(note)s Notified: %(people)s.',
                        note=note,
                        people=', '.join(pending.mapped('name')),
                    ),
                    subtype_xmlid='mail.mt_note',
                )

    @api.model
    def _sbs_visible_company_ids(self, company):
        """This company or branch, its parent companies, and shared records.

        Stock locations stay on the configured company itself. Products and lots
        may belong to a parent company and still sit in a branch warehouse.
        """
        if company.parent_path:
            company_ids = [int(part) for part in company.parent_path.split('/') if part]
        else:
            company_ids = company.ids
        return company_ids + [False]

    @api.model
    def _sbs_tz_name(self, company):
        name = company.partner_id.tz or 'UTC'
        try:
            ZoneInfo(name)
        except Exception:
            return 'UTC'
        return name

    @api.model
    def _sbs_utc_bound(self, tz_name, day, end=False):
        clock = time.max if end else time.min
        local = datetime.combine(day, clock, tzinfo=ZoneInfo(tz_name))
        return local.astimezone(ZoneInfo('UTC')).replace(tzinfo=None)

    @api.model
    def _sbs_expiration_day(self, lot, tz_name):
        localized = fields.Datetime.context_timestamp(
            lot.with_context(tz=tz_name),
            lot.expiration_date,
        )
        return localized.date()


class SbsLotExpiryNotifyLog(models.Model):
    _name = 'sbs.lot.expiry.notify.log'
    _description = 'Expiry Notification Log'
    _order = 'notified_on desc, id desc'

    lot_id = fields.Many2one('stock.lot', required=True, ondelete='cascade', index=True)
    config_id = fields.Many2one(
        'sbs.expiry.notify.config', required=True, ondelete='cascade', index=True,
    )
    company_id = fields.Many2one(related='config_id.company_id', store=True, index=True)
    user_id = fields.Many2one('res.users', required=True, ondelete='cascade', index=True)
    expiration_date = fields.Datetime(string='Expiry Date', required=True)
    notified_on = fields.Date(required=True)

    _lot_user_expiry_uniq = models.Constraint(
        'UNIQUE (lot_id, config_id, user_id, expiration_date)',
        'This person was already notified for this lot expiry date.',
    )
