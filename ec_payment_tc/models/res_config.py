# -*- coding: utf-8 -*-#
#############################################################################
#                                                                           #
#Copyright (C) HackSystem, Inc - All Rights Reserved                        #
#Unauthorized copying of this file, via any medium is strictly prohibited   #
#Proprietary and confidential                                               #
#Written by Ing. Harry Alvarez <halvarezg@hacksystem.es>, 2023              #
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

class TcConfigSettings(models.TransientModel):
	_inherit = 'res.config.settings'

	journal_tc_retention_id = fields.Many2one('account.journal', 'Diario Retenciones de Tarjetas de Credito',
											  related="company_id.journal_tc_retention_id",
											  readonly=False)
	account_comision_retention_id = fields.Many2one('account.account',
													u'Cuenta para Comisiones de Tarjeta de Credito',
													related="company_id.account_comision_retention_id",
													readonly=False)
	account_transit_retention_id = fields.Many2one('account.account',u'Cuenta para Transito de Tarjeta de Credito',
												   related="company_id.account_transit_retention_id",
												   readonly=False)
	account_comision_invoice_id = fields.Many2one('account.account', u'Cuenta para Comisiones de Facturas',
												  related="company_id.account_comision_invoice_id",
												  readonly=False)