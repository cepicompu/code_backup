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


class ResBank(models.Model):
	_inherit = 'res.bank'

	type_load_tc = fields.Selection([('diners','DINERS CLUB'),
									 ('guayaquil','BANCO GUAYAQUIL'),
									 ('bolivariano', 'BANCO BOLIVARIANO'),],
									string="Tipo de Carga TC a Bancos",)
	partner_id = fields.Many2one('res.partner', string='Proveedor', required=False, readonly=False)