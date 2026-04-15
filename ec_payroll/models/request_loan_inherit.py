# -*- coding: utf-8 -*-
from odoo import models, fields, registry, api
from odoo.tools.translate import _
from odoo.exceptions import RedirectWarning, UserError, ValidationError
import logging, base64
from io import BytesIO
from datetime import date
try:
	from odoo.tools.misc import xlsxwriter
except ImportError:
	import xlsxwriter
_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
	_inherit='account.payment'

	request_salary_id = fields.Many2one('hr.account.payment.line', ondelete='cascade')

	def _prepare_payment_moves(self):
		# account_details =None
		if self.request_loan_line_id:
			company = self.env.company
			if not company.salarios_account_id:
				raise UserError(_("Debe configurar una cuenta contable de sueldos en los ajustes de Nómina"))

			self.destination_account_id = self.request_loan_line_id.request_id.payment_account_id.id
		res = super(HrAccountPayment, self)._prepare_payment_moves()

		return res

	def _get_counterpart_move_line_vals(self, invoice=False):

		account = None
		company = self.env.company
		company.salarios_account_id

		if self.request_loan_line_id:
			account = self.request_loan_line_id.request_id.hr_rule.account_debit.id
		elif self.request_salary_id:
			account = company.salarios_account_id.id
		else:
			account = self.destination_account_id.id

		if self.payment_type == 'transfer':
			name = self.name
		else:
			name = ''
			if self.partner_type == 'customer':
				if self.payment_type == 'inbound':
					name += _("Customer Payment")
				elif self.payment_type == 'outbound':
					name += _("Customer Credit Note")
			elif self.partner_type == 'supplier':
				if self.payment_type == 'inbound':
					name += _("Vendor Credit Note")
				elif self.payment_type == 'outbound':
					name += _("Vendor Payment")
			if invoice:
				name += ': '
				for inv in invoice:
					if inv.move_id:
						if inv.number:
							name += inv.number + ', '
						else:
							name += inv.document_number + ', '

				name = name[:len(name) - 2]
		return {
			'name': name,
			'account_id': account,
			'journal_id': self.journal_id.id,
			'currency_id': self.currency_id != self.company_id.currency_id and self.currency_id.id or False,
		}


def _get_counterpart_move_line_vals(self, invoice=False):
	# import pdb
	# pdb.set_trace()
	if self.request_loan_line_id:
		account = self.request_loan_line_id.request_id.hr_rule.account_debit.id
	else:
		account = self.destination_account_id.id
	if self.payment_type == 'transfer':
		name = self.name
	else:
		name = ''
		if self.partner_type == 'customer':
			if self.payment_type == 'inbound':
				name += _("Customer Payment")
			elif self.payment_type == 'outbound':
				name += _("Customer Credit Note")
		elif self.partner_type == 'supplier':
			if self.payment_type == 'inbound':
				name += _("Vendor Credit Note")
			elif self.payment_type == 'outbound':
				name += _("Vendor Payment")
		if invoice:
			name += ': '
			for inv in invoice:
				if inv.move_id:
					if inv.number and len(inv.number)>0:
						name += inv.number + ', '
					else:
						name += inv.document_number + ', '
			name = name[:len(name)-2]
	return {
		'name': name,
		'account_id': account,
		'journal_id': self.journal_id.id,
		'currency_id': self.currency_id != self.company_id.currency_id and self.currency_id.id or False,
	}


class HrCompany(models.Model):

	_inherit = 'res.company'

	journal_chque_anticipo = fields.Many2one('account.journal',string=u'Diario Anticipo (Cheque)',
											 ondelete="restrict",readonly=False)
	journal_trans_anticipo = fields.Many2one('account.journal',string=u'Diario Anticipo (Transferencia)',
											 ondelete="restrict",readonly=False)
	account_fortnight_id = fields.Many2one('account.account', string=u'Cuenta Anticipo Quincena',
										   ondelete="restrict")
	account_salary_id = fields.Many2one('account.account', string=u'Cuenta Sueldo', ondelete="restrict")
	separate_for_supplies = fields.Boolean(string='Separar asiento para Provisiones?')
	movement_in_lot = fields.Boolean(string='Asiento Contable en Lote?')
	grouping_method = fields.Selection([
		('analytic', 'Analítico'),
		('employee', 'Empleado')
	], default='analytic', string="Método de agrupación contable")


class HrConfigSetting(models.TransientModel):

	_inherit = 'res.config.settings'

	journal_chque_anticipo = fields.Many2one('account.journal',string=u'Diario Anticipo (Cheque)',
											 ondelete="restrict" ,related="company_id.journal_chque_anticipo",readonly=False)
	journal_trans_anticipo = fields.Many2one('account.journal',string=u'Diario Anticipo (Transferencia)',
											 ondelete="restrict",related="company_id.journal_trans_anticipo",readonly=False)
	account_fortnight_id = fields.Many2one('account.account', string=u'Cuenta Anticipo Quincena',
										   ondelete="restrict",related="company_id.account_fortnight_id",readonly=False)
	account_salary_id = fields.Many2one('account.account', string=u'Cuenta Sueldo', related="company_id.account_salary_id",
										ondelete="restrict",readonly=False)
	separate_for_supplies = fields.Boolean(string='Separar asiento para Provisiones?', related="company_id.separate_for_supplies",readonly=False)
	movement_in_lot = fields.Boolean(string='Asiento Contable en Lote?', related="company_id.movement_in_lot",readonly=False)
	grouping_method = fields.Selection(
		selection=[('analytic', 'Analítico'), ('employee', 'Empleado')],
		string="Método de agrupación contable",
		related='company_id.grouping_method',
		readonly=False,
		store=False,
	)


class HrContract(models.Model):

	_inherit = 'hr.contract'

	journal_chque_anticipo = fields.Many2one('account.journal',string=u'Diario Anticipo (Cheque)',
											 ondelete="restrict")
	journal_trans_anticipo = fields.Many2one('account.journal',string=u'Diario Anticipo (Transferencia)',
											 ondelete="restrict")


class HrAccountPayment(models.Model):
	_inherit='account.payment'

	request_loan_line_id =	fields.Many2one('request.loan.payment.line')


class ScheduleTransaction(models.Model):

	_inherit = 'hr.scheduled.transaction'

	request_loan_line =	fields.Many2one('request.loan.payment',ondelete="cascade")
