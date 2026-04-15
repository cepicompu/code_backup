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




class reportLoans(models.AbstractModel):
    _name = 'report.ec_payroll_advance.report_loans'

  
    def _get_max_date(self,payment_id):
        max_date_pay=0 
        max_date_pay = max([x.date for x in self.env['hr.scheduled.transaction'].search([('payment_id','=',payment_id)])])
        return max_date_pay 

    def _get_amount_pay(self,payment_id):
        amount=0 
        amount = sum([x.amount for x in self.env['hr.scheduled.transaction'].search([('payment_id','=',payment_id),('processed','=',True)])])
        return amount or 0.00


    @api.model
    def _get_report_values(self, docids, data=None):
        data = dict(data or {})
        vals = []
    
        objLoans=self.env['request.egress'].search([('state','=','delivered'),('request_date','>=',data['start_date']),('request_date','<=',data['end_date'])])
        for oline in objLoans:
            #.filtered(lambda x: x.state in ('posted','reconciled'))
            for pline in self.env['account.payment'].search([('request_egress_id','in',tuple(objLoans.ids))]):
                values={}
                values['employee_id']=oline.employee_id
                values['amount_loan']=oline.amount
                values['amount_pay']=self._get_amount_pay(pline.id)
                values['amount_pending'] = oline.amount - self._get_amount_pay(pline.id)
                values['number_payments']=oline.numbers_discount
                values['end_payment']=self._get_max_date(pline.id)
                values['payment_id']=pline
                if pline.state in ['posted','reconciled']:
                    values['state']='PAGADO'
                else:
                    values['state']='BORRADOR'
                vals.append(values)
        data.update({'vals':vals})
        return data

class reportLoansWizard(models.TransientModel):
    _name = 'report.loans.wizard'


    start_date  = fields.Date('Fecha Inicial')
    end_date = fields.Date('Fecha Final')



    def print_pdf_report(self):

    	data = {
            'start_date': self.start_date,
            'end_date'	: self.end_date,
        }
    	return self.env.ref('ec_payroll_advance.action_report_loans').report_action([], data=data)
    	


    def print_xls_report(self):

        data = {
            'start_date': self.start_date,
            'end_date'  : self.end_date,
        }
        return {
            'type': 'ir_actions_xlsx_download',
            'data': {'model': 'report.loans.wizard',
                     'options': json.dumps(data, default=date_utils.json_default),
                     'output_format': 'xlsx',
                     'report_name': 'Reporte de Préstamos Entregados',
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

        sheet = workbook.add_worksheet('REPORTE DE PRESTAMOS ENTREGADOS')
        headers={}
       
        sheet.write(3, 0, _('Empleado'), report_format2)
        sheet.write(3, 1, _('Monto Préstamo'), report_format2)
        sheet.write(3, 2, _('Monto Pagado'), report_format2)
        sheet.write(3, 3, _('Monto Pendiente'), report_format2)
        sheet.write(3, 4, _('Número de Cuotas'), report_format2)
        sheet.write(3, 5, _('F. Ultima Cuota'), report_format2)
        sheet.write(3, 6, _('Pago #'), report_format2)
       


        headers={'1':0,'2':1,'3':2,'4':3,'5':4,'6':5,'7':6}

        sheet.merge_range(0, 0, 0, 6, _('REPORTE DE PRESTAMOS ENTREGADOS'), report_format)
        

        obj = self.env['report.ec_payroll_advance.report_loans']._get_report_values(docids,data)

        for line in obj:
            r=line

        row=3
        if obj:
            for lrow in obj['vals']:  
                row+=1         
              
                sheet.write(row, headers['1'], lrow['employee_id'].name, )
                sheet.write(row, headers['2'], lrow['amount_loan'], )
                sheet.write(row, headers['3'], lrow['amount_pay'], )
                sheet.write(row, headers['4'], lrow['amount_pending'], )
                sheet.write(row, headers['5'], lrow['number_payments'], )
                sheet.write(row, headers['6'], lrow['end_payment'], )
                sheet.write(row, headers['7'], lrow['payment_id'].name, )
        
        for line in headers.values():
            sheet.set_column(0,line, 18)
        
        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()


        