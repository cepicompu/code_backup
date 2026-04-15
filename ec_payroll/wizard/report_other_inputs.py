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







class reportDeduction(models.AbstractModel):
    _name = 'report.ec_payroll_advance.report_other_inputs'

    @api.model
    def _get_report_values(self, docids, data=None):
        data = dict(data or {})
        vals = []
        # objpayslip=self.env['hr.payslip'].search([('date_from', '>=', data['start_date']),('date_to', '<=', data['end_date']),('state','=','done')])
        for pt in sorted(self.env['hr.payslip.line'].search([('date_from', '>=', data['start_date']),('date_to', '<=', data['end_date'])]).filtered(lambda x: 
            x.salary_rule_id.category_id.code =='OINGR' and x.slip_id.state == 'done' and abs(x.total) > 0),key=lambda x:x.create_date) :
            vals.append(pt)
        data.update({'vals':vals})
        return data

class reportDeductionWizard(models.TransientModel):
    _name = 'report.other.inputs.wizard'


    start_date  = fields.Date('Fecha Inicial')
    end_date = fields.Date('Fecha Final')



    def print_pdf_report(self):

    	data = {
            'start_date': self.start_date,
            'end_date'	: self.end_date,
        }
    	return self.env.ref('ec_payroll_advance.action_report_other_inputs').report_action([], data=data)
    	


    def print_xls_report(self):

        data = {
            'start_date': self.start_date,
            'end_date'  : self.end_date,
        }
        return {
            'type': 'ir_actions_xlsx_download',
            'data': {'model': 'report.other.inputs.wizard',
                     'options': json.dumps(data, default=date_utils.json_default),
                     'output_format': 'xlsx',
                     'report_name': 'Reporte de Otros Ingresos',
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

        sheet = workbook.add_worksheet('REPORTE DE OTROS INGRESOS')
        headers={}
       
        sheet.write(3, 0, _('Empleado'), report_format2)
        sheet.write(3, 1, _('Departamento'), report_format2)
        sheet.write(3, 2, _('Cargo'), report_format2)
        sheet.write(3, 3, _('F.Inicial'), report_format2)
        sheet.write(3, 4, _('F.Final'), report_format2)
        sheet.write(3, 5, _('Otros Ingresos'), report_format2)
        sheet.write(3, 6, _('Monto'), report_format2)
       


        headers={'1':0,'2':1,'3':2,'4':3,'5':4,'6':5,'7':6}

        sheet.merge_range(0, 0, 0, 6, _('REPORTE DE OTROS INGRESOS'), report_format)
        

        obj = self.env['report.ec_payroll_advance.report_other_inputs']._get_report_values(docids,data)

        for line in obj:
            r=line

        row=3
        if obj:
            for lrow in obj['vals']:  
                row+=1         
              
                sheet.write(row, headers['1'], lrow.employee_id.name, )
                sheet.write(row, headers['2'], lrow.contract_id.department_id.name, )
                sheet.write(row, headers['3'], lrow.contract_id.job_id.name, )
                sheet.write(row, headers['4'], lrow.date_from, )
                sheet.write(row, headers['5'], lrow.date_to, )
                sheet.write(row, headers['6'], lrow.salary_rule_id.name, )
                sheet.write(row, headers['7'], lrow.total, )
        
        for line in headers.values():
            sheet.set_column(0,line, 18)
        
        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()


