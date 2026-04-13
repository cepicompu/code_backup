# -*- encoding: utf-8 -*-
from odoo import models, api, fields

import logging
_logger = logging.getLogger(__name__)

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    @api.onchange('pos_payment_method_ids')
    def _check_cash_payment_method(self):
        for config in self:
            if len(config.pos_payment_method_ids.filtered('is_cash_count')) > 1:
                config.pos_payment_method_ids = config.pos_payment_method_ids._origin

    pos_sale_shop_id = fields.Many2one(related='pos_config_id.sale_shop_id', string="Estalecimiento", readonly=False)
    pos_sri_printer_point_id = fields.Many2one(related='pos_config_id.sri_printer_point_id', string="Punto de Emisión", readonly=False)
    pos_to_invoice = fields.Boolean(related='pos_config_id.to_invoice', string="Facturar por Defecto", readonly=False)
    pos_allowed_value_for_no_client = fields.Float(related='pos_config_id.allowed_value_for_no_client',
                                                   string="Valor Máximo Permitido para Consumidor Final", readonly=False)
    pos_allowed_value_for_no_invoice = fields.Float(related='pos_config_id.allowed_value_for_no_invoice',
                                                    string="Valor Máximo Permitido para no facturar", readonly=False)
    pos_blind_closure = fields.Boolean(related='pos_config_id.blind_closure', string="Cierre Ciego", readonly=False)
    pos_blind_closure_attempts = fields.Integer(related='pos_config_id.blind_closure_attempts', string="Intentos de Cierre Ciego", readonly=False)
    pos_ship_later_default_value = fields.Boolean(related='pos_config_id.ship_later_default_value', string="Ship Later by Default", readonly=False)