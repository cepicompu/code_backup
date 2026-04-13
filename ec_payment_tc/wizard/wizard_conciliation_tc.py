# -*- coding: utf-8 -*-#
#############################################################################
#                                                                           #
#Copyright (C) HackSystem, Inc - All Rights Reserved                        #
#Unauthorized copying of this file, via any medium is strictly prohibited   #
#Proprietary and confidential                                               #
#Written by Ing. Harry Alvarez <halvarezg@hacksystem.es>, 2023              #
#                                                                           #
#############################################################################

import re
from odoo import api, fields, models, _
from odoo.exceptions import RedirectWarning, UserError, ValidationError

class ConciliatedPaymentTC(models.TransientModel):
	_name='wizard.conciliation.tc'


	def get_journal_context(self):
		if self.env.context.get('journal_id',False):
			return self.env.context.get('journal_id')
		else:
			return False

	def get_amount_commission_context(self):
		if self.env.context.get('amount_commission',False):
			return self.env.context.get('amount_commission')
		else:
			return 0.00

	def get_amount_retention_context(self):
		if self.env.context.get('amount_retention',False):
			return self.env.context.get('amount_retention')
		else:
			return 0.00

	def get_amount_select_context(self):
		if self.env.context.get('amount_select',False):
			return self.env.context.get('amount_select')
		else:
			return 0.00

	journal_id=fields.Many2one('account.journal','Diario de Pago',default=get_journal_context)
	partner_id=fields.Many2one('res.partner','Proveedor')
	amount_commission = fields.Float("Valor de Comisión", default=get_amount_commission_context)
	amount_retention = fields.Float("Valor Retencion", default=get_amount_retention_context)
	amount_bank = fields.Float("Valor de Banco", )
	have_amount_diff = fields.Boolean("Diferencia")
	amount_diff = fields.Float("Valor Diferencia")
	amount_select = fields.Float("Valor Selecionado", default=get_amount_select_context)


	def validate(self):
		self.generate_payment()


	def get_info_regulation(self,payment_ids):
		objPayment=self.env['account.payment'].browse(payment_ids)

		ref=''
		payment_tc=self.env.context.get('tc_id',False)
		if payment_tc:
			objPaymentTc=self.env['account.payment.tc.cab'].browse(payment_tc)
			ref='Lote: '+objPaymentTc.lote+'\n'

		for line in objPayment:
			if line.reference_tc:
				ref+='Ref.TC.: '+line.reference_tc+'\n'

		return ref

	def generate_payment(self):
		if not self.env.company.account_comision_retention_id:
			raise UserError(_(u'Debe configurar las cuenta de Comisiones de Tarjeta de credito!!'))
		if self.amount_retention:
			if not self.env.company.journal_tc_retention_id:
				raise UserError(_(u'Debe configurar el Diario de Retenciones de Tarjeta de Credito!!'))
		objPaymentTc=None
		payment_tc=self.env.context.get('tc_id',False)
		if payment_tc:
			objPaymentTc=self.env['account.payment.tc.cab'].browse(payment_tc)

		amount_commission = self.amount_commission
		amount_total=0
		for line in objPaymentTc.line_ids:
			if line.select_row:
				amount_total+=line.amount
		if amount_total!=self.amount_select:
			raise UserError(_(u'El monto seleccionado no es igual al monto total de la conciliacion!!'))
		if amount_total - self.amount_retention - self.amount_commission <= 0.00:
			raise UserError(_(u'El monto seleccionado no es suficiente para realizar la conciliacion!!'))
		data_line_ids = []
		account_debit = self.journal_id.default_account_id.id
		if objPaymentTc.journal_conciliation.inbound_payment_method_line_ids:
			account_debit = objPaymentTc.journal_conciliation.inbound_payment_method_line_ids[0].payment_account_id.id
		if objPaymentTc.amount_iva:
			if not self.env.company.account_retention_iva_id:
				raise UserError(_(u'Debe configurar la cuenta de Retencion de IVA!!'))
			data_line_ids.append((0, 0, {'name': "RETENCION IVA",
										 'debit': objPaymentTc.amount_iva,
										 'credit': 0.00,
										 'partner_id': self.partner_id.id,
										 'account_id': self.env.company.account_transit_retention_id.id,
										 'date': objPaymentTc.date_move,
										 'ref': objPaymentTc.description,
										 }))
		if objPaymentTc.amount_renta:
			if not self.env.company.account_retention_renta_id:
				raise UserError(_(u'Debe configurar la cuenta de Retencion de Renta!!'))
			data_line_ids.append((0, 0, {'name': "RETENCION RENTA",
										 'debit': objPaymentTc.amount_renta,
										 'credit': 0.00,
										 'partner_id': self.partner_id.id,
										 'account_id': self.env.company.account_transit_retention_id.id,
										 'date': objPaymentTc.date_move,
										 'ref': objPaymentTc.description,
										 }))

		if amount_commission > 0.00:
			data_line_ids.append((0, 0, {'name': "COMISIONES",
										 'debit': amount_commission,
										 'credit': 0.0,
										 'partner_id': self.partner_id.id,
										 'account_id': self.env.company.account_comision_retention_id.id,
										 'date': objPaymentTc.date_move,
										 'ref': objPaymentTc.description
										 }))
		if len(objPaymentTc.bank_payment_ids):
			for bank_payment in objPaymentTc.bank_payment_ids:
				account_debit = bank_payment.journal_id.default_account_id.id
				data_line_ids.append((0, 0, {'name': bank_payment.journal_id.name,
											 'debit': bank_payment.amount,
											 'credit': 0.00,
											 'partner_id': self.partner_id.id,
											 'account_id': account_debit,
											 'date': objPaymentTc.date_move,
											 'ref': objPaymentTc.description
											 }),)
		else:
			data_line_ids.append((0, 0, {'name': self.journal_id.name,
										 'debit': self.amount_select - self.amount_retention - amount_commission,
										 'credit': 0.00,
										 'partner_id': self.partner_id.id,
										 'account_id': account_debit,
										 'date': objPaymentTc.date_move,
										 'ref': objPaymentTc.description
										 }),)
		for line in objPaymentTc.line_ids:
			if line.select_row:
				data_line_ids.append((0, 0, {'name': line.journal_id.name,
											 'debit':  0.00,
											 'credit': line.amount,
											 'partner_id': self.partner_id.id,
											 'account_id': line.journal_id.default_account_id.id,
											 'date': objPaymentTc.date_move,
											 'ref': objPaymentTc.description
											 }))
				line.state_conciliation_tc = 'conciliated'
				line.payment_rel_tc_id.state_conciliation_tc = 'conciliated'
				line.payment_rel_tc_pos_id.state_conciliation_tc = 'conciliated'

		if abs(self.have_amount_diff):
			if self.amount_diff > 0:
				data_line_ids.append((0, 0, {'name': "Diferencia en Conciliacion",
											 'debit': 0.00,
											 'credit': abs(self.amount_diff),
											 'partner_id': self.partner_id.id,
											 'account_id': objPaymentTc.diff_account_id.id,
											 'date': objPaymentTc.date_move,
											 'ref': objPaymentTc.description,
											 'analytic_distribution': {objPaymentTc.account_analytic_id.id: 100} if objPaymentTc.account_analytic_id else False,
											 }))
			else:
				data_line_ids.append((0, 0, {'name': "Diferencia en Conciliacion",
											 'debit': abs(self.amount_diff),
											 'credit': 0.00,
											 'partner_id': self.partner_id.id,
											 'account_id': objPaymentTc.diff_account_id.id,
											 'date': objPaymentTc.date_move,
											 'ref': objPaymentTc.description,
											 'analytic_distribution': {objPaymentTc.account_analytic_id.id: 100} if objPaymentTc.account_analytic_id else False,
											 }))

		if len(data_line_ids) != 0:
			move_vals = {
				'date': objPaymentTc.date_move,
				'ref': objPaymentTc.name,
				'journal_id': self.journal_id.id,
				'partner_id': self.partner_id.id,
				'move_type': 'entry',
				'line_ids': data_line_ids

			}
			move_id = self.env['account.move'].create(move_vals)
			move_id.action_post()

			if objPaymentTc:
				objPaymentTc.write({'state': 'done', 'move_id': move_id.id})

			for invoice_line in objPaymentTc.invoice_ids:
				if invoice_line.need_create_invoice:
					if not self.env.company.account_comision_retention_id:
						raise UserError(_(u'Debe configurar las cuenta de Comisiones de Tarjeta de credito!!'))
					account_analytic_id = False
					if invoice_line.sale_shop_id:
						if invoice_line.sale_shop_id.project_id:
							account_analytic_id = invoice_line.sale_shop_id.project_id
					invoice_id = self.env['account.move'].create({'ref': objPaymentTc.description,
																  'partner_id': self.partner_id.id,
																  'move_type': 'in_invoice',
																  'invoice_date': invoice_line.invoice_date,
																  'date': invoice_line.invoice_date,
																  'document_type': 'electronic',
																  'electronic_authorization': invoice_line.electronic_authorization,
																  'l10n_latam_document_number': invoice_line.l10n_latam_document_number,
																  'invoice_line_ids': [(0, 0, {'name': "Comision por Tarjeta de Credito",
																							   'account_id':self.env.company.account_comision_invoice_id.id,
																							   'tax_ids': [(6, 0, [self.env.company.account_purchase_tax_id.id])],
																							   'quantity': 1,
																							   'price_unit': invoice_line.amount_without_tax,
																							   'date': invoice_line.invoice_date,
																							   'analytic_distribution': {account_analytic_id.id: 100} if account_analytic_id else False,
																							   })],
																  })
					invoice_id.action_post()
					analytic_distribution = False
					data_line_inovice_ids = []
					for line_invoice in invoice_id.line_ids:
						if line_invoice.analytic_distribution:
							analytic_distribution = line_invoice.analytic_distribution
					data_line_inovice_ids.append((0, 0, {'name': self.partner_id.property_account_receivable_id.name,
														 'debit': invoice_line.amount_total,
														 'credit': 0.00,
														 'partner_id': self.partner_id.id,
														 'account_id': self.partner_id.property_account_payable_id.id,
														 'date': invoice_line.invoice_date,
														 'analytic_distribution': analytic_distribution,
														 }))
					data_line_inovice_ids.append((0, 0, {'name': self.env.company.account_comision_retention_id.name,
														 'debit': 0.00,
														 'credit': invoice_line.amount_total,
														 'partner_id': self.partner_id.id,
														 'account_id': self.env.company.account_comision_retention_id.id,
														 'date': invoice_line.invoice_date,
														 'analytic_distribution': analytic_distribution,
														 }))
					if len(data_line_inovice_ids) != 0:
						move_invoice_vals = {
							'date': invoice_line.invoice_date,
							'ref': "Cruce de Liquidacion de TC: " + str(objPaymentTc.name),
							'journal_id': objPaymentTc.journal_conciliation.id,
							'move_type': 'entry',
							'line_ids': data_line_inovice_ids
						}
						move_invoice_id = self.env['account.move'].create(move_invoice_vals)
						move_invoice_id._post()
						lines = self.env['account.move.line']
						lines += invoice_id.line_ids.filtered(lambda line: line.account_id.id == self.partner_id.property_account_payable_id.id and not line.reconciled)
						lines += move_invoice_id.line_ids.filtered(lambda line: line.account_id.id == self.partner_id.property_account_payable_id.id and not line.reconciled)
						lines.with_context(amount=invoice_line.amount_total).reconcile()
						move_invoice_id._compute_payment_state()

			if objPaymentTc.have_withholding:
				for withhold_line in objPaymentTc.withhold_ids:
					account_analytic_id = False
					if withhold_line.sale_shop_id:
						if withhold_line.sale_shop_id.project_id:
							account_analytic_id = withhold_line.sale_shop_id.project_id
					withhold_id = self.env['account.withhold'].create({'partner_multi_id': self.partner_id.id,
																	   'document_type': 'electronic',
																	   'transaction_type': 'sale',
																	   'tarjeta_credito': True,
																	   'multiple': True,
																	   'creation_date': withhold_line.withhold_date,
																	   'l10n_latam_document_number': withhold_line.l10n_latam_document_number,
																	   'electronic_authorization': withhold_line.electronic_authorization,
																	   })
					self.env['account.withhold.line'].create({'retention_id': withhold_id.id,
															  'description': 'retencion_iva',
															  'tax_base': withhold_line.base_iva,
															  'retention_percentage_manual': withhold_line.percentage_iva,
															  })

					self.env['account.withhold.line'].create({'retention_id': withhold_id.id,
															  'description': 'retencion_renta',
															  'tax_base': withhold_line.base_renta,
															  'retention_percentage_manual': withhold_line.percentage_renta,
															  })
					withhold_id.button_approve()
					if withhold_id.move_id:
						for line in withhold_id.move_id.line_ids:
							line.write({'analytic_distribution': {account_analytic_id.id: 100} if account_analytic_id else False})