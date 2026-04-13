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


class AccountJournal(models.Model):
	_inherit='account.journal'

	credit_card = fields.Boolean("Tarjeta de Credito", default=False)

	payment_method_for_reports = fields.Selection(
		[('efectivo', 'Efectivo'), ('cheque', 'Cheque'), ('retencion', 'Retenciones Venta'),
		 ('tarjeta', 'Tarjeta Crédito'), ('transferencia', 'Transferencia'), ('deposito', 'Depósito'),
		 ('cruce', 'Cruce')], string='Forma de Pago para Reportes', default='efectivo')

