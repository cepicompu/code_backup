# -*- encoding: utf-8 -*-
from odoo import models, api, fields


class PosConfig(models.Model):
    _inherit = 'pos.config'

    @api.onchange('payment_method_ids')
    def _check_cash_payment_method(self):
        for config in self:
            if len(config.payment_method_ids.filtered('is_cash_count')) > 1:
                config.payment_method_ids = config.payment_method_ids._origin

    sale_shop_id = fields.Many2one("sale.shop", string="Estalecimiento")
    sri_printer_point_id = fields.Many2one("sri.printer.point", string="Punto de Emisión")
    to_invoice = fields.Boolean("Facturar por Defecto")
    allowed_value_for_no_client = fields.Float("Valor Máximo Permitido para Consumidor Final", default=50.00)
    allowed_value_for_no_invoice = fields.Float("Valor Máximo Permitido para no facturar", default=4.00)
    blind_closure = fields.Boolean("Cierre Ciego", default=False)
    blind_closure_attempts = fields.Integer("Intentos de Cierre Ciego", default=3)
    ship_later_default_value = fields.Boolean(string="Ship Later by Default", default=False)
