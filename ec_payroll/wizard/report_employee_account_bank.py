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



class reportEmployeeBanck(models.AbstractModel):
    _name = 'report.ec_payroll_advance.report_employee_account_bank'

    @api.model
    def _get_report_values(self, docids, data=None):
        data = dict(data or {})
        vals = []
        values={}
        

        for pt in self.env['hr.contract'].search([('state','=','open')]):
            vals.append(pt)
        data.update({'vals':vals})
        return data

class reportEmployeeBanckWizard(models.TransientModel):
    _name = 'report.employee.account.bank.wizard'


    start_date  = fields.Date('Fecha Inicial')
    end_date = fields.Date('Fecha Final')



    def print_pdf_report(self):

    	data = {
            'start_date': self.start_date,
            'end_date'	: self.end_date,
        }
    	return self.env.ref('ec_payroll_advance.action_report_employee_account_bank').report_action([], data=data)
    	


    def print_xls_report(self):

        data = {
            'start_date': self.start_date,
            'end_date'  : self.end_date,
        }
        return {
            'type': 'ir_actions_xlsx_download',
            'data': {'model': 'report.employee.account.bank.wizard',
                     'options': json.dumps(data, default=date_utils.json_default),
                     'output_format': 'xlsx',
                     'report_name': 'Reporte de Cuentas Bancarias',
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

        sheet = workbook.add_worksheet('REPORTE DE CUENTAS BANCARIAS')
        headers={}
       
        sheet.write(3, 0, _('Empleado'), report_format2)
        sheet.write(3, 1, _('Departamento'), report_format2)
        sheet.write(3, 2, _('Cargo'), report_format2)
        sheet.write(3, 3, _('F.Ingreso'), report_format2)
        sheet.write(3, 4, _('F.Pago'), report_format2)
        sheet.write(3, 5, _('Tipo Cuenta'), report_format2)
        sheet.write(3, 6, _('Cuenta'), report_format2)
        sheet.write(3, 7, _('Banco'), report_format2)


        headers={'1':0,'2':1,'3':2,'4':3,'5':4,'6':5,'7':6,'8':7}

        sheet.merge_range(0, 0, 0, 7, _('REPORTE DE CUENTAS BANCARIAS'), report_format)
        

        obj = self.env['report.ec_payroll_advance.report_employee_account_bank']._get_report_values(docids,data)

        for line in obj:
            r=line

        row=3
        if obj:
            for lrow in obj['vals']:  
                row+=1         
              
                sheet.write(row, headers['1'], lrow.employee_id.name, )
                sheet.write(row, headers['2'], lrow.department_id.name, )
                sheet.write(row, headers['3'], lrow.job_id.name, )
                sheet.write(row, headers['4'], lrow.date_start, )
                sheet.write(row, headers['5'], lrow.employee_id.payment_method, )
                sheet.write(row, headers['6'], lrow.employee_id.bank_account_id.type_account, )
                sheet.write(row, headers['7'], lrow.employee_id.bank_account_id.acc_number, )
                sheet.write(row, headers['8'], lrow.employee_id.bank_account_id.bank_id.name, )
        
        for line in headers.values():
            sheet.set_column(0,line, 18)
        
        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()

