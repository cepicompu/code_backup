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

class reportEmployeeContract(models.AbstractModel):
    _name = 'report.ec_payroll_advance.report_employee_type_contract'




    def _get_total_hours_contract(self,employee):
        idsContract=self.env['hr.contract'].search([('employee_id','=',int(employee)),('state','=','open')]) 
        
        return sum(self.env['hr.payslip.line'].search([('contract_id','in',tuple(idsContract.ids))]).mapped('days_worked'))


    @api.model
    def _get_report_values(self, docids, data=None):
        data = dict(data or {})
        vals = []
       
        
        all_records=data['all_records']
        employee_id = data['employee_id']
      
        
        if not all_records:
            objContracts=self.env['hr.contract'].search([('employee_id','=',employee_id)])   
        else:
            objContracts=self.env['hr.contract'].search([('state','=','open')])
          

       
        for line in objContracts:
            # if self._get_active_contract(line.employee_id):
            val={}
            val['id_control']=line.id
            val['contract_id']= line
            val['hours']= self._get_total_hours_contract(line.employee_id)
            vals.append(val)
        data.update({'vals':vals})
        return data

class reportEmployeeContractWizard(models.TransientModel):
    _name = 'report.employee.type.contract.wizard'



    all_records = fields.Boolean('Todos',default=True)
    employee_id =fields.Many2one('hr.employee','Empleado')
   



    def print_pdf_report(self):

    	data = {
            'all_records': self.all_records,
            'employee_id'	: self.employee_id.id,
        }
    	return self.env.ref('ec_payroll_advance.action_report_employee_type_contract').report_action([], data=data)
    	


    def print_xls_report(self):

        data = {
            'all_records': self.all_records,
            'employee_id'   : self.employee_id.id,
        }
        return {
            'type': 'ir_actions_xlsx_download',
            'data': {'model': 'report.employee.type.contract.wizard',
                     'options': json.dumps(data, default=date_utils.json_default),
                     'output_format': 'xlsx',
                     'report_name': 'Reporte de Empleados por Tipo de Contrato',
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

        sheet = workbook.add_worksheet('REPORTE DE EMPLEADOS POR TIPO DE CONTRATO')
        headers={}
       
        sheet.write(3, 0, _('Empleado'), report_format2)
        sheet.write(3, 1, _('Departamento'), report_format2)
        sheet.write(3, 2, _('Cargo'), report_format2)
        sheet.write(3, 3, _('Tipo Contrato'), report_format2)
        sheet.write(3, 4, _('Tipo Jornada'), report_format2)
        sheet.write(3, 5, _('F.Ingreso'), report_format2)
        sheet.write(3, 6, _('Horas'), report_format2)


        headers={'1':0,'2':1,'3':2,'4':3,'5':4,'6':5,'7':6}

        sheet.merge_range(0, 0, 0, 6, _('REPORTE DE EMPLEADOS POR TIPO DE CONTRATO'), report_format)
        

        obj = self.env['report.ec_payroll_advance.report_employee_type_contract']._get_report_values(docids,data)

        for line in obj:
            r=line

        row=3
        if obj:
            for lrow in obj['vals']:  
                row+=1         
              
                sheet.write(row, headers['1'], lrow['contract_id'].employee_id.name, )
                sheet.write(row, headers['2'], lrow['contract_id'].department_id.name, )
                sheet.write(row, headers['3'], lrow['contract_id'].job_id.name, )
                sheet.write(row, headers['4'], lrow['contract_id'].contract_type_id.name, )
                sheet.write(row, headers['5'], 'COMPLETA' if lrow['contract_id'].type_day == 'complete' else 'PARCIAL', )
                sheet.write(row, headers['6'], lrow['contract_id'].date_start, )
                sheet.write(row, headers['7'], lrow['hours'], )
        
        for line in headers.values():
            sheet.set_column(0,line, 18)
        
        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()

