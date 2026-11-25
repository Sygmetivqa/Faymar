# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductBrand(models.Model):
    _name = 'product.brand'
    _description = 'Product Brand'
    _order = 'name, id'

    name = fields.Char(string='Brand', required=True, translate=True, index=True)
    active = fields.Boolean(default=True)
    description = fields.Text(translate=True)
