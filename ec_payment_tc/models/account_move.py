# -*- coding: utf-8 -*-#
#############################################################################
#                                                                           #
#Copyright (C) HackSystem, Inc - All Rights Reserved                        #
#Unauthorized copying of this file, via any medium is strictly prohibited   #
#Proprietary and confidential                                               #
#Written by Ing. Harry Alvarez <halvarezg@hacksystem.es>, 2024              #
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

class PayemntTcLiqWizardLine(models.TransientModel):
	_name = 'payment.tc.liq.wizard.line'


	account_payment_tc_id = fields.Many2one('account.payment.tc.invoice', string='Liquidacion TC')
	amount_total = fields.Float('Total', related='account_payment_tc_id.amount_total')
	payment_tc_liq_id = fields.Many2one('payment.tc.liq.wizard', string='Liquidacion TC')


class PayemntTcLiqWizard(models.TransientModel):
	_name = 'payment.tc.liq.wizard'

	date = fields.Date('Fecha')
	move_id = fields.Many2one('account.move', string='Move')
	line_ids = fields.One2many('payment.tc.liq.wizard.line', 'payment_tc_liq_id', string='Lineas de Liquidacion TC')

	def payment_with_tc_liq(self):
		if not self.env.company.account_comision_retention_id:
			raise UserError(_(u'Debe configurar las cuenta de Comisiones de Tarjeta de credito!!'))
		for line in self.line_ids:
			data_line_ids = []
			analytic_distribution = False
			for line_invoice in self.move_id.line_ids:
				if line_invoice.analytic_distribution:
					analytic_distribution = line_invoice.analytic_distribution
			data_line_ids.append((0, 0, {'name': self.move_id.partner_id.property_account_receivable_id.name,
										 'debit':line.amount_total,
										 'credit': 0.00,
										 'partner_id': self.move_id.partner_id.id,
										 'account_id': self.move_id.partner_id.property_account_payable_id.id,
										 'date': self.date,
										 'analytic_distribution': analytic_distribution,
										 }))
			data_line_ids.append((0, 0, {'name': self.env.company.account_comision_retention_id.name,
										 'debit': 0.00,
										 'credit': line.amount_total,
										 'partner_id': self.move_id.partner_id.id,
										 'account_id': self.env.company.account_comision_retention_id.id,
										 'date': self.date,
										 'analytic_distribution': analytic_distribution,
										 }))
			if len(data_line_ids) != 0:
				move_vals = {
					'date':  self.date,
					'ref': "Cruce de Liquidacion de TC: " + str(line.account_payment_tc_id.payment_tc_cab_id.name),
					'journal_id': line.account_payment_tc_id.payment_tc_cab_id.journal_conciliation.id,
					'move_type': 'entry',
					'line_ids': data_line_ids
				}
				move_id = self.env['account.move'].create(move_vals)
				move_id._post()
				lines = self.env['account.move.line']
				lines += self.move_id.line_ids.filtered(lambda line: line.account_id.id == self.move_id.partner_id.property_account_payable_id.id and not line.reconciled)
				lines += move_id.line_ids.filtered(lambda line: line.account_id.id == self.move_id.partner_id.property_account_payable_id.id and not line.reconciled)
				lines.with_context(amount=line.amount_total).reconcile()
				line.account_payment_tc_id.write({'state': 'done'})
				move_id._compute_payment_state()
		return

class PaymentTcInvoiceData(models.TransientModel):
	_name = 'payment.tc.invoice.data'

	def _compute_amount_total(self):
		for record in self:
			record.amount_total = sum(line.amount for line in record.lines)
			record.dif = record.invoice_id.amount_total - record.amount_total

	invoice_id = fields.Many2one('account.move', string='Factura')
	lines = fields.One2many('payment.tc.invoice.data.line', 'payment_tc_invoice_data_id', string='Lineas de Factura')
	amount_total = fields.Float('Total', compute='_compute_amount_total')
	dif = fields.Float('Diferencia', compute='_compute_amount_total')

class PaymentTcInvoiceDataLine(models.TransientModel):
	_name = 'payment.tc.invoice.data.line'

	payment_tc_cab_id = fields.Many2one('account.payment.tc.cab', string='Liquidacion TC')
	amount = fields.Float('Monto')
	local_trade = fields.Char('Comercio')
	sale_shop_id = fields.Many2one('sale.shop', string='Tienda')
	payment_tc_invoice_data_id = fields.Many2one('payment.tc.invoice.data', string='Datos de Factura')

class AccountMove(models.Model):
	_inherit='account.move'

	def search_payment_tc(self):
		invoice_tc_ids = self.env['account.payment.tc.invoice'].search([('l10n_latam_document_number','=',self.l10n_latam_document_number)])
		data = []
		if invoice_tc_ids:
			for invoice_tc_id in invoice_tc_ids:
				if invoice_tc_id.payment_tc_cab_id.state == 'done':
					data.append({'local_trade': invoice_tc_id.local_trade,
								 'sale_shop_id': invoice_tc_id.sale_shop_id.id,
								 'amount': invoice_tc_id.amount_total,
								 'payment_tc_cab_id': invoice_tc_id.payment_tc_cab_id.id})
		if data:
			invoice_data_id = self.env['payment.tc.invoice.data'].create({'lines': [(0, 0, x) for x in data],
																		  'invoice_id': self.id})
			return {
				'type': 'ir.actions.act_window',
				'name': 'Datos de Factura',
				'res_model': 'payment.tc.invoice.data',
				'res_id': invoice_data_id.id,
				'view_mode': 'form',
				'view_type': 'form',
				'target': 'new',
			}
		else:
			raise UserError(_('No se encontro ninguna liquidacion de TC para la factura.'))

	def payment_with_tc_liq(self):
		if self.state != 'posted':
			raise UserError(_('Solo se puede realizar pagos con liquidacion de TC en asientos contables confirmados.'))

		invoice_tc_ids = self.env['account.payment.tc.invoice'].search([('l10n_latam_document_number', '=', self.l10n_latam_document_number)])
		data = []
		if invoice_tc_ids:
			for invoice_tc_id in invoice_tc_ids:
				if invoice_tc_id.payment_tc_cab_id.state == 'done':
					data.append({'account_payment_tc_id': invoice_tc_id.id,})
		if data:
			wizard_id = self.env['payment.tc.liq.wizard'].create({'line_ids': [(0, 0, x) for x in data],
																  'move_id': self.id})
		else:
			raise UserError(_('No se encontro ninguna liquidacion de TC para la factura.'))
		return {
			'type': 'ir.actions.act_window',
			'name': 'Pago con Liquidacion de TC',
			'res_model': 'payment.tc.liq.wizard',
			'view_mode': 'form',
			'res_id': wizard_id.id,
			'view_type': 'form',
			'target': 'new',
		}

