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



class reportEmployeeWithholding(models.AbstractModel):
	_name = 'report_employee_withholding'
	_inherit = 'report.report_xlsx.abstract'
	_description = 'Employee Withholding'

  
	

	@api.model
	def _get_employee_ir(self,data,rules,employee_id):
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
	def report_excel(self):
		output = io.BytesIO()
		workbook = xlsxwriter.Workbook(output, {'in_memory': True})

		bold = workbook.add_format({'bold': True})
		middle = workbook.add_format({'bold': True, 'top': 1})
		left = workbook.add_format({'left': 1, 'top': 1, 'bold': True})
		right = workbook.add_format({'right': 1, 'top': 1})
		top = workbook.add_format({'top': 1})
		report_format = workbook.add_format({'font_size': 18, 'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_color': 'white', 'bg_color': '#0F1570',
				 'border': 1})
		report_format2 = workbook.add_format(
			{'font_size': 12, 'bold': True, 'align': 'center_across', 'valign': 'vcenter', 'font_color': 'white',
			 'bg_color': '#0F1570',
			 'border': 1})
		rounding = self.env.company.currency_id.decimal_places or 2
		lang_code = self.env.user.lang or 'en_US'
		date_format = workbook.add_format({'num_format': 'dd/mm/yyyy'})
		decimal_format =  workbook.add_format({'num_format': '#,##0.00'}),
		# ec_xlsx = self.env['hs.report.xlsx']

		workbook.close()
		output.seek(0)
		response.stream.write(output.read())
		output.close()





		
	# def _get_report_values(self, docids, data=None):
	# 	data = dict(data or {})
	# 	vals = []
	# 	objpayslip=None
	# 	company = self.env.company
	# 	values={}

	# 	salary_rule_id=data['salary_rule_id']
	   
	
	# 	# ,'|','|',('thirteenth_payment','=','accumulated'),('fourteenth_payment','=','accumulated'),
	# 	#             ('reserve_payment','=', 'accumulated')
	# 	for oline in self.env['hr.contract'].search([('state','=','open')]):
	# 		for line in self._get_amount_rule(data,salary_rule_id,oline.employee_id.id):
	# 			values={}
	# 			values['contract_id']=oline
	# 			values['month']=line['mes']
	# 			values['amount_ir']=round(line['total'],2)
	# 			vals.append(values)
	# 	data.update({'vals':vals})
	# 	return data


class reportIncomeTaxWizard(models.TransientModel):
	_name = 'report.employee.withholding.wizard'


	date_from  = fields.Date('Fecha Inicial',required=True)
	date_to = fields.Date('Fecha Final',required=True)


		


	def print_xls_report(self):
	
		date_from = datetime.strptime(str(self.date_from), "%Y-%m-%d")
		date_to = datetime.strptime(str(self.date_to), "%Y-%m-%d")
		if date_from:
			if date_from > date_to:
				raise UserError("Fecha debe ser menor a la fecha final")
		data = {
			'ids': self.ids,
			'model': self._name,
			'date_from': self.date_from,
			'date_to': self.date_to,
		}
		return {
			'type': 'ir_actions_xlsx_download',
			'data': {'model': 'report.employee.withholding.wizard',
					 'options': json.dumps(data, default=date_utils.json_default),
					 'output_format': 'xlsx',
					 'report_name': 'Reporte 107',
					 }
		}


	def get_xlsx_report(self, data, response):
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
		# ec_xlsx = self.env['hs.report.xlsx']
		sheet = workbook.add_worksheet('REPORTE 107')
		headers={}
		col=0
		sheet.write(3, col, _('Empleado'), report_format2)
		col+=1
		sheet.write(3, col, _('Identificación'), report_format2)
		headers={'employee':0,'identification':1}
		for line in self._get_columns(data):
			col+=1
			sheet.write(3, col, _(line['nombre']), report_format2)
			headers[line['code']]=col
			
		sheet.merge_range(0, 0, 0, col, _('REPORTE 107: %s') % data['date_from'][:4], report_format)

		row=3
		idsRows=[]
		for lrow in self._get_rows(data):			
			if lrow['identification_id'] not in idsRows:
				row+=1
				idsRows.append(lrow['identification_id'])
			print(row)
			sheet.write(row, headers['employee'], lrow['employee'], )
			sheet.write(row, headers['identification'], lrow['identification_id'], )
			sheet.write(row, headers[lrow['code']], lrow['total'], )


		for line in headers.values():
			sheet.set_column(0,line, 18)




		workbook.close()
		output.seek(0)
		response.stream.write(output.read())
		output.close()



	def _get_columns(self,data):
		# This has to be done by SQL for performance reasons avoiding
		# left join with ir_translation on the translatable field "name"
		cr = self._cr

		cr.execute(
			"""with payslip (employee_id,total,date_from,date_to,code,name_ir)
				as (
					select a.employee_id ,a.total ,a.date_from,a.date_to ,b.code_report ,b."name"  from hr_payslip_line a inner join hr_salary_rule b 
					on b.id=a.salary_rule_id where b.apply_report_ir=true
					union all
					select a.employee_id ,a.monto_deducir,afy.date_start  ,afy.date_stop  ,b.code_report,b.tipo_gasto  from hr_tabla_ir_deducible_empleado a 
					inner join hr_tabla_ir_deducible b on b.id=a.tipo_gasto
					inner join account_fiscalyear afy on afy.id=a.fiscalyear_id)
				 select distinct code, code||' - ' ||name_ir as nombre 
				 from payslip a inner join hr_employee b on a.employee_id = b.id   
				 where date_from::date>=%s::date and date_to::date<=%s::date
				order by code asc""",
			(data['date_from'],data['date_to']),
		)
	
		fetched_data = cr.dictfetchall()

		return fetched_data


	def _get_rows(self,data):
		# This has to be done by SQL for performance reasons avoiding
		# left join with ir_translation on the translatable field "name"
		cr = self._cr

		cr.execute(
			"""with payslip (employee_id,total,date_from,date_to,code,name_ir)
					as (
						select a.employee_id ,a.total ,a.date_from,a.date_to ,b.code_report ,b."name"  from hr_payslip_line a inner join hr_salary_rule b 
						on b.id=a.salary_rule_id where b.apply_report_ir=true
						union all
						select a.employee_id ,a.monto_deducir,afy.date_start  ,afy.date_stop  ,b.code_report,b.tipo_gasto  from hr_tabla_ir_deducible_empleado a 
						inner join hr_tabla_ir_deducible b on b.id=a.tipo_gasto
						inner join account_fiscalyear afy on afy.id=a.fiscalyear_id)
					 select b.name as employee,b.identification_id,sum(total) as total,code,code||' - ' ||name_ir ,date_from,date_to
					 from payslip a inner join hr_employee b on a.employee_id = b.id  
					 where date_from::date>=%s::date and date_to::date<=%s::date
					group by b.name,b.identification_id,code,name_ir, date_from,date_to 
					order by b.name asc,code""",
			(data['date_from'],data['date_to']),
		)
	
		fetched_data = cr.dictfetchall()

		return fetched_data



		