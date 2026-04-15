# -*- coding: utf-8 -*-
#############################################################################
#                                                                           #
# Copyright (C) CEN-ERP, Inc - All Rights Reserved                          #
# Unauthorized copying of this file, via any medium is strictly prohibited  #
# Proprietary and confidential                                              #
# Written by Ing. Darwin Vélez <dvelez@cenecuador.edu.ec>, 2023 - 2024      #
#                                                                           #
#############################################################################
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


class reportAdvance(models.AbstractModel):
    _name = 'report.ec_payroll_advance.report_advance'

    @api.model
    def get_details(self, data=False, total=False, advance_type=False, date_start=False, date_end=False, period=False):
        return {'advance_type': advance_type,
                'date_start': date_start,
                'date_end': date_end,
                'period': period,
                'vals': data,
                'total_base': total['total_base'],
                'total_advance': total['total_advance'],
                'currency_id': self.env.company.currency_id,
                }

    @api.model
    def _get_report_values(self, docids, data=None):
        data = dict(data or {})
        data.update(self.get_details(data['reporte'], data['total'], data['advance_type'], data['date_start'], data['date_end'], data['period']))
        return data


class reportAdvanceWizard(models.TransientModel):
    _name = 'report.advance.wizard'

    name = fields.Many2one('account.fiscalyear',u'Periodo')
    month_period = fields.Many2one('account.period',u'Mes', domain="[('fiscalyear_id', '=', name)]")
    type_advance = fields.Selection([
        ('fortnight', 'Quincena'),
        ('thirteenth', u'Décimo Tercero'),
        ('fourteenth', u'Décimo Cuarto'),
    ], string='Tipo de Anticipo', required=True, default=None, )

    @api.onchange('name')
    def _get_type_advance(self):
        if self.name:
            self.month_period = False


    def print_pdf_report(self):
        payments = self.env['request.loan.payment'].search([('state', '=', 'done'),
                                                            ('type_advance','=',self.type_advance),
                                                            ('request_date','>=',self.month_period.date_start),
                                                            ('request_date','<=',self.month_period.date_stop),])
        report = []
        data = {}
        advance_type = u'QUINCENA'
        if self.type_advance=='thirteenth':
            advance_type = u'DÉCIMO TERCER SUELDO'
        if self.type_advance=='fourteenth':
            advance_type = u'DÉCIMO CUARTO SUELDO'
        total = []
        total_base = 0.00
        total_advance = 0.00
        for pays in payments:
            for exp in pays.line_ids:
                wage = 0.00
                contract_id = self.env['hr.contract'].search([('employee_id','=',exp.employee_id.id),('state','=','open')],limit=1)
                if contract_id:
                    # if contract_id.type_day == 'complete':
                    wage = contract_id.wage
                    # else:
                    #     wage = contract_id.value_for_parcial
                else:
                    raise UserError('El empleado ' + str(exp.employee_id.name.upper()) + ' no tiene un contrato activo.')
                if wage > 0.00:
                    percent = (exp.amount * 100) / wage
                else:
                    percent = pays.monto_asignado
                report.append({'employee': str(exp.employee_id.name.upper()),
                               'identification': str(exp.employee_id.identification_id),
                               'request_date': str(pays.request_date),
                               'payment_date': str(pays.payment_date),
                               'campus': str(exp.employee_id.sede_id.name),
                               'amount_base': wage,
                               'percent': round(percent, 2),
                               'amount': exp.amount,
                               'observation': exp.observation or ' ',
                               'bank': str(exp.employee_id.bank_id.name.upper()),
                               'bank_number': str(exp.employee_id.account_number),
                               })
                total_advance += exp.amount
                total_base += wage
        total.append({'total_advance':total_advance,
                      'total_base':total_base,})
        report = sorted(report, key=lambda i: i['employee'])
        data.update({'reporte': report,
                     'total': total[0],
                     'advance_type': advance_type,
                     'date_start': str(self.month_period.date_start),
                     'date_end': str(self.month_period.date_stop),
                     'period': str(self.name.name),
                     })
        return self.env.ref('ec_payroll_advance.action_report_advance').report_action([], data=data)


    def print_xls_report(self):
        payments = self.env['request.loan.payment'].search([('state', '=', 'done'),
                                                            ('type_advance', '=', self.type_advance),
                                                            ('request_date', '>=', self.month_period.date_start),
                                                            ('request_date', '<=', self.month_period.date_stop), ])
        report = []
        data = {}
        advance_type = u'QUINCENA'
        if self.type_advance == 'thirteenth':
            advance_type = u'DÉCIMO TERCER SUELDO'
        if self.type_advance == 'fourteenth':
            advance_type = u'DÉCIMO CUARTO SUELDO'
        total = []
        total_base = 0.00
        total_advance = 0.00
        for pays in payments:
            for exp in pays.line_ids:
                wage = 0.00
                contract_id = self.env['hr.contract'].search(
                    [('employee_id', '=', exp.employee_id.id), ('state', '=', 'open')], limit=1)
                if contract_id:
                    # if contract_id.type_day == 'complete':
                    wage = contract_id.wage
                    # else:
                    #     wage = contract_id.value_for_parcial
                else:
                    raise UserError('El empleado ' + str(exp.employee_id.name.upper()) + ' no tiene un contrato activo.')
                if wage > 0.00:
                    percent = (exp.amount * 100) / wage
                else:
                    percent = pays.monto_asignado
                report.append({'employee': str(exp.employee_id.name.upper()),
                               'identification': str(exp.employee_id.identification_id),
                               'request_date': str(pays.request_date),
                               'payment_date': str(pays.payment_date),
                               'campus': str(exp.employee_id.sede_id.name),
                               'amount_base': wage,
                               'percent': percent,
                               'amount': exp.amount,
                               'observation': exp.observation or ' ',
                               'bank': str(exp.employee_id.bank_id.name.upper()),
                               'bank_number': str(exp.employee_id.account_number),
                               })
                total_advance += exp.amount
                total_base += wage
        total.append({'total_advance': total_advance,
                      'total_base': total_base, })
        report = sorted(report, key=lambda i: i['employee'])
        data.update({'reporte': report,
                     'total': total[0],
                     'advance_type': advance_type,
                     'date_start': str(self.month_period.date_start),
                     'date_end': str(self.month_period.date_stop),
                     'period': str(self.name.name),
                     })
        return {
            'type': 'ir_actions_xlsx_download',
            'data': {'model': 'report.advance.wizard',
                     'options': json.dumps(data, default=date_utils.json_default),
                     'output_format': 'xlsx',
                     'report_name': 'Reporte de Anticipos',
                     }
        }


    def get_xlsx_report(self, data, response):
        docids = None
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})

        bold = workbook.add_format({'bold': True})
        middle = workbook.add_format({'bold': True, 'top': 1})
        left = workbook.add_format({'left': 1, 'top': 1, 'bold': True})
        right = workbook.add_format({'right': 1, 'top': 1})
        top = workbook.add_format({'top': 1})
        report_format = workbook.add_format(
            {'font_size': 14, 'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_color': 'black',
             'bg_color': '#dcdde6',
             'border': 1})
        report_format2 = workbook.add_format(
            {'font_size': 10, 'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_color': 'black',
             'bg_color': '#dcdde6',
             'border': 1})
        rounding = self.env.company.currency_id.decimal_places or 2
        lang_code = self.env.user.lang or 'en_US'
        date_format = workbook.add_format({'num_format': 'dd/mm/yyyy'})
        decimal_format = workbook.add_format({'num_format': '#,##0.00'}),

        sheet = workbook.add_worksheet('REPORTE DE ANTICIPOS')
        sheet.write(2, 0, _('Empleado'), report_format2)
        sheet.write(2, 1, _('Identificación'), report_format2)
        sheet.write(2, 2, _('Clasificación'), report_format2)
        sheet.write(2, 3, _('Sede'), report_format2)
        sheet.write(2, 4, _('Banco'), report_format2)
        sheet.write(2, 5, _('#Cuenta'), report_format2)
        sheet.write(2, 6, _('Fecha de Solicitud'), report_format2)
        sheet.write(2, 7, _('Fecha de Pago'), report_format2)
        sheet.write(2, 8, _('Sueldo de Contrato'), report_format2)
        sheet.write(2, 9, _('Porcentaje'), report_format2)
        sheet.write(2, 10, _('Monto de Anticipo'), report_format2)
        sheet.write(2, 11, _('Observación'), report_format2)
        sheet.merge_range(0, 0, 0, 11, _('REPORTE DE ANTICIPOS DE ' + str(data['advance_type'])),report_format)
        sheet.merge_range(1, 0, 1, 11, _('PERIODO: ' + str(data['period']) + '       DESDE: ' + str(data['date_start']) + '       HASTA ' + str(data['date_end'])),report_format)
        obj = self.env['report.ec_payroll_advance.report_advance']._get_report_values(docids, data)

        for line in obj:
            r = line

        row = 3
        if obj:
            for lrow in obj['vals']:
                sheet.write(row, 0, lrow['employee'], )
                sheet.write(row, 1, lrow['identification'], )
                sheet.write(row, 2, lrow['campus'], )
                sheet.write(row, 3, lrow['bank'], )
                sheet.write(row, 4, lrow['bank_number'], )
                sheet.write(row, 5, lrow['request_date'], )
                sheet.write(row, 6, lrow['payment_date'], )
                sheet.write(row, 7, '$ ' + str(round(lrow['amount_base'],2)), )
                sheet.write(row, 8, round(lrow['percent'],2), )
                sheet.write(row, 9, '$ ' + str(round(lrow['amount'],2)), )
                sheet.write(row, 10, lrow['observation'], )
                row += 1
            sheet.merge_range(row, 0, row, 6, _('TOTAL'), report_format2)
            sheet.write(row, 7, '$ ' + str(round(obj['total_base'], 2)), report_format2)
            sheet.write(row, 8, str(' '), report_format2)
            sheet.write(row, 9, '$ ' + str(round(obj['total_advance'], 2)), report_format2)
            sheet.write(row, 10, str(' '), report_format2)

        COLUM_SIZES = [35, 18, 25, 18, 18, 18, 18, 18, 15, 15, 15, 20]
        for position in range(len(COLUM_SIZES)):
            sheet.set_column(position, position, COLUM_SIZES[position])

        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()
