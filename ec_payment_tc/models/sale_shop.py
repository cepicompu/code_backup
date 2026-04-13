# -*- coding: utf-8 -*-#
#############################################################################
#                                                                           #
#Copyright (C) HackSystem, Inc - All Rights Reserved                        #
#Unauthorized copying of this file, via any medium is strictly prohibited   #
#Proprietary and confidential                                               #
#Written by Ing. Harry Alvarez <halvarezg@hacksystem.tech>, 2024            #
#                                                                           #
#############################################################################
from odoo.tools.translate import _
from odoo.exceptions import RedirectWarning, UserError, ValidationError
from odoo import models, fields, registry, api
import odoo.addons.decimal_precision as dp
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as DTF
import time
import logging
_logger = logging.getLogger(__name__)

class SaleShopLocalTrade(models.Model):
	_name = 'sale.shop.local.trade'

	bank_id = fields.Many2one('res.bank', string='Banco', domain="[('type_load_tc', '!=', False)]")
	local_trade = fields.Char('Comercio')
	sale_shop_id = fields.Many2one('sale.shop', string='Tienda')


class SaleShop(models.Model):
	_inherit = 'sale.shop'

	local_trade_ids = fields.One2many('sale.shop.local.trade', 'sale_shop_id', string='Codigo de Comercios')

