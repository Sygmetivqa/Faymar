# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    brand_id = fields.Many2one(
        'product.brand',
        string='Brand',
        index=True,
        tracking=True,
        help='Brand of this product.',
    )
    country_of_origin_id = fields.Many2one(
        'res.country',
        string='Country of Origin',
        tracking=True,
        help='Country where this product was made or grown.',
    )
