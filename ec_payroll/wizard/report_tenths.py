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


#74 14
#76 13

class reportThenths13(models.AbstractModel):
	_name = 'report.ec_payroll_advance.report_thenths'

  
	def get_contract(self,employee_id):
		objContracts=self.env['hr.contract'].search([('employee_id','=',employee_id.id),('state','=','open')],limit=1)   

		return objContracts


	

	def get_amount_thenths(self,contract_id,date,rule_id,resultado):
		objpayslip = self.env['hr.payslip']

		amount=0

		# print(date,contract_id.employee_id.name)
		# import pdb 
		# pdb.set_trace()

		for line in objpayslip.search([('contract_id','=',contract_id.id),('date_from','<=',date),('date_to','>=',date)]).mapped('line_ids').filtered(lambda x: x.salary_rule_id.id==rule_id):
			amount=line.total
			resultado['total']+=amount

		return amount




	@api.model
	def _get_report_values(self, docids, data=None):
		data = dict(data or {})
		vals = []
		company = self.env.company
		rule_id=company.rule_thirteenth_id.id

		# company.rule_fourteenth_id.id ,
		#         'thirteenth' : company.rule_thirteenth_id.id,
	
		
		objContracts = self.env['hr.contract'].search([('state','=','open')])

		for line in objContracts:
			values={}
			resultado={}
			resultado['total']=0
			values['employee_id']=line.employee_id
			values['diciembre']=self.get_amount_thenths(line,datetime.strptime(str(data['anio']-1) +'-12'+'-01', '%Y-%m-%d').date(),rule_id,resultado)
			values['enero']=self.get_amount_thenths(line,datetime.strptime(str(data['anio']) +'-01'+'-01', '%Y-%m-%d').date(),rule_id,resultado)
			values['febrero']=self.get_amount_thenths(line,datetime.strptime(str(data['anio']) +'-02'+'-01', '%Y-%m-%d').date(),rule_id,resultado)
			values['marzo']=self.get_amount_thenths(line,datetime.strptime(str(data['anio']) +'-03'+'-01', '%Y-%m-%d').date(),rule_id,resultado)
			values['abril']=self.get_amount_thenths(line,datetime.strptime(str(data['anio']) +'-04'+'-01', '%Y-%m-%d').date(),rule_id,resultado)
			values['mayo']=self.get_amount_thenths(line,datetime.strptime(str(data['anio']) +'-05'+'-01', '%Y-%m-%d').date(),rule_id,resultado)
			values['junio']=self.get_amount_thenths(line,datetime.strptime(str(data['anio']) +'-06'+'-01', '%Y-%m-%d').date(),rule_id,resultado)
			values['julio']=self.get_amount_thenths(line,datetime.strptime(str(data['anio']) +'-07'+'-01', '%Y-%m-%d').date(),rule_id,resultado)
			values['agosto']=self.get_amount_thenths(line,datetime.strptime(str(data['anio']) +'-08'+'-01', '%Y-%m-%d').date(),rule_id,resultado)
			values['septiembre']=self.get_amount_thenths(line,datetime.strptime(str(data['anio']) +'-09'+'-01', '%Y-%m-%d').date(),rule_id,resultado)
			values['octubre']=self.get_amount_thenths(line,datetime.strptime(str(data['anio']) +'-10'+'-01', '%Y-%m-%d').date(),rule_id,resultado)
			values['noviembre']=self.get_amount_thenths(line,datetime.strptime(str(data['anio']) +'-11'+'-01', '%Y-%m-%d').date(),rule_id,resultado)
			values['amount_total']=resultado['total']
			vals.append(values)

			
		data.update({'vals':vals})
		return data


class reportThenths14(models.AbstractModel):
	_name = 'report.ec_payroll_advance.report_thenths_14'

  
	def get_contract(self,employee_id):
		objContracts=self.env['hr.contract'].search([('employee_id','=',employee_id.id),('state','=','open')],limit=1)   

		return objContracts

	def get_amount_thenths(self,contract_id,date,rule_id,resultado):
		objpayslip = self.env['hr.payslip']

		amount=0

		print(date,contract_id.employee_id.name,rule_id)
		# import pdb 
		# pdb.set_trace()

		for line in objpayslip.search([('contract_id','=',contract_id.id),('date_from','<=',date),('date_to','>=',date)]).mapped('line_ids').filtered(lambda x: x.salary_rule_id.id==rule_id.id):
			amount=line.total
			resultado['total']+=amount

		return amount


	@api.model
	def _get_report_values(self, docids, data=None):
		data = dict(data or {})
		vals = []
		company = self.env.company
		rule_id=company.rule_fourteenth_id
		# company.rule_fourteenth_id.id ,
		#         'thirteenth' : company.rule_thirteenth_id.id,
	
		
		objContracts = self.env['hr.contract'].search([('state','=','open')])

		for line in objContracts:
			values={}
			resultado={}
			resultado['total']=0
			values['employee_id']=line.employee_id
			values['marzo']=self.get_amount_thenths(line,datetime.strptime(str(data['anio']) +'-03'+'-01', '%Y-%m-%d').date(),rule_id,resultado)
			values['abril']=self.get_amount_thenths(line,datetime.strptime(str(data['anio']) +'-04'+'-01', '%Y-%m-%d').date(),rule_id,resultado)
			values['mayo']=self.get_amount_thenths(line,datetime.strptime(str(data['anio']) +'-05'+'-01', '%Y-%m-%d').date(),rule_id,resultado)
			values['junio']=self.get_amount_thenths(line,datetime.strptime(str(data['anio']) +'-06'+'-01', '%Y-%m-%d').date(),rule_id,resultado)
			values['julio']=self.get_amount_thenths(line,datetime.strptime(str(data['anio']) +'-07'+'-01', '%Y-%m-%d').date(),rule_id,resultado)
			values['agosto']=self.get_amount_thenths(line,datetime.strptime(str(data['anio']) +'-08'+'-01', '%Y-%m-%d').date(),rule_id,resultado)
			values['septiembre']=self.get_amount_thenths(line,datetime.strptime(str(data['anio']) +'-09'+'-01', '%Y-%m-%d').date(),rule_id,resultado)
			values['octubre']=self.get_amount_thenths(line,datetime.strptime(str(data['anio']) +'-10'+'-01', '%Y-%m-%d').date(),rule_id,resultado)
			values['noviembre']=self.get_amount_thenths(line,datetime.strptime(str(data['anio']) +'-11'+'-01', '%Y-%m-%d').date(),rule_id,resultado)
			values['diciembre']=self.get_amount_thenths(line,datetime.strptime(str(data['anio']) +'-12'+'-01', '%Y-%m-%d').date(),rule_id,resultado)
			values['enero']=self.get_amount_thenths(line,datetime.strptime(str(data['anio']-1) +'-01'+'-01', '%Y-%m-%d').date(),rule_id,resultado)
			values['febrero']=self.get_amount_thenths(line,datetime.strptime(str(data['anio']-1) +'-02'+'-01', '%Y-%m-%d').date(),rule_id,resultado)
			values['amount_total']=resultado['total']
			vals.append(values)

			
		data.update({'vals':vals})
		return data



	

class reportThenthsWizard(models.TransientModel):
	_name = 'report.thenths.wizard'


	anio  = fields.Integer('Año')
	report_type = fields.Selection([('d13','Décimo Tercero'),('d14','Décimo Cuarto')],u'Tipo de Reporte',required=True)
	



	def print_pdf_report(self):

		data = {
			'anio': self.anio,
			'report_type':self.report_type
		}

		if self.report_type=='d13':
			return self.env.ref('ec_payroll_advance.action_report_thenths').report_action([], data=data)
		else:
			return self.env.ref('ec_payroll_advance.action_report_thenths_14').report_action([], data=data)
		
		


	def print_xls_report(self):
		report_type=''

		data = {
			'anio': self.anio,
			'report_type':self.report_type
		}	

		return {
			'type': 'ir_actions_xlsx_download',
			'data': {'model': 'report.thenths.wizard',
					 'options': json.dumps(data, default=date_utils.json_default),
					 'output_format': 'xlsx',
					 'report_name': 'Reporte de Anticipos',
					 },
			'report_type': 'xlsx',
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

		headers={}
		headers={'1':0,'2':1,'3':2,'4':3,'5':4,'6':5,'7':6,'8':7,'9':8,'10':9,'11':10,'12':11,'13':12,'14':13,'15':14,'16':15}



		if data['report_type']=='d13':
			

			sheet = workbook.add_worksheet('REPORTE DE DÉCIMO TERCERO')
			




			sheet.write(3, 0, _('Código'), report_format2)
			sheet.write(3, 1, _('Nombres'), report_format2)
			sheet.write(3, 2, _('Identificación'), report_format2)
			sheet.write(3, 3, _('Diciembre'), report_format2)
			sheet.write(3, 4, _('Enero'), report_format2)
			sheet.write(3, 5, _('Febrero'), report_format2)
			sheet.write(3, 6, _('Marzo'), report_format2)
			sheet.write(3, 7, _('Abril'), report_format2)
			sheet.write(3, 8, _('Mayo'), report_format2)
			sheet.write(3, 9, _('Junio'), report_format2)
			sheet.write(3, 10, _('Julio'), report_format2)
			sheet.write(3, 11, _('Agosto'), report_format2)
			sheet.write(3, 12, _('Septiembre'), report_format2)
			sheet.write(3, 13, _('Octubre'), report_format2)
			sheet.write(3, 14, _('Noviembre'), report_format2)
			sheet.write(3, 15, _('Total Décimo 13'), report_format2)
		   


			

			sheet.merge_range(0, 0, 0, 11, _('REPORTE DE DÉCIMO TERCERO'), report_format)
			

			obj = self.env['report.ec_payroll_advance.report_thenths']._get_report_values(docids,data)

			for line in obj:
				r=line

			row=4
			if obj:
				for lrow in obj['vals']:  
					row+=1         
				  
					sheet.write(row, headers['1'], lrow['employee_id'].codigo_empleado, )
					sheet.write(row, headers['2'], lrow['employee_id'].name, )
					sheet.write(row, headers['3'], lrow['employee_id'].identification_id, )
					sheet.write(row, headers['4'], lrow['diciembre'], )
					sheet.write(row, headers['5'], lrow['enero'], )
					sheet.write(row, headers['6'], lrow['febrero'], )

					sheet.write(row, headers['7'], lrow['marzo'], )
					sheet.write(row, headers['8'], lrow['abril'], )
					sheet.write(row, headers['9'], lrow['mayo'], )
					sheet.write(row, headers['10'], lrow['junio'], )
					sheet.write(row, headers['11'], lrow['julio'], )
					sheet.write(row, headers['12'], lrow['agosto'], )
					sheet.write(row, headers['13'], lrow['septiembre'], )
					sheet.write(row, headers['14'], lrow['octubre'], )
					sheet.write(row, headers['15'], lrow['noviembre'], )
					sheet.write(row, headers['16'],lrow['amount_total'])

		else:
			sheet = workbook.add_worksheet('REPORTE DE DÉCIMO TERCERO')
			




			sheet.write(3, 0, _('Código'), report_format2)
			sheet.write(3, 1, _('Nombres'), report_format2)
			sheet.write(3, 2, _('Identificación'), report_format2)
			sheet.write(3, 3, _('Marzo'), report_format2)
			sheet.write(3, 4, _('Abril'), report_format2)
			sheet.write(3, 5, _('Mayo'), report_format2)
			sheet.write(3, 6, _('Junio'), report_format2)
			sheet.write(3, 7, _('Julio'), report_format2)
			sheet.write(3, 8, _('Agosto'), report_format2)
			sheet.write(3, 9, _('Septiembre'), report_format2)
			sheet.write(3, 10, _('Octubre'), report_format2)
			sheet.write(3, 11, _('Noviembre'), report_format2)
			sheet.write(3, 12, _('Diciembre'), report_format2)
			sheet.write(3, 13, _('Enero'), report_format2)
			sheet.write(3, 14, _('Febrero'), report_format2)
			sheet.write(3, 15, _('Total Décimo 13'), report_format2)
		   


			

			sheet.merge_range(0, 0, 0, 11, _('REPORTE DE DÉCIMO TERCERO'), report_format)
			

			obj = self.env['report.ec_payroll_advance.report_thenths_14']._get_report_values(docids,data)

			for line in obj:
				r=line

			row=4
			if obj:
				for lrow in obj['vals']:  
					row+=1         
				  
					sheet.write(row, headers['1'], lrow['employee_id'].codigo_empleado, )
					sheet.write(row, headers['2'], lrow['employee_id'].name, )
					sheet.write(row, headers['3'], lrow['employee_id'].identification_id, )
					sheet.write(row, headers['4'], lrow['marzo'], )
					sheet.write(row, headers['5'], lrow['abril'], )
					sheet.write(row, headers['6'], lrow['mayo'], )

					sheet.write(row, headers['7'], lrow['junio'], )
					sheet.write(row, headers['8'], lrow['julio'], )
					sheet.write(row, headers['9'], lrow['agosto'], )
					sheet.write(row, headers['10'], lrow['septiembre'], )
					sheet.write(row, headers['11'], lrow['octubre'], )
					sheet.write(row, headers['12'], lrow['noviembre'], )
					sheet.write(row, headers['13'], lrow['diciembre'], )
					sheet.write(row, headers['14'], lrow['enero'], )
					sheet.write(row, headers['15'], lrow['febrero'], )
					sheet.write(row, headers['16'],lrow['amount_total'])



		
		for line in headers.values():
			sheet.set_column(0,line, 18)
		
		workbook.close()
		output.seek(0)
		response.stream.write(output.read())
		output.close()