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


class AccountPayment(models.Model):
	_inherit= 'account.payment'

	@api.onchange('journal_id')
	def onchange_journal_id(self):
		if self.journal_id.forma_pago_id:
			self.forma_pago_id=self.journal_id.forma_pago_id
		if self.journal_id.bank_id:
			self.bank_id=self.journal_id.bank_id

	@api.depends('payment_type', 'journal_id')
	def _compute_hide_payment_method(self):
		for payment in self:
			if not payment.journal_id or payment.journal_id.type not in ['bank']:
				payment.hide_payment_method = True
				continue
			journal_payment_methods = payment.payment_type == 'inbound' \
									  and payment.journal_id.inbound_payment_method_ids \
									  or payment.journal_id.outbound_payment_method_ids
			payment.hide_payment_method = len(journal_payment_methods) == 1 and journal_payment_methods[0].code == 'manual'


	def action_draft(self):
		super(AccountPayment,self).action_draft()
		if self.payment_conciliation_tc:
			self.payment_conciliation_tc.write({'state_conciliation_tc':'not_conciliate'})


	def post(self):
		res = super(AccountPayment,self).action_post()
		if self.payment_conciliation_tc and res:
			self.payment_conciliation_tc.write({'state_conciliation_tc':'conciliated'})
		return res


	@api.depends('journal_id','payment_type','payment_method_id')
	def _get_state(self):
		tc=False
		for record in self:
			if record.payment_type=='inbound':
				if record.journal_id:
					if record.journal_id.credit_card:
						tc=True

			record.is_credit_card=tc
			record.state_conciliation_tc = 'not_conciliate'


	is_credit_card = fields.Boolean('Pago con TC',compute='_get_state',store=True)
	state_conciliation_tc = fields.Selection([('conciliated','Conciliado'),('not_conciliate','No Conciliado')],'Estado Regularización TC')
	payment_conciliation_tc = fields.Many2one('account.payment','Pago Relacionado')
	bank_id = fields.Many2one('res.bank', u'Banco', readonly=True, states={'draft': [('readonly', False), ]},
							  ondelete="restrict")
	voucher_type = fields.Selection([
		('automatic', 'Automatico'),
		('manual', 'Manual'),
	], u'Tipo de Voucher', default="automatic", readonly=True, states={'draft': [('readonly', False), ]})
	lote_tc = fields.Char(u'Lote TC', required=False, readonly=True, states={'draft': [('readonly', False), ]})
	auth_tc = fields.Char(u'Autorización TC', readonly=True, states={'draft': [('readonly', False), ]})
	reference_tc = fields.Char("Referencia TC")
	tarjeta_number = fields.Char(u'Número de Tarjeta', size=4, required=False, readonly=True,
								 states={'draft': [('readonly', False), ]})
	tc_origin = fields.Selection([('local', 'Local'), ('international', 'Internacional')], 'Procedencia de la Tarjeta')
	type_card_issue = fields.Many2one('sri.credit.card', 'Tipo de Emisor Tarjeta')
	type_card = fields.Selection([('debito', 'Débito'), ('credito', 'Crédito'), ('prepago', 'Prepago')], 'Tipo Tarjeta')
	payment_deferred = fields.Selection([('ninguno', 'Ninguno'), ('3', '3 Meses'), ('6', '6 Meses'), ('12', '12 Meses'), ('24', '24 Meses')],'Pago diferido a')
	poseedor = fields.Char(u'Poseedor')
	type_transfer = fields.Selection(
		[('propio', 'Transferencia Propio Banco'), ('nacional', 'Transferencia Otro Banco Nacional'),
		 ('exterior', 'Transferencia Banco Exterior')], 'Tipo de Transferencia')
	bank_company_account_id = fields.Many2one('res.partner.bank', related="journal_id.bank_account_id", readonly=True,
											  store=True)
	date_pay_transfer_tc = fields.Date('Fecha')

	def _prepare_payment_moves(self):
		# account_details =None

		if self.env.context.get('tarjeta_credito', False) and self.env.context.get('account_payment_id', False):
			self.destination_account_id = self.env.context.get('account_payment_id')
		res = super(AccountPayment, self)._prepare_payment_moves()

		return res



	def action_conciate(self):
		return self._payment_tc()


	def _payment_tc(self):
		ids=self.filtered(lambda x: x.is_credit_card and x.state_conciliation_tc=='not_conciliate').ids
		return {
			'name': _('Regularización de Pagos con TC'),
			'type': 'ir.actions.act_window',
			'res_model': 'wizard.conciliation.tc',
			'view_mode': 'form',
			'view_type': 'form',
			'target': 'new',
			'context': {
				'payment_ids': ids,

			}
		}


	def _prepare_payment_moves(self):
		if self.env.context.get('reconcile_tc',False):
			res = super(AccountPayment, self)._prepare_payment_moves()
			res[0]['line_ids'] = self.env.context['reconcile_tc_data']
			return res
		res=super(AccountPayment, self)._prepare_payment_moves()
		if res:
			if self.payment_method_id.code=='tc'  and self.env.company.account_advance_tc:
				res[0]['line_ids'][1][2]['account_id']=self.env.company.account_advance_tc.id
		return res

class AccountPaymentMethod(models.Model):
	_inherit = 'account.payment.method'

	@api.model
	def _get_payment_method_information(self):
		res = super()._get_payment_method_information()
		res['tc_in'] = {'mode': 'multi', 'domain': [('type', '=', 'bank')]}
		return res