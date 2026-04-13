# -*- coding: utf-8 -*-#
import logging
from datetime import timedelta
from functools import partial
import json
import requests
import psycopg2
import pytz
from datetime import date, datetime, timedelta
from odoo import api, fields, models, tools, _
from odoo.tools import float_is_zero, float_round, float_repr, float_compare
from odoo.exceptions import UserError
from odoo.http import request
from odoo.osv.expression import AND
import base64
import logging

_logger = logging.getLogger(__name__)

try:
    from odoo.tools.misc import xlsxwriter
except ImportError:
    import xlsxwriter
import io
import pickle


class ReportDifferencesByLoad(models.AbstractModel):
    _name = 'report.ec_payment_tc.report_differences_by_load'

    @api.model
    def create_workbook(self, page_string=''):
        fp = io.BytesIO()
        # crear el reporte en memoria, no en archivo
        workbook = xlsxwriter.Workbook(fp, {'in_memory': True, 'constant_memory': False})
        worksheet = workbook.add_worksheet(page_string)
        FORMATS = {
            'title': workbook.add_format(
                {'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_color': 'white', 'bg_color': '#0F1570',
                 'border': 1}),
            'border': workbook.add_format({'border': 1}),
            'bold': workbook.add_format({'bold': True, 'text_wrap': True}),
            'single_bold': workbook.add_format({'bold': True}),
            'bold_border': workbook.add_format({'bold': True, 'border': 1}),
            'number': workbook.add_format({'num_format': '#,##0.00'}),
            'number_0f': workbook.add_format({'num_format': '#,##0'}),
            'money': workbook.add_format({'num_format': '$#,##0.00'}),
            'number_bold': workbook.add_format({'num_format': '#,##0.00', 'bold': True}),
            'money_bold': workbook.add_format({'num_format': '$#,##0.00', 'bold': True}),
            'date': workbook.add_format({'num_format': 'dd/mm/yyyy'}),
            'datetime': workbook.add_format({'num_format': 'dd/mm/yyyy h:m:s'}),
            'date_bold': workbook.add_format({'num_format': 'dd/mm/yyyy', 'bold': True}),
            'datetime_bold': workbook.add_format({'num_format': 'dd/mm/yyyy h:m:s', 'bold': True}),
            'merge_center': workbook.add_format({'align': 'center', 'valign': 'vcenter', 'bold': True}),
            'merge_center_single': workbook.add_format({'align': 'center', 'valign': 'vcenter'}),
            'merge_left': workbook.add_format({'align': 'left', 'valign': 'vcenter'}),
            'merge_right': workbook.add_format({'align': 'right', 'valign': 'vcenter', 'bold': True}),
            'aqua': workbook.add_format({'font_color': '#909C9D', 'num_format': '#,##0.00'}),
        }
        return fp, workbook, worksheet, FORMATS

    @api.model
    def get_workbook_binary(self, fp, workbook):
        workbook.close()
        fp.seek(0)
        data = fp.read()
        fp.close()
        return data

    def get_report_xls(self, data):
        def set_line(workbook, current_row, de):
            worksheet.write(current_row, 0, de['name'], report_format5)
            worksheet.write(current_row, 1, de['date'], report_format5)
            worksheet.write(current_row, 2, de['journal'], report_format5)
            worksheet.write(current_row, 3, de['lote'], report_format5)
            worksheet.write(current_row, 4, de['auth'], report_format5)
            worksheet.write(current_row, 5, de['total'], report_format3)
            worksheet.write(current_row, 6, de['amount_bank'], report_format3)
            worksheet.write(current_row, 7, de['amount_retention'], report_format3)
            worksheet.write(current_row, 8, de['amount_commission'], report_format3)
            worksheet.write(current_row, 9, de['diff'], report_format3)
            worksheet.write(current_row, 10, de['estado'], report_format5)
            worksheet.write(current_row, 11, de['description'], report_format5)
        fp, workbook, worksheet, FORMATS = self.create_workbook("REPORTE DE DIFERENCIA POR CARGA")
        report_format1 = workbook.add_format(
            {'font_size': 10, 'bold': True, 'align': 'left', 'valign': 'vcenter', 'font_color': 'black',
             'bg_color': '#dcdde6',
             'border': 1})
        report_format2 = workbook.add_format(
            {'font_size': 10, 'bold': True, 'align': 'right', 'valign': 'vcenter', 'font_color': 'black',
             'bg_color': '#dcdde6', 'num_format': '0.00',
             'border': 1})
        report_format3 = workbook.add_format(
            {'num_format': '0.00', 'font_size': 10, 'align': 'right', 'valign': 'vcenter', 'font_color': 'black',
             'border': 1})
        report_format32 = workbook.add_format(
            {'font_size': 10, 'align': 'right', 'valign': 'vcenter', 'font_color': 'black', 'border': 1})
        report_format4 = workbook.add_format(
            {'font_size': 10, 'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_color': 'black',
             'bg_color': '#dcdde6',
             'border': 1})
        report_format5 = workbook.add_format(
            {'font_size': 10, 'align': 'left', 'valign': 'vcenter', 'font_color': 'black', 'border': 1})
        # worksheet = workbook.add_worksheet("FORMATO")
        worksheet.merge_range(0, 0, 0, 11, data['tipo_rep'], report_format4)
        worksheet.write(1, 0, _('Desde:'), report_format4)
        worksheet.write(1, 1, data['date_s'], report_format5)
        worksheet.write(1, 2, _('Hasta:'), report_format4)
        worksheet.write(1, 3, data['date_e'], report_format5)

        worksheet.write(2, 0, _('Nombre'), report_format4)
        worksheet.write(2, 1, _('Fecha de Liquidación'), report_format4)
        worksheet.write(2, 2, _('Diario de Conciliación'), report_format4)
        worksheet.write(2, 3, _('Lote TC'), report_format4)
        worksheet.write(2, 4, _('Autorización TC'), report_format4)
        worksheet.write(2, 5, _('Valor lineas'), report_format4)
        worksheet.write(2, 6, _('Monto Bancario'), report_format4)
        worksheet.write(2, 7, _('Valor Retención'), report_format4)
        worksheet.write(2, 8, _('Valor de Comisión'), report_format4)
        worksheet.write(2, 9, _('Diferencia'), report_format4)
        worksheet.write(2, 10, _('Estado'), report_format4)
        worksheet.write(2, 11, _('Descripción'), report_format4)
        current_row = 3
        worksheet.autofilter(2, 0, 2, 11)
        for de in data['datos']:
            set_line(workbook, current_row, de)
            current_row += 1

        COLUM_SIZES = [20, 15, 30,  15, 15, 18, 18, 18, 18, 18, 18, 40, 40, 15,]
        for position in range(len(COLUM_SIZES)):
            worksheet.set_column(position, position, COLUM_SIZES[position])
        return self.get_workbook_binary(fp, workbook)


class ReportDifferencesByLoadWizard(models.TransientModel):
    _name = 'report.differences.by.load.wizard'
    _description = 'Reporte de diferencias por carga'

    date_start = fields.Date("Fecha de incio")
    date_end = fields.Date("Fecha de fin")
    all_banks = fields.Boolean(u'Buscar todos los bancos?', default=False)
    bank_id = fields.Many2one('res.bank', string='Banco', required=False)


    def get_report_data(self):

        if self.all_banks:
            payments = self.env['account.payment.tc.cab'].search([('date_move', '>=', self.date_start),
                                                                   ('date_move', '<=', self.date_end),
                                                                   ('ammount_diff','!=', 0.00)
                                                                   ])
        else:
            payments = self.env['account.payment.tc.cab'].search([('date_move', '>=', self.date_start),
                                                                  ('date_move', '<=', self.date_end),
                                                                  ('bank_id', '=', self.bank_id.id),
                                                                  ('ammount_diff', '!=', 0.00)
                                                                  ])
        datos = []
        data = {}
        for movs in payments:
            if round(movs.ammount_diff,2) == 0.00:
                continue
            state = 'Borrador'
            if movs.state == 'done':
                state = 'Conciliado'

            datos.append(
                {'name': str(movs.name),
                 'date': str(movs.date_move),
                 'journal': movs.journal_conciliation.name if movs.journal_conciliation else ' ',
                 'lote': movs.lote_tc or ' ',
                 'auth': movs.auth_tc or ' ',
                 'total': '{:.2f}'.format(round(movs.total_select_payment,2)),
                 'amount_bank': '{:.2f}'.format(round(movs.amount_bank,2)),
                 'amount_retention': '{:.2f}'.format(round(movs.amount_retention,2)),
                 'amount_commission': '{:.2f}'.format(round(movs.amount_commission,2)),
                 'diff': '{:.2f}'.format(round(movs.ammount_diff,2)),
                 'estado': state,
                 'description': movs.description or  ' ',
                 })

        datos = sorted(datos, key=lambda i: i['name'])
        tipo_rep = 'REPORTE DE DIFERENCIA POR CARGA'
        data = {'datos': datos,
                'date_s': str(self.date_start),
                'date_e': str(self.date_end),
                'tipo_rep': tipo_rep,
                }
        report_model = self.env['report.ec_payment_tc.report_differences_by_load']
        return report_model.get_report_xls(data)

    def print_xls(self):
        self.ensure_one()
        if self.date_end < self.date_start:
            raise UserError(_('La fecha de fin no puede ser menor que la de inicio.'))
        if not self.all_banks:
            if not self.bank_id:
                raise UserError(_('Seleccione primero un Banco.'))
        return {'type': 'ir.actions.act_url',
                'url': '/download/saveas?model=%(model)s&record_id=%(record_id)s&method=%(method)s&filename=%(filename)s' % {
                    'filename': 'REPORTE DE DIFERENCIA POR CARGA.xlsx',
                    'model': self._name,
                    'record_id': self.id,
                    'method': 'get_report_data',
                },
                'target': 'new',
                }

