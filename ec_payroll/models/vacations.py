# -*- coding: utf-8 -*-
from odoo import models, fields, registry, api
from odoo.tools.translate import _
from odoo.exceptions import RedirectWarning, UserError, ValidationError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DF
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as DTF
from datetime import datetime,date
from dateutil.relativedelta import relativedelta
import time
import logging
from dateutil import rrule
from pytz import timezone, utc
import pytz

_logger = logging.getLogger(__name__)




class hrContract(models.Model):
	_inherit='hr.contract'


	def get_last_vacations(self):

		for line in self:
			objVacations=line.env['hr.request.vacations'].search([('id','=',line.id)]).mapped('date_start')
			if objVacations:
				return max(objVacations)
			else:
				return False




class hrWorkEntry(models.Model):
	_inherit= 'hr.work.entry'
	request_vacations_id = fields.Many2one('hr.request.vacations')


class hrScheduledTransaction(models.Model):
	_inherit= 'hr.scheduled.transaction'
	request_vacations_id = fields.Many2one('hr.request.vacations', ondelete='cascade')


class hrVacations(models.Model):
	_name = "hr.request.vacations"
	_rec_name='number'

	def ics_datetime(self,idate, allday=False):
		if idate:
			if allday:
				return fields.Date.to_date(idate)
			else:
				idate = fields.Datetime.to_datetime(idate)
				return idate.replace(tzinfo=pytz.timezone('UTC'))
		return False

	def get_number(self):

		code=None
		cr=self._cr
		cr.execute('SELECT max(number::int) + 1 FROM hr_request_vacations')
		results = cr.fetchone()


		if results[0]:
			code=str(results[0]).zfill(6)
		else:
			code='000001'
		return code


	def get_last_date_vacation(self):

		objRequest = self.search([('employee_id','=', self.employee_id.id),('state','not in',['draft','send'] )]).filtered(lambda x: x.days_vacations==x.days_legal_to_pay)

		if not objRequest:
			return self.contract_id.date_start
		else:
			return max([x.date_complete_year for x in objRequest])



	number = fields.Char(string=u'Código', readonly=True,default=get_number)
	employee_id 	= 	fields.Many2one('hr.employee',string=u'Empleado', required=True)
	contract_id 	=	fields.Many2one('hr.contract',string=u'Contrato')
	date_contract_start = fields.Date(string=u'F. Inicio Cálculo',  required=True,readonly=False)
	date_trx = fields.Date(string=u"Fecha de Transacción",default=fields.Date.today())
	state = fields.Selection([('draft','Borrador'),('send','Enviado'),('done','Aprobado'),('pay','Pagado')], string=u'Estado',default='draft')
	days_vacations = fields.Float(string=u'Días de Vacaciones')
	month_for_vacations = fields.Float(string=u'Meses Vacaciones')
	pay_type = fields.Selection([('enjoy','Gozada'),('paid','Pagada')],string=u'Tipo',required=True,readonly=False) #,('liquidation','Liquidación')
	structure_id = fields.Many2one('hr.payroll.structure',string=u'Estructura Salarial')
	date_complete_year=fields.Date(string=u'F. Final Cálculo',help=u'' )
	date_start = fields.Date(string=u'F. Inicio Vacaciones', required=True)
	date_end = fields.Date(string=u'F. Fin Vacaciones',required=True)
	salary_acum = fields.Float(string=u'Sueldo Acumulado')
	other_inputs = fields.Float(string=u'Otros Ingresos')
	amount_total = fields.Float(string=u'Monto Vacaciones')
	payslip_id = fields.Many2one('hr.payslip', string=u'Última Nómina de Cálulo')
	days_legal_to_pay = fields.Float(string=u'Días Totales Pago',readonly=True)
	company_id = fields.Many2one('res.company', string='Compañía', default=lambda self: self.env.company.id)


	def get_salary_acum(self,rule_id,last_date,date_complete_year):
		total=False

		# import pdb  
		# pdb.set_trace()
		for line in list(rrule.rrule(rrule.MONTHLY, dtstart=last_date, until=date_complete_year)):


			idsLines = self.env['hr.payslip.line'].search([('contract_id', '=', self.contract_id.id),('date_from', '<=', line.strftime("%Y-%m-%d")),('date_to', '>=', line.strftime("%Y-%m-%d")),('slip_id.state', '=', 'done'),('salary_rule_id', 'in', tuple(rule_id))])

			total+= sum(idsLines.mapped("total"))
		return total


	def get_days(self):
		days=(self.date_end +  relativedelta(days=1) - self.date_start).days
		return days


	def get_other_pays_vacations(self):
		other_pays=0
		remaining_days=0

		objRequest = self.search([('employee_id','=', self.employee_id.id),('state','not in',['draft','send'] ),
								  ('date_contract_start','=',self.date_contract_start.strftime("%Y-%m-%d")),
								  ('date_complete_year','=',self.date_complete_year.strftime("%Y-%m-%d"))])

		for line in objRequest:
			other_pays+=line.days_vacations
			remaining_days+=line.days_legal_to_pay

		if other_pays<remaining_days:
			return other_pays
		return remaining_days


	def get_days_legal_for_vacations(self):
		days=0
		days_vacations=15
		years_for_extra_vacations=3
		years_diff =self.get_years_from_start_contract() - years_for_extra_vacations
		if years_diff >=0:
			days= days_vacations + (1 if years_diff ==0 else years_diff)
		else:
			days= days_vacations
		return days-self.get_other_pays_vacations()


	def get_years_from_start_contract(self):
		last_date=self.contract_id.date_start
		complete_date=self.date_complete_year

		years_complete=len(list(rrule.rrule(rrule.YEARLY, dtstart=last_date, until=complete_date)))
		return years_complete -1

	def get_months(self):
		last_date=self.get_last_date_vacation()
		complete_date=self.date_complete_year

		months_complete=0
		if len(list(rrule.rrule(rrule.MONTHLY, dtstart=last_date, until=complete_date)))>12:
			months_complete=12
		return months_complete


	def get_exists_slip(self):
		if self.pay_type=='paid':
			transaction = self.env['hr.scheduled.transaction'].search([('request_vacations_id','=',self.id)])
			if transaction:
				if self.env['hr.payslip.line'].search([('transaction_id','=',transaction.id)]):
					raise UserError(_(u'Existe una Nómina creada con esta Transacción, verifique') )

		if self.pay_type=='enjoy':
			if self.payslip_id:
				raise UserError(_(u'Existe una Nómina creada con esta Transacción, verifique') )
		return False


	def get_conf_rule_advance_vacations(self):
		if self.env.company.rule_vacation:
			return self.env.company.rule_vacation
		else:
			return False

	def get_conf_code_rule_pay_vacations(self):
		if self.env.company.code_rule_pay_vacation:
			rule_id = self.env['hr.salary.rule'].search([('code','=',self.env.company.code_rule_pay_vacation),
														 ('struct_id','=',self.contract_id.struct_id.id)])
			return rule_id
		else:
			return False

	def get_conf_structure_vacations(self):
		if self.env.company.struct_enjoyd_id:
			return self.env.company.struct_enjoyd_id
		else:
			return False

	###########TRANSACTIONS##########

	@api.onchange('contract_id')
	def on_change_contract(self):

		if self.contract_id.date_start:
			self.date_contract_start= self.get_last_date_vacation()
			self.date_complete_year= self.get_last_date_vacation() +  relativedelta(years=1)
			self.days_legal_to_pay=self.get_days_legal_for_vacations()


	def action_to_calculate(self):
		salary_rule_id=False
		inputs_rule_ids=[]
		oinputs_rule_ids=[]

		salary_rule_id = self.get_conf_rule_advance_vacations()
		if not salary_rule_id:
			raise UserError(_(u'No existe regla de Provisión de Vacaciones Creada') )

		oinputs_rule_ids=self.contract_id.struct_id.rule_ids.filtered(lambda x: x.category_id.code=='OINGR')

		last_date=self.get_last_date_vacation()

		self.amount_total=self.get_salary_acum([salary_rule_id.id],last_date,self.date_complete_year)
		self.other_inputs=self.get_salary_acum(oinputs_rule_ids.ids,last_date,self.date_complete_year)
		self.salary_acum=self.get_salary_acum([salary_rule_id.id],last_date,self.date_complete_year)

		#REVISAR BUSQUEDA
		amount_total = 0.00
		provisions = self.env['payroll.provision'].search([('name','=',self.employee_id.id)])
		for prov in provisions:
			amount_total += prov.holidays
		self.amount_total = amount_total

		self.month_for_vacations=self.get_months()
		self.days_vacations = self.get_days()
		self.days_legal_to_pay=self.get_days_legal_for_vacations()


	def action_to_send(self):

		if self.days_legal_to_pay<self.days_vacations:
			raise UserError(_(u'Días de vacaciones incorrectos') )
		self.state='send'

	def action_draft(self):
		self.state = 'draft'

		# if not self.get_exists_slip():
		# 	self.state='draft'

		if self.pay_type=='paid':
			self.env['hr.scheduled.transaction'].search([('request_vacations_id','=',self.id)]).unlink()

		self.reverse_leaves_work_entry()

	def action_done(self):


		# if self.pay_type=='enjoy':
		# 	return True

		# if self.pay_type=='paid':
		# 	self.create_new_statement()
		self.create_new_statement()

		# if self.pay_type=='liquidation':

		self.state='done'

		#if self.pay_type=='enjoy':
		self.update_calendar()



	def update_calendar(self):
		work_entry_type_leaves = 7 # Debe estar en la configuración General de RRHH  hr.work.entry.type
		for line in self.env['hr.work.entry'].search([('employee_id','=',self.employee_id.id),('date_start','>=',self.date_start),('date_stop','<=',self.date_end)]):

			line.sudo().write({'work_entry_type_id':work_entry_type_leaves,'request_vacations_id':self.id})

	def reverse_leaves_work_entry(self):
		work_entry_type = 1 # Debe estar en la configuración General de RRHH  hr.work.entry.type
		for line in self.env['hr.work.entry'].search([('request_vacations_id','=',self.id)]):
			line.sudo().write({'work_entry_type_id':work_entry_type})


	def unlink(self):
		if not self.get_exists_slip():
			self.reverse_leaves_work_entry()
			return super(hrVacations, self).unlink()


	@api.model
	def create_new_statement(self):
		salary_rule_pay_id = self.get_conf_code_rule_pay_vacations()
		if not salary_rule_pay_id:
			raise UserError(_(u'No existe regla de Pago de Vacaciones Creada') )
		data = {
			'employee_id': self.employee_id.id,
			'rule_id': salary_rule_pay_id.id,
			'name': salary_rule_pay_id.name +' ' + self.employee_id.name,
			'code':salary_rule_pay_id.code +'/' + self.number +'/' +  str(self.date_start.strftime('%B')).upper() + '/'+ self.employee_id.identification_id or str(self.employee_id.id),
			'date': self.date_start,
			'amount': self.amount_total,
			'request_vacations_id':self.id
		}
		ids = self.env['hr.scheduled.transaction'].create(data)
		return ids



	


