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


class ResCompany(models.Model):
	_inherit='res.company'

	account_advance_tc = fields.Many2one('account.account','Cuenta de Anticipo TC',required=False)



class ResConfig(models.TransientModel):
	_inherit='res.config.settings'

	account_advance_tc = fields.Many2one('account.account','Cuenta de Anticipo TC',required=False,related="company_id.account_advance_tc",readonly=False)


class AccountPaymentTcWizard(models.Model):
	_name = 'account.payment.tc.wizard'
	_description = 'Wizard para la conciliación de pagos con TC'


	data_file = fields.Binary(string="Upload File")
	filename = fields.Char(string="File Name")
	process = fields.Boolean(string="Procesado", default=False)
	results = fields.Text(string="Resultados", readonly=True)
	account_payment_tc_id = fields.Many2one('account.payment.tc.cab', 'Conciliación TC')
	bank_id = fields.Many2one('res.bank', 'Banco', domain="[('type_load_tc', '!=', False)]")
	journal_id = fields.Many2one('account.journal', 'Diario de Pago', domain="[('type', '=', 'bank')]")
	type_load_tc = fields.Selection(related='bank_id.type_load_tc', string="Tipo de Carga TC a Bancos", readonly=True)

	def load_file(self):
		import base64
		import xlrd
		import io
		self.ensure_one()
		
		# Check file extension or try to open as Excel first
		try:
			file_content = base64.b64decode(self.data_file)
			# Try to open as Excel (xls or xlsx)
			# Using xlrd for xls, but for xlsx we might need openpyxl or pandas. 
			# Since we saw 'pandas' available in the environment (used in analysis script), let's use pandas if possible or fallback to standard libs.
			# However, standard Odoo might not have pandas. We should try xlrd (good for xls) or openpyxl (good for xlsx).
			# Let's try to assume it's Excel if we can read it.
			
			# NOTE: Using pandas as it was used in analysis step successfully.
			import pandas as pd
			df = pd.read_excel(io.BytesIO(file_content))
			is_excel = True
		except Exception:
			is_excel = False

		cont_found = 0
		payment_data = []
		results = []
		
		if is_excel:
			# Excel logic
			for index, row in df.iterrows():
				try:
					# Mapping columns
					# LOTE can be int or string in dataframe
					lote = str(row.get('LOTE', '')).replace('.0', '')
					autorizacion = str(row.get('AUTORIZACION', '')).replace('.0', '')
					valor_total = float(row.get('VALOR TOTAL', 0.0))
					
					# Retentions and Commissions
					ret_iva = float(row.get('RET. IVA', 0.0))
					ret_fuente = float(row.get('RET. FUENTE', 0.0))
					comision = float(row.get('COMISION', 0.0))
					
					# Authorization logic: Excel has full auth, but sometimes systems truncate or match differently.
					# The analysis showed POS payments might have full code. 
					# The existing text logic matched last digits. Let's try exact match first, then fuzzy if needed.
					# But based on plan, we propagate 'auth_tc' directly from POS input.
					
					# Search payments
					# We need to match by Auth AND Amount? Or just specific fields?
					# Existing logic matched Auth and Amount.
					
					payments = self.env['account.payment'].search([
						('is_credit_card', '=', True),
						('state_conciliation_tc', '=', 'not_conciliate'),
						('state', '=', 'posted'),
						('auth_tc', '=', autorizacion),
						# ('amount', '=', round(valor_total, 2)) # Amount matching can be tricky due to float
					])
					
					# Filter by amount python side to avoid float errors in search or use range
					payments = payments.filtered(lambda p: abs(p.amount - round(valor_total, 2)) < 0.02)

					found_payment = False
					if len(payments) != 0:
						for payment in payments:
							payment_data.append(payment.id)
							found_payment = True
					
					if not found_payment:
						results.append(f"No se encontró el pago con autorización: {autorizacion} y monto: {valor_total} (Lote: {lote})")
					else:
						# If found, select them in lines
						for line_payment in self.account_payment_tc_id.line_ids:
							if line_payment.payment_rel_tc_id.id in payment_data:
								line_payment.write({'select_row': True})
						cont_found += 1
						
						# Update CAB totals for mapped Retentions/Commissions if this row matches
						# Note: One Excel row = One Transaction.
						# We should accumulate these values to the header if they are not already set?
						# Or does the wizard assume we sum these from the found payments?
						# The model has 'amount_iva', 'amount_renta', 'amount_commission' on the CAB model.
						# We should accumulate them here from the Excel rows that we successfully MATCHED.
						
						if found_payment:
							self.account_payment_tc_id.amount_iva += ret_iva
							self.account_payment_tc_id.amount_renta += ret_fuente
							self.account_payment_tc_id.amount_commission += comision

				except Exception as e:
					results.append(f"Error procesando fila {index}: {str(e)}")
					
		else:
			# Fallback to existing text logic
			datas = base64.decodestring(self.data_file).decode(encoding="latin1").split('\n')
			cont = 0
			for data in datas:
				found_payment = False
				if cont == 0:
					cont += 1
					continue
				if len(data) < 139: # Safety check
					continue
				recap = data[4:18]
				vale = data[18:32]
				autorizacion_raw = data[46:60]
				autorizacion = autorizacion_raw[8:]
				total_str = data[124:139]
				total_clean = total_str.lstrip("0")
				if not total_clean:
					continue
				decimal = total_clean[len(total_clean) - 2:]
				entero = total_clean[:len(total_clean) - 2]
				if not entero: entero = "0"
				total = float(entero + "." + decimal)
				
				payments = self.env['account.payment'].search([('is_credit_card', '=', True),
															   ('state_conciliation_tc', '=', 'not_conciliate'),
															   ('state', '=', 'posted'), ('auth_tc', '=', autorizacion),
															   ('amount', '=', round(total, 2))
															   ])
				if len(payments) != 0:
					for payment in payments:
						payment_data.append(payment.id)
						found_payment = True

				if not found_payment:
					results.append("No se encontró el pago con autorización: " + autorizacion + " y monto: " + str(total))
				else:
					for line_payment in self.account_payment_tc_id.line_ids:
						if line_payment.payment_rel_tc_id.id in payment_data:
							line_payment.write({'select_row': True})
				if found_payment:
					cont_found += 1

		results_str = ""
		if cont_found != 0:
			results_str = "Se encontraron " + str(cont_found) + " pagos"
			results.append(results_str)
		for result in results:
			if results_str == "":
				results_str = result
			else:
				results_str = results_str + "\n"
				results_str = results_str + result
		self.process = True
		self.results = results_str
		return {
			'type': 'ir.actions.act_window',
			'res_model': 'account.payment.tc.wizard',
			'view_mode': 'form',
			'view_type': 'form',
			'res_id': self.id,
			'views': [(False, 'form')],
			'target': 'new',
		}

class AccountPaymentTcFilesDetails(models.Model):
	_name = 'account.payment.tc.files.details'

	date = fields.Date('Fecha')
	bin = fields.Char('BIN')
	lote = fields.Char('Lote')
	referencia = fields.Char('Referencia')
	autorizacion = fields.Char('Autorización')
	amount = fields.Float('Monto')
	amount_net = fields.Float('Monto Neto')
	amount_pay = fields.Float('Monto Acreditado')
	amount_iva = fields.Float('IVA')
	amount_renta = fields.Float('Renta')
	amount_commission = fields.Float('Comisión')
	local_trade = fields.Char('Comercio Local')
	sale_shop_id = fields.Many2one('sale.shop', 'Establecimiento de Venta')
	found = fields.Boolean('Encontrado')
	files_id = fields.Many2one('account.payment.tc.files', 'Archivo')
	l10n_latam_document_number = fields.Char('Número de Factura')

class AccountPaymentTcFiles(models.Model):
	_name = 'account.payment.tc.files'

	def view_data(self):
		return {
			'name': _('Detalles'),
			'type': 'ir.actions.act_window',
			'res_model': 'account.payment.tc.files',
			'view_mode': 'form',
			'view_type': 'form',
			'res_id': self.id,
		}

	def unlink(self):
		for rec in self:
			bank_payment = self.env['account.payment.bank.payment'].search([('file_id', '=', rec.id)])
			if bank_payment:
				bank_payment.unlink()
			invoice_payment = self.env['account.payment.tc.invoice'].search([('file_id', '=', rec.id)])
			if invoice_payment:
				invoice_payment.unlink()
			withhold_payment = self.env['account.payment.tc.withhold'].search([('file_id', '=', rec.id)])
			if withhold_payment:
				withhold_payment.unlink()
				self.payment_tc_cab_id.have_withholding = False
		res = super().unlink()
		return res

	name = fields.Char('Nombre', required=True)
	date = fields.Date('Fecha de Carga', default=fields.Date.today)
	payment_tc_cab_id = fields.Many2one('account.payment.tc.cab', 'Conciliación TC')
	line_details = fields.One2many('account.payment.tc.files.details', 'files_id', 'Detalles')

class AccountPaymentBankPayment(models.Model):
	_name = 'account.payment.bank.payment'
	_rec_name = 'number_liq'

	name_code_bank = fields.Char('Código de Banco')
	journal_id = fields.Many2one('account.journal', 'Diario')
	amount = fields.Float('Monto')
	number_liq = fields.Char('Número de Liquidación')
	payment_tc_cab_id = fields.Many2one('account.payment.tc.cab', 'Conciliación TC')
	local_trade = fields.Char('Comercio Local')
	sale_shop_id = fields.Many2one('sale.shop', 'Establecimiento de Venta')
	file_id = fields.Many2one('account.payment.tc.files', 'Archivo')

class AccountPaymentTcInvoice(models.Model):
	_name = 'account.payment.tc.invoice'
	_rec_name = 'l10n_latam_document_number'

	@api.model
	def fill_padding(self, number, padding):
		return str(number).rjust(padding, '0')

	@api.onchange('l10n_latam_document_number')
	def complete_number(self):
		if self.l10n_latam_document_number:
			res = self.l10n_latam_document_number
			number = self.l10n_latam_document_number.split('-')
			if number:
				if len(number) == 3:
					try:
						seq = self.fill_padding(int(number[2]), 9)
						establecimiento = self.fill_padding(int(number[0]), 3)
						emision = self.fill_padding(int(number[1]), 3)
						res = "%s-%s-%s" % (establecimiento, emision, seq)
					except:
						res = number
				self.l10n_latam_document_number = res

	name_code = fields.Char('Código')
	invoice_date = fields.Date('Fecha de Factura')
	l10n_latam_document_number = fields.Char('Número de Documento')
	electronic_authorization = fields.Char('Autorización Electrónica')
	amount_without_tax = fields.Float('Monto sin IVA')
	amount_total = fields.Float('Monto')
	payment_tc_cab_id = fields.Many2one('account.payment.tc.cab', 'Conciliación TC')
	file_id = fields.Many2one('account.payment.tc.files', 'Archivo')
	move_id = fields.Many2one('account.move', 'Asiento Contable')
	local_trade = fields.Char('Comercio Local')
	sale_shop_id = fields.Many2one('sale.shop', 'Establecimiento de Venta')
	state = fields.Selection([('draft', 'Por Cruzar'), ('done', 'Cruzado')], 'Estado', default='draft')
	need_create_invoice = fields.Boolean('Necesita Crear Factura', default=False)

class AccountPaymentTcWithhold(models.Model):
	_name = 'account.payment.tc.withhold'
	_rec_name = 'l10n_latam_document_number'

	withhold_date = fields.Date('Fecha de Factura')
	l10n_latam_document_number = fields.Char('Número de Documento')
	electronic_authorization = fields.Char('Autorización Electrónica')
	base_iva = fields.Float('Base Imponible IVA')
	percentage_iva = fields.Float('Porcentaje IVA')
	amount_iva = fields.Float('Monto IVA')
	base_renta = fields.Float('Base Imponible Renta')
	percentage_renta = fields.Float('Porcentaje Renta')
	amount_renta = fields.Float('Monto Renta')
	amount_without_tax = fields.Float('Monto sin IVA')
	amount_total = fields.Float('Monto')
	payment_tc_cab_id = fields.Many2one('account.payment.tc.cab', 'Conciliación TC')
	file_id = fields.Many2one('account.payment.tc.files', 'Archivo')
	local_trade = fields.Char('Comercio Local')
	sale_shop_id = fields.Many2one('sale.shop', 'Establecimiento de Venta')

class AccountPaymentTcCab(models.Model):
	_name='account.payment.tc.cab'

	@api.onchange('line_ids')
	def onchage_invoice_payment_id(self):
		for rec in self:
			if rec.line_ids:
				for line in rec.line_ids:
					if line.invoice_payment_id:
						line.invoice_payment_id.amount = line.amount


	def select_all(self):
		for line in self.line_ids:
			line.select_row = True

	def no_select_all(self):
		for line in self.line_ids:
			line.select_row = False

	def clear_lines(self):
		for line in self.line_ids:
			if not line.select_row:
				line.unlink()

	def action_load_payments(self):
		return {
			'name': _('Cargar Pagos'),
			'type': 'ir.actions.act_window',
			'res_model': 'account.payment.tc.wizard',
			'view_mode': 'form',
			'view_type': 'form',
			'target': 'new',
			'context': {
				'default_account_payment_tc_id': self.id,
				'default_bank_id': self.bank_id.id,
			}
		}


	def unlink(self):
		for rec in self:
			if rec.state=='done':
				raise UserError(_('Para eliminar la conciciación debe cambiar a borrador este registro.'))
		res = super().unlink()
		return res


	def button_journal_entries(self):
		return {
			'name': _('Journal Items'),
			'view_mode': 'tree,form',
			'res_model': 'account.move',
			'view_id': False,
			'type': 'ir.actions.act_window',
			'domain': [('id', '=', self.move_id.id)],
		}

	# @api.depends('')
	# def get_state()
	@api.depends("line_ids")
	def _get_total_select_payment(self):
		for rec in self:
			total = 0.00
			for line in rec.line_ids:
				if line.select_row:
					total += line.amount
			rec.total_select_payment = total

	@api.depends('retention_id','amount_iva','amount_renta')
	def _get_total_retention(self):
		for record in self:
			total = 0.00
			iva = 0.00
			renta = 0.00
			if record.retention_id:
				for ret in record.retention_id:
					total += ret.total
					# for line in ret.retention_line_ids:
					# 	if line.description == "retencion_iva":
					# 		iva += line.retained_value_manual
					# 	if line.description == "retencion_renta":
					# 		renta += line.retained_value_manual
			else:
				if abs(record.amount_iva - 0.00) > 0.0001:
					total += record.amount_iva
				if abs(record.amount_renta - 0.00) > 0.0001:
					total += record.amount_renta
			record.amount_retention = total
	# self.amount_iva = iva
	# self.amount_renta = renta

	def _get_amount_bank(self):
		for rec in self:
			total = 0.00
			for line in rec.bank_payment_ids:
				total += line.amount
			rec.amount_bank = total

	def _get_ammount_diff(self):
		for rec in self:
			amount_bank = rec.amount_bank or 0.0
			amount_retention = rec.amount_retention or 0.0
			amount_commission = rec.amount_commission or 0.0
			total_select_payment = rec.total_select_payment or 0.0
			rec.ammount_diff = (amount_bank + amount_retention + amount_commission) - total_select_payment


	name = fields.Char('Nombre', required=True)
	printer_ids = fields.Many2many('sri.printer.point', 'payment_tc_printer_rel', 'payment_tc_id', 'printer_id', 'Puntos de impresión')
	date_move = fields.Date('Fecha Liquidacion', default=fields.Date.today)
	date = fields.Date('Fecha')
	is_range_date = fields.Boolean('Rango de Fechas', default=False)
	date_start = fields.Date('Fecha Inicio')
	date_end = fields.Date('Fecha Fin')
	description = fields.Char('Descripción', required=False)
	journal_filter = fields.Many2one('account.journal','Diario de Tc')
	journal_conciliation = fields.Many2one('account.journal','Diario de Conciliación', default=lambda self: self.env.company.journal_tc_retention_id)
	bank_id = fields.Many2one('res.bank',related='journal_conciliation.bank_id')
	partner_journal_id = fields.Many2one('res.partner',related='bank_id.partner_id')
	line_ids = fields.One2many('account.payment.tc.det','payment_cab_id')
	state = fields.Selection([('draft','Borrador'),('done','Conciliado')], 'Estado',default='draft')
	reference_tc = fields.Char("Referencia TC", required=False)
	lote_tc = fields.Char('Lote TC',required=False)
	auth_tc = fields.Char('Autorización TC',required=False)
	file_ids = fields.One2many('account.payment.tc.files','payment_tc_cab_id')
	bank_payment_ids = fields.One2many('account.payment.bank.payment','payment_tc_cab_id')
	invoice_ids = fields.One2many('account.payment.tc.invoice','payment_tc_cab_id')
	withhold_ids = fields.One2many('account.payment.tc.withhold','payment_tc_cab_id')
	amount_bank = fields.Float('Monto Bancario', compute='_get_amount_bank')
	ammount_diff = fields.Float('Diferencia', compute='_get_ammount_diff', store=False)
	amount_difference = fields.Float('Diferencia',  store=False)
	send_diff_account = fields.Boolean('Enviar a Diferencia a cuenta contable', default=False)
	diff_account_id = fields.Many2one('account.account','Cuenta de Diferencia')
	account_analytic_id = fields.Many2one('account.analytic.account','Cuenta Analitica')
	bank_id = fields.Many2one('res.bank', string='Banco', domain="[('type_load_tc', '!=', False)]")
	have_withholding = fields.Boolean('Tiene Retención', default=False)

	def _get_payment_method_codes_to_exclude(self):
		self.ensure_one()
		return []

	@api.depends('journal_filter')
	def _compute_payment_method_line_fields(self):
		for pay in self:
			pay.available_payment_method_line_ids = pay.journal_filter._get_available_payment_method_lines('inbound')
			to_exclude = pay._get_payment_method_codes_to_exclude()
			if to_exclude:
				pay.available_payment_method_line_ids = pay.available_payment_method_line_ids.filtered(lambda x: x.code not in to_exclude)

	available_payment_method_line_ids = fields.Many2many('account.payment.method.line',compute='_compute_payment_method_line_fields')
	account_payment_method_line_id = fields.Many2one('account.payment.method.line',
													 domain="[('id', 'in', available_payment_method_line_ids)]",
													 string='Método de Pago')

	retention_id = fields.Many2many(comodel_name='account.withhold',
									relation='payment_tc_retention_rel',
									column1='payment_tc_id',
									column2='retention_id',
									string='Retención')

	amount_iva = fields.Float("Valor IVA")
	amount_renta = fields.Float("Valor Renta")
	amount_retention = fields.Float("Valor Retencion", compute='_get_total_retention', store=False)
	payment_id = fields.Many2one('account.payment','Pago Relacionado')
	total_select_payment = fields.Float("Valor lineas Seleccionada", compute='_get_total_select_payment')
	amount_commission = fields.Float("Valor de Comisión")
	have_invoice = fields.Boolean("Tiene Factura para crear", default=False)
	move_id = fields.Many2one("account.move", string="Asiento Contable")


	def action_draft(self):
		self.line_ids.mapped('payment_rel_tc_id').write({'state_conciliation_tc':'not_conciliate','payment_conciliation_tc':None})
		self.move_id.button_draft()
		self.move_id.button_cancel()
		self.write({'state':'draft','move_id':None})

	def get_lines(self):
		if self.line_ids:
			for line in self.line_ids:
				if not line.select_row:
					line.unlink()
		# busqueda para pagos
		search_domain = [('is_credit_card', '=', True),('state_conciliation_tc', '=', 'not_conciliate'), ('state', '=', 'posted')]
		if self.is_range_date:
			search_domain.append(('date', '>=', self.date_start))
			search_domain.append(('date', '<=', self.date_end))
		else:
			if self.date:
				search_domain.append(('date', '=', self.date))
		if self.journal_filter:
			search_domain.append(('journal_id', '=', self.journal_filter.id))
		if self.account_payment_method_line_id:
			search_domain.append(('payment_method_line_id', '=', self.account_payment_method_line_id.id))
		if self.auth_tc:
			search_domain.append(('auth_tc', '=', self.auth_tc))
		if self.lote_tc:
			search_domain.append(('lote_tc', '=', self.lote_tc))
		if self.reference_tc:
			search_domain.append(('reference_tc', '=', self.reference_tc))
		payments = self.env['account.payment'].search(search_domain)
		for line in payments:
			for invoice in line.reconciled_invoice_ids:
				if line.id not in self.line_ids.mapped('payment_rel_tc_id').ids:
					self.env['account.payment.tc.det'].create({'payment_cab_id': self.id,
															   'payment_rel_tc_id': line.id,
															   'payment_date': line.date,
															   'partner_id': line.partner_id.id,
															   'currency_id': line.currency_id.id,
															   'amount': line.amount,
															   'date': line.date,
															   'journal_id': line.journal_id.id,
															   # 'payment_conciliation_tc': line.payment_conciliation_tc.id,
															   'is_credit_card': line.journal_id.credit_card,
															   # 'state_conciliation_tc': line.state_conciliation_tc,
															   # 'type_card': line.type_card,
															   'lote_tc': line.lote_tc,
															   'reference_tc': line.reference_tc,
															   'auth_tc': line.auth_tc,
															   })
	# if invoice.printer_id in self.printer_ids:


	def action_close(self):
		no_select = False
		for line in self.line_ids:
			if line.select_row:
				no_select = True
		if not no_select:
			raise UserError(_(u'Debe seleccionar las líneas a conciliar!!'))
		ids=self.line_ids.filtered(lambda x: x.is_credit_card and x.state_conciliation_tc=='not_conciliate' and x.select_row).mapped('payment_rel_tc_id').ids
		partner_id = False
		if self.journal_conciliation.bank_account_id:
			partner_id = self.journal_conciliation.bank_account_id.partner_id.id
		return {
			'name': _('Regularización de Pagos con TC'),
			'type': 'ir.actions.act_window',
			'res_model': 'wizard.conciliation.tc',
			'view_mode': 'form',
			'view_type': 'form',
			'target': 'new',
			'context': {
				'payment_ids': ids,
				'journal_id': self.journal_conciliation.id,
				'amount_commission': self.amount_commission,
				'amount_retention': self.amount_retention,
				'amount_select': self.total_select_payment,
				'default_amount_bank': self.amount_bank,
				'default_have_amount_diff': self.send_diff_account,
				'default_amount_diff': self.ammount_diff,
				'tc_id':self.id,
				'default_partner_id':partner_id,

			}
		}

class AccountPaymentTcDet(models.Model):
	_name='account.payment.tc.det'

	payment_cab_id=fields.Many2one('account.payment.tc.cab')
	payment_rel_tc_id=fields.Many2one('account.payment', 'Pago',store=True)
	payment_date = fields.Date(string="Fecha")
	partner_id = fields.Many2one('res.partner','Cliente',readonly=True,store=True)
	currency_id = fields.Many2one('res.currency',readonly=True,store=True)
	amount_payment = fields.Monetary(readonly=True, currency_field='currency_id', store=True, string="Monto Acreditado")
	amount_net = fields.Monetary(readonly=True, currency_field='currency_id', store=True, string="Monto Neto")
	amount = fields.Monetary(readonly=True,currency_field='currency_id',store=True, string="Monto Pago")
	date = fields.Date(readonly=True,store=True)
	journal_id = fields.Many2one('account.journal',readonly=True,store=True)
	payment_conciliation_tc = fields.Many2one('account.payment',readonly=True)
	is_credit_card = fields.Boolean('Pago con TC',readonly=True,store=True)
	state_conciliation_tc = fields.Selection([('conciliated','Conciliado'),('not_conciliate','No Conciliado')], string="Estado",readonly=True,store=True)
	# state_conciliation_tc = fields.Selection([('conciliated', 'Conciliado'), ('not_conciliate', 'No Conciliado')],'Estado Regularización TC', default='not_conciliate')
	# circular  = fields.Char(related="payment_rel_tc_id.communication",readonly=True,store=True)
	type_net = fields.Selection([('medianet', 'Medianet'), ('datafast', 'Datafast')],string="Tipo de Red")
	type_card_issue=fields.Many2one('sri.credit.card')
	type_card = fields.Selection([('debito', 'Débito'), ('credito', 'Crédito'), ('prepago', 'Prepago')], store=True)
	lote_tc =fields.Char(string="Lote")
	reference_tc = fields.Char(string="Referencia")
	auth_tc = fields.Char(string="Autorización")
	select_row = fields.Boolean("Seleccionar", default=False)
	bank_payment_id = fields.Many2one('account.payment.bank.payment', 'Pago Bancario Asociado')
	invoice_payment_id = fields.Many2one('account.payment.tc.invoice', 'Factura Asociada')
	journal_id_file = fields.Many2one('account.journal', 'Diario de Pago Carga')
	l10n_latam_document_number_file = fields.Char('Número de Documento Carga')




