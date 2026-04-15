import re
import json
import logging
import requests
import base64
from datetime import date, datetime, timedelta
from odoo import api, fields, models, tools, _
from odoo.http import request
from odoo.exceptions import UserError, Warning, RedirectWarning, ValidationError
from odoo.tools import date_utils

email_validator = re.compile(r"[^@]+@[^@]+\.[^@]+")

_logger = logging.getLogger(__name__)

from odoo.osv.expression import AND

try:
    from odoo.tools.misc import xlsxwriter, workbook
except ImportError:
    import xlsxwriter
import io



class reportDeduction(models.AbstractModel):
    _name = 'report.ec_payroll_advance.report_deduction'

    @api.model
    def get_details(self, data=False, start_date=False, end_date=False, total=False):
        return {'start_date': start_date,
                'end_date': end_date,
                'total': total,
                'vals': data,
                'currency_id': self.env.company.currency_id,
                }

    @api.model
    def _get_report_values(self, docids, data=None):
        data = dict(data or {})
        data.update(self.get_details(data['reporte'], data['start_date'], data['end_date'], data['total']))
        return data

class reportDeductionWizard(models.TransientModel):
    _name = 'report.deduction.wizard'


    start_date  = fields.Date('Fecha Inicial')
    end_date = fields.Date('Fecha Final')


    def print_pdf_report(self):
        trubros = self.env['hr.scheduled.transaction.category'].search([('mostrar_en_registros','=',True)])
        expenses = self.env['hr.scheduled.transaction'].search([('category_transaction_id','in', trubros.ids),
                                                                ('date', '>=', self.start_date),
                                                                ('date', '<=', self.end_date),
                                                                ('processed','=',True) #depende como quede al final
                                                                ])
        report = []
        data = {}
        total = 0.00
        for exp in expenses:

            report.append({'employee': str(exp.employee_id.name),
                           'identification': str(exp.employee_id.identification_id),
                           'date': str(exp.date),
                           'motive': str(exp.category_transaction_id.name),
                           'observation': exp.observation or ' ',
                           'amount': exp.amount,
                           })
            total += exp.amount


        data.update({'reporte': report,
            'start_date': str(self.start_date),
            'end_date'	: str(self.end_date),
            'total'	: total,
        })
        return self.env.ref('ec_payroll_advance.action_report_deduction').report_action([], data=data)
    	


    def print_xls_report(self):

        trubros = self.env['hr.scheduled.transaction.category'].search([('mostrar_en_registros', '=', True)])
        expenses = self.env['hr.scheduled.transaction'].search([('category_transaction_id', 'in', trubros.ids),
                                                                ('date', '>=', self.start_date),
                                                                ('date', '<=', self.end_date),
                                                                ('processed','=',True) #depende como quede al final
                                                                ])
        report = []
        data = {}
        total = 0.00
        for exp in expenses:
            report.append({'employee': str(exp.employee_id.name),
                           'identification': str(exp.employee_id.identification_id),
                           'date': str(exp.date),
                           'motive': str(exp.category_transaction_id.name),
                           'observation': str(exp.observation),
                           'amount': exp.amount,
                           })
            total += exp.amount

        data.update({'reporte': report,
                     'start_date': str(self.start_date),
                     'end_date': str(self.end_date),
                     'total': total,
                     })
        return {
            'type': 'ir_actions_xlsx_download',
            'data': {'model': 'report.deduction.wizard',
                     'options': json.dumps(data, default=date_utils.json_default),
                     'output_format': 'xlsx',
                     'report_name': 'Reporte de Deducciones',
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

        sheet = workbook.add_worksheet('REPORTE DE DEDUCCIONES')
        headers={}
       
        sheet.write(3, 0, _('Empleado'), report_format2)
        sheet.write(3, 1, _('Identificación'), report_format2)
        sheet.write(3, 2, _('Clasificación'), report_format2)
        sheet.write(3, 3, _('Fecha'), report_format2)
        sheet.write(3, 4, _('Motivo'), report_format2)
        sheet.write(3, 5, _('Observación'), report_format2)
        sheet.write(3, 6, _('Monto'), report_format2)


        headers={'1':0,'2':1,'3':2,'4':3,'5':4,'6':5,'7':6}

        sheet.merge_range(0, 0, 0, 6, _('REPORTE DE DEDUCCIONES'), report_format)
        sheet.merge_range(1, 0, 1, 6, _('DESDE: '+ str(data['start_date']) + ' HASTA: ' + str(data['end_date'])), report_format)

        obj = self.env['report.ec_payroll_advance.report_deduction']._get_report_values(docids,data)

        for line in obj:
            r=line

        row=4
        if obj:
            for lrow in obj['vals']:  
                sheet.write(row, headers['1'], lrow['employee'], )
                sheet.write(row, headers['2'], lrow['identification'], )
                sheet.write(row, headers['3'], lrow['date'], )
                sheet.write(row, headers['4'], lrow['motive'], )
                sheet.write(row, headers['5'], lrow['observation'], )
                sheet.write(row, headers['6'], '$ ' + str(round(lrow['amount'],2)), )
                row += 1
            sheet.merge_range(row, 0, row, 4, _('TOTAL'), report_format)
            sheet.write(row, headers['6'], '$ ' + str(round(obj['total'], 2)), report_format)
        COLUM_SIZES = [35, 18, 25, 18, 35, 35, 15]
        for position in range(len(COLUM_SIZES)):
            sheet.set_column(position, position, COLUM_SIZES[position])
        
        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()


 