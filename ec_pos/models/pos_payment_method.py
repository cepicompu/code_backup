# -*- encoding: utf-8 -*-
from odoo import models, fields

class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    x_ask_reference = fields.Boolean(string='Solicitar Referencia', default=False)
    x_ask_lote_auth = fields.Boolean(string='Solicitar Lote y Autorización', default=False)
    x_surcharge_percentage = fields.Float(string='Porcentaje de Recargo')
    x_surcharge_product_id = fields.Many2one('product.product', string='Producto de Recargo')
