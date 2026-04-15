import json
from datetime import datetime
from odoo.exceptions import UserError
from odoo import api, fields, models, tools, _
from odoo.tools import date_utils, io
try:
	from odoo.tools.misc import xlsxwriter, workbook
except ImportError:
	import xlsxwriter
import io



class reportIncomeTaxMonth(models.AbstractModel):
	_name = 'report.ec_payroll_advance.report_income_tax_month'

  
	

	@api.model
	def _get_amount_rule(self,data,rules,employee_id):
		# This has to be done by SQL for performance reasons avoiding
		# left join with ir_translation on the translatable field "name"
		cr = self._cr

		cr.execute(
			"""Select sum(total) as total,
					to_char(hpl.date_from , 'TMMonth') as mes
					from hr_payslip_line hpl 
					inner join hr_payslip hp on hp.id=hpl.slip_id 
					inner join hr_salary_rule hsr ON hsr.id =hpl.salary_rule_id 
					where salary_rule_id =%s and hpl.employee_id=%s 
					and hp.type_slip_pay ='slip'
					and hpl.date_from >=%s and hpl.date_to <=%s 
					group by to_char(hpl.date_from , 'TMMonth'),hpl.date_from
					order by hpl.date_from""",
			(rules,employee_id,data['start_date'],data['end_date']),
		)
	
		fetched_data = cr.dictfetchall()

		return fetched_data
		




	@api.model
	def _get_report_values(self, docids, data=None):
		data = dict(data or {})
		vals = []
		objpayslip=None
		company = self.env.company
		values={}

		salary_rule_id=data['salary_rule_id']
	   
	
		# ,'|','|',('thirteenth_payment','=','accumulated'),('fourteenth_payment','=','accumulated'),
		#             ('reserve_payment','=', 'accumulated')
		for oline in self.env['hr.contract'].search([('state','=','open')]):
			for line in self._get_amount_rule(data,salary_rule_id,oline.employee_id.id):
				values={}
				values['contract_id']=oline
				values['month']=line['mes']
				values['amount_ir']=round(line['total'],2)
				vals.append(values)
		data.update({'vals':vals})
		return data

class reportIncomeTax(models.AbstractModel):
	_name = 'report.ec_payroll_advance.report_income_tax'

  
	def _get_amount_rule(self,data,rules,employee_id):
		objpayslip=None
	  
	
		objpayslip=sorted(self.env['hr.payslip.line'].search([('employee_id','=',employee_id),('salary_rule_id','=',rules),('date_from', '>=', data['start_date']),('date_to', '<=', data['end_date'])]).filtered(lambda x: 
						x.slip_id.state == 'done' and abs(x.total) > 0),key=lambda x:x.create_date)

		return sum([x.total for x in objpayslip]) or 0.00
		

	@api.model
	def _get_report_values(self, docids, data=None):
		data = dict(data or {})
		vals = []
		objpayslip=None
		company = self.env.company


		salary_rule_id=data['salary_rule_id']
		

		for oline in self.env['hr.contract'].search([('state','=','open')]):
			values={}
			values['contract_id']=oline
			values['amount_ir']=round(self._get_amount_rule(data,salary_rule_id,oline.employee_id.id),2)

			   
			vals.append(values)
		data.update({'vals':vals})
		return data

class reportIncomeTaxWizard(models.TransientModel):
	_name = 'report.income.tax.wizard'

	def _get_default_income(self):
		ir = self.env['hr.salary.rule'].search([('name','ilike','renta')],limit=1)
		return ir.id or None

	salary_rule_id=fields.Many2one('hr.salary.rule',u'Regla Impuesto Renta',required=True,default=_get_default_income)
	report_type = fields.Selection([('acumulated','Acumulado'),('month','Mensual')],u'Tipo de Reporte',required=True)
	start_date  = fields.Date('Fecha Inicial',required=True)
	end_date = fields.Date('Fecha Final',required=True)



	def print_pdf_report(self):

	

		data = {
			'salary_rule_id':	self.salary_rule_id.id,
			'report_type':  self.report_type,
			'start_date':   self.start_date,
			'end_date'	:   self.end_date,
		}

		if self.report_type=='acumulated':
			return self.env.ref('ec_payroll_advance.action_report_income_tax').report_action([], data=data)
		else:
			return self.env.ref('ec_payroll_advance.action_report_income_tax_month').report_action([], data=data)


		


	def print_xls_report(self):

		data = {
			'salary_rule_id':	self.salary_rule_id.id,
			'report_type':  self.report_type,
			'start_date':   self.start_date,
			'end_date'	:   self.end_date,
		}
		return {
			'type': 'ir_actions_xlsx_download',
			'data': {'model': 'report.income.tax.wizard',
					 'options': json.dumps(data, default=date_utils.json_default),
					 'output_format': 'xlsx',
					 'report_name': 'Reporte de Impuesto a la Renta',
					 }
		}



	def get_xlsx_report(self, data, response):
		docids=None
		output = io.BytesIO()
		workbook = xlsxwriter.Workbook(output, {'in_memory': True})

		bold = workbook.add_format({'bold': True})
		middle = workbook.add_format({'bold': True, 'top': 1})
		left = workbook.add_format({'left': 1, 'top': 1, 'bold': True})
		right = workbook.add_format({'right': 1, 'top': 1})
		top = workbook.add_format({'top': 1})
		report_format = workbook.add_format({'font_size': 14, 'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_color': 'black', 'bg_color': '#dcdde6',
				 'border': 1})
		report_format2 = workbook.add_format({'font_size': 10, 'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_color': 'black','bg_color': '#dcdde6',
			 'border': 1})
		rounding = self.env.company.currency_id.decimal_places or 2
		lang_code = self.env.user.lang or 'en_US'
		date_format = workbook.add_format({'num_format': 'dd/mm/yyyy'})
		decimal_format =  workbook.add_format({'num_format': '#,##0.00'}),

		obj={}
		headers={}


		if data['report_type']=='acumulated':
			sheet = workbook.add_worksheet('REPORTE DE IMPUESTO A LA RENTA ACUMULADO')
			sheet.write(3, 0, _('Empleado'), report_format2)
			sheet.write(3, 1, _('F.Contrato'), report_format2)
			sheet.write(3, 2, _('IR'), report_format2)
			headers={'1':0,'2':1,'3':2}
			sheet.merge_range(0, 0, 0, 2, _('REPORTE DE IMPUESTO A LA RENTA ACUMULADO'), report_format)
			obj = self.env['report.ec_payroll_advance.report_income_tax']._get_report_values(docids,data)

		else:
			sheet = workbook.add_worksheet('REPORTE DE IMPUESTO A LA RENTA MENSUAL')
			sheet.write(3, 0, _('Empleado'), report_format2)
			sheet.write(3, 1, _('F.Contrato'), report_format2)
			sheet.write(3, 2, _('Mes'), report_format2)
			sheet.write(3, 3, _('IR'), report_format2)
			headers={'1':0,'2':1,'3':2,'4':3}
			sheet.merge_range(0, 0, 0, 3, _('REPORTE DE IMPUESTO A LA RENTA MENSUAL'), report_format)
			obj = self.env['report.ec_payroll_advance.report_income_tax_month']._get_report_values(docids,data)






		row=3
		if obj:
			for lrow in obj['vals']:  
				row+=1         
			  
				sheet.write(row, headers['1'], lrow['contract_id'].employee_id.name, )
				sheet.write(row, headers['2'], lrow['contract_id'].department_id.name, )

				if data['report_type']=='acumulated':
					sheet.write(row, headers['3'], lrow['amount_ir'], )
				else:
					sheet.write(row, headers['3'], lrow['month'], )
					sheet.write(row, headers['4'], lrow['amount_ir'], )
			   
		
		for line in headers.values():
			sheet.set_column(0,line, 18)
		
		workbook.close()
		output.seek(0)
		response.stream.write(output.read())
		output.close()

