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




class reportLoansPayment(models.AbstractModel):
    _name = 'report.ec_payroll_advance.report_loans_payment'

  
    def get_contract(self,employee_id):
        objContracts=self.env['hr.contract'].search([('employee_id','=',employee_id.id),('state','=','open')],limit=1)   

        return objContracts
   


    @api.model
    def _get_report_values(self, docids, data=None):
        data = dict(data or {})
        vals = []

    
        objLoans=self.env['request.loan.payment'].search([('state','=','done'),('request_date','>=',data['start_date']),('request_date','<=',data['end_date'])])
        # import pdb  
        # pdb.set_trace()
        # for oline in objLoans:
            #.filtered(lambda x: x.state in ('posted','reconciled'))
        for pline in self.env['request.loan.payment.line'].search([('request_id','in',tuple(objLoans.ids))]):
            values={}
            wage=0
            values['employee_id']=pline.employee_id
            contract_id=self.get_contract(pline.employee_id)
            if contract_id:      
                if contract_id.type_day=='complete':
                    wage=contract_id.wage
                else:
                    wage=contract_id.value_for_parcial

            values['payment_date']=pline.request_id.payment_date
            values['sueldo_nominal']=wage
            values['amount_pay']=pline.amount
            vals.append(values)
            
        data.update({'vals':vals})
        return data

class reportLoansPaymentWizard(models.TransientModel):
    _name = 'report.loans.payment.wizard'


    start_date  = fields.Date('Fecha Inicial')
    end_date = fields.Date('Fecha Final')



    def print_pdf_report(self):

    	data = {
            'start_date': self.start_date,
            'end_date'	: self.end_date,
        }
    	return self.env.ref('ec_payroll_advance.action_report_loans_payment').report_action([], data=data)
    	


    def print_xls_report(self):

        data = {
            'start_date': self.start_date,
            'end_date'  : self.end_date,
        }
        return {
            'type': 'ir_actions_xlsx_download',
            'data': {'model': 'report.loans.payment.wizard',
                     'options': json.dumps(data, default=date_utils.json_default),
                     'output_format': 'xlsx',
                     'report_name': 'Reporte de Anticipos',
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

        sheet = workbook.add_worksheet('REPORTE DE ANTICIPOS')
        headers={}




        sheet.write(3, 0, _('Código'), report_format2)
        sheet.write(3, 1, _('Fecha Pago'), report_format2)
        sheet.write(3, 2, _('Nombre'), report_format2)
        sheet.write(3, 3, _('Identificación'), report_format2)
        sheet.write(3, 4, _('Ubicación'), report_format2)
        sheet.write(3, 5, _('Clasificación'), report_format2)
        sheet.write(3, 6, _('Establecimiento'), report_format2)
        sheet.write(3, 7, _('Forma Pago'), report_format2)
        sheet.write(3, 8, _('Banco'), report_format2)
        sheet.write(3, 9, _('Tipo Cuenta'), report_format2)
        sheet.write(3, 10, _('Número Cuenta'), report_format2)
        sheet.write(3, 11, _('Sueldo Nominal'), report_format2)
        sheet.write(3, 12, _('Monto Quincena'), report_format2)
       


        headers={'1':0,'2':1,'3':2,'4':3,'5':4,'6':5,'7':6,'8':7,'9':8,'10':9,'11':10,'12':11,'13':12}

        sheet.merge_range(0, 0, 0, 12, _('REPORTE DE PRESTAMOS ENTREGADOS'), report_format)
        

        obj = self.env['report.ec_payroll_advance.report_loans_payment']._get_report_values(docids,data)

        for line in obj:
            r=line

        row=4
        if obj:
            for lrow in obj['vals']:  
                row+=1         
              
                sheet.write(row, headers['1'], lrow['employee_id'].codigo_empleado, )
                sheet.write(row, headers['2'], lrow['payment_date'], )
                sheet.write(row, headers['3'], lrow['employee_id'].name, )
                sheet.write(row, headers['4'], lrow['employee_id'].identification_id, )
                if lrow['employee_id'].employee_type=='admin':
                    sheet.write(row, headers['5'], 'ADMINISTRATIVO', )
                    sheet.write(row, headers['6'], 'ADMINISTRATIVO', )
                else:
                    sheet.write(row, headers['5'], 'ACADEMICO', )
                    sheet.write(row, headers['6'], 'ADMINISTRATIVO', )
                sheet.write(row, headers['7'], lrow['employee_id'].sede_id.name,)
                if lrow['employee_id'].payment_method=='CUE':
                    sheet.write(row, headers['8'], 'DEPOSITO CUENTA')
                elif lrow['employee_id'].payment_method=='EFE':
                    sheet.write(row, headers['8'], 'EFECTIVO')
                elif lrow['employee_id'].payment_method=='CHE':
                    sheet.write(row, headers['8'], 'CHEQUE')
                elif lrow['employee_id'].payment_method=='TRA':
                    sheet.write(row, headers['8'], 'TRANSFERENCIA')
                else:
                    sheet.write(row, headers['8'], '')

                sheet.write(row, headers['9'], lrow['employee_id'].bank_account_id.bank_id.name if lrow['employee_id'].bank_account_id else '', )

                if lrow['employee_id'].bank_account_id.type_account=='savings':
                    sheet.write(row, headers['10'], 'AHORRO')
                elif lrow['employee_id'].bank_account_id.type_account=='current':
                    sheet.write(row, headers['10'], 'CORRIENTE')
                elif lrow['employee_id'].bank_account_id.type_account=='virtual':
                    sheet.write(row, headers['10'], 'VIRTUAL')

                sheet.write(row, headers['11'], lrow['employee_id'].bank_account_id.acc_number, )
                sheet.write(row, headers['12'], lrow['sueldo_nominal'], )
                sheet.write(row, headers['13'], lrow['amount_pay'], )

        
        for line in headers.values():
            sheet.set_column(0,line, 18)
        
        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()