import json
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError
from odoo import api, fields, models, tools, _
from odoo.tools import date_utils, io
try:
    from odoo.tools.misc import xlsxwriter, workbook
except ImportError:
    import xlsxwriter
import io




class reportPendingVacations(models.AbstractModel):
    _name = 'report.ec_payroll_advance.report_pending_vacations'

    def get_days(self,date_start,date_end):

        days=(date_end +  relativedelta(days=1) - date_start).days
        return days

    @api.model
    def _get_report_values(self, docids, data=None):
        data = dict(data or {})
        vals = []
        date_evaluated=datetime.strptime(data['date_evaluated'], "%Y-%m-%d").date()

      
        if data['all_employees']:
            objVacations=self.env['hr.contract'].search([('state','=','open')])
        elif 'employee_id' in data :
            objVacations=self.env['hr.contract'].search([('employee_id','=',data['employee_id']),('state','=','open')])





        for line in objVacations:
            last_vacations_date=line.get_last_vacations() or line.date_start
            if self.get_days( last_vacations_date ,date_evaluated )>365:
                values={}
                values['contract_id']=line 
                values['date_start']=last_vacations_date 
                values['date_end']= date_evaluated
                values['days_vacations']=self.get_days(last_vacations_date ,date_evaluated)


                vals.append(values)
        data.update({'vals':vals})
        return data

class reportPendingVacationsWizard(models.TransientModel):
    _name = 'report.pending.vacations.wizard'

    date_evaluated  =   fields.Date(u'Fecha de Evaluación',default=datetime.now(),required=True)
    all_employees   =   fields.Boolean('Todos los Empleados')
    employee_id    =   fields.Many2one('hr.employee','Empleado')

    


    def print_pdf_report(self):

    	data = {
            'date_evaluated':self.date_evaluated,
            'employee_id': self.employee_id.id,
            'all_employees':self.all_employees,
        }
    	return self.env.ref('ec_payroll_advance.action_report_pending_vacations').report_action([], data=data)
    	


    def print_xls_report(self):

        data = {
            'date_evaluated':self.date_evaluated,
            'employee_id': self.employee_id.id,
            'all_employees':self.all_employees,
        }
        return {
            'type': 'ir_actions_xlsx_download',
            'data': {'model': 'report.pending.vacations.wizard',
                     'options': json.dumps(data, default=date_utils.json_default),
                     'output_format': 'xlsx',
                     'report_name': 'Reporte de Vacaciones Pendientes',
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

        sheet = workbook.add_worksheet('REPORTE DE VACACIONES PENDIENTES')
        headers={}
       
        sheet.write(3, 0, _('Empleado'), report_format2)
        sheet.write(3, 1, _('F.Contrato'), report_format2)
        sheet.write(3, 2, _('F.Inicio'), report_format2)
        sheet.write(3, 3, _('F.Fin'), report_format2)
        sheet.write(3, 4, _('Días'), report_format2)

       


        headers={'1':0,'2':1,'3':2,'4':3,'5':4}

        sheet.merge_range(0, 0, 0, 4, _('REPORTE DE VACACIONES PENDIENTES'), report_format)
        

        obj = self.env['report.ec_payroll_advance.report_pending_vacations']._get_report_values(docids,data)

        for line in obj:
            r=line

        row=3
        if obj:
            for lrow in obj['vals']:  
                row+=1         
              
                sheet.write(row, headers['1'], lrow['contract_id'].employee_id.name, )
                sheet.write(row, headers['2'], lrow['contract_id'].date_start, )
                sheet.write(row, headers['3'], lrow['date_start'], )
                sheet.write(row, headers['4'], lrow['date_end'], )
                sheet.write(row, headers['5'], lrow['days_vacations'], )

        
        for line in headers.values():
            sheet.set_column(0,line, 18)
        
        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()

