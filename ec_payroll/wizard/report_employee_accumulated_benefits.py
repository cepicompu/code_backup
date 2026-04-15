import json
import select
from datetime import datetime
from odoo.exceptions import UserError
from odoo import api, fields, models, tools, _
from odoo.tools import date_utils, io
try:
    from odoo.tools.misc import xlsxwriter, workbook
except ImportError:
    import xlsxwriter
import io

class reportEmployeeBenefits(models.AbstractModel):
    _name = 'report.ec_payroll_advance.report_employee_accumulated_benefits'

    @api.model
    def get_details(self, data=False, totales=False, d_type=False, current_date=False, period_year=False):
        return {'d_type': d_type,
                'vals': data,
                'currency_id': self.env.company.currency_id,
                'total_dic': totales['total_dic'],
                'total_ene': totales['total_ene'],
                'total_feb': totales['total_feb'],
                'total_marz': totales['total_marz'],
                'total_abr': totales['total_abr'],
                'total_may': totales['total_may'],
                'total_jun': totales['total_jun'],
                'total_jul': totales['total_jul'],
                'total_ago': totales['total_ago'],
                'total_sep': totales['total_sep'],
                'total_oct': totales['total_oct'],
                'total_nov': totales['total_nov'],
                'total_val': totales['total_val'],
                'total_ant': totales['total_ant'],
                'total_liq': totales['total_liq'],
                'current_date': current_date,
                'period_year': period_year,
                'period_year_ant': period_year -1,
                }

    @api.model
    def _get_report_values(self, docids, data=None):
        data = dict(data or {})
        data.update(self.get_details(data['reporte'], data['totales'], data['d_type'], data['current_date'], data['period_year']))
        return data


class reportEmployeeBenefits(models.TransientModel):
    _name = 'report.employee.accumulated.benefits.wizard'



    select_tenth = fields.Selection([('thirt',u'Décimo Tercero'),
                                     ('fourt',u'Décimo Cuarto'),
                                     ('reserve_funds',u'Fondo de Reserva')],
                                     string=u'Seleccione Acumulación :')
    year_acum = fields.Many2one('account.fiscalyear', u'Seleccione Año')

    def print_pdf_report(self):
        if self.select_tenth== 'thirt':
            employees = self.env['hr.contract'].search([('thirteenth_payment', '=', 'accumulated')])
        elif self.select_tenth=='fourt':
            employees = self.env['hr.contract'].search([('fourteenth_payment', '=', 'accumulated')])
        else:
            employees = self.env['hr.contract'].search([('reserve_payment', '=', 'accumulated')])
        report = []
        totales = []
        total_dic = 0.00
        total_ene = 0.00
        total_feb = 0.00
        total_marz = 0.00
        total_abr = 0.00
        total_may = 0.00
        total_jun = 0.00
        total_jul = 0.00
        total_ago = 0.00
        total_sep = 0.00
        total_oct = 0.00
        total_nov = 0.00
        total_val = 0.00
        total_ant = 0.00
        data = {}
        for exp in employees:
            provisions = self.env['payroll.provision'].search([('employee_id', '=', exp.employee_id.id),
                                                               ('year', '=', int(self.year_acum.name))])
            dic = 0.00
            ene = 0.00
            feb = 0.00
            marz = 0.00
            abr = 0.00
            may = 0.00
            jun = 0.00
            jul = 0.00
            ago = 0.00
            sep = 0.00
            oct = 0.00
            nov = 0.00
            daydic = 0.00
            dayene = 0.00
            dayfeb = 0.00
            daymarz = 0.00
            dayabr = 0.00
            daymay = 0.00
            dayjun = 0.00
            dayjul = 0.00
            dayago = 0.00
            daysep = 0.00
            dayoct = 0.00
            daynov = 0.00
            total = 0.00
            if len(provisions) > 0:
                year_dic = provisions[0].year - 1
                provision = self.env['payroll.provision'].search([('employee_id', '=', exp.employee_id.id),
                                                                  ('year', '=', year_dic),
                                                                  ('month', '=', 12)])
                if len(provision) > 0:
                    if self.select_tenth == 'thirt':
                        dic = provision[0].thirteenth
                    elif self.select_tenth == 'fourt':
                        dic = provision[0].fourteenth
                    else:
                        dic = provision[0].reserve_funds
                    total_dic += dic
                    daydic = provision[0].days_payroll

            for prov in provisions:
                if prov.month == 1:
                    if self.select_tenth == 'thirt':
                        ene = prov.thirteenth
                    elif self.select_tenth == 'fourt':
                        ene = prov.fourteenth
                    else:
                        ene = prov.reserve_funds
                    total_ene += ene
                    dayene = prov.days_payroll
                if prov.month == 2:
                    if self.select_tenth == 'thirt':
                        feb = prov.thirteenth
                    elif self.select_tenth == 'fourt':
                        feb = prov.fourteenth
                    else:
                        feb = prov.reserve_funds
                    total_feb += feb
                    dayfeb = prov.days_payroll
                if prov.month == 3:
                    if self.select_tenth == 'thirt':
                        marz = prov.thirteenth
                    elif self.select_tenth == 'fourt':
                        marz = prov.fourteenth
                    else:
                        marz = prov.reserve_funds
                    total_marz += marz
                    daymarz = prov.days_payroll
                if prov.month == 4:
                    if self.select_tenth == 'thirt':
                        abr = prov.thirteenth
                    elif self.select_tenth == 'fourt':
                        abr = prov.fourteenth
                    else:
                        abr = prov.reserve_funds
                    total_abr += abr
                    dayabr = prov.days_payroll
                if prov.month == 5:
                    if self.select_tenth == 'thirt':
                        may = prov.thirteenth
                    elif self.select_tenth == 'fourt':
                        may = prov.fourteenth
                    else:
                        may = prov.reserve_funds
                    total_may += may
                    daymay = prov.days_payroll
                if prov.month == 6:
                    if self.select_tenth == 'thirt':
                        jun = prov.thirteenth
                    elif self.select_tenth == 'fourt':
                        jun = prov.fourteenth
                    else:
                        jun = prov.reserve_funds
                    total_jun += jun
                    dayjun = prov.days_payroll
                if prov.month == 7:
                    if self.select_tenth == 'thirt':
                        jul = prov.thirteenth
                    elif self.select_tenth == 'fourt':
                        jul = prov.fourteenth
                    else:
                        jul = prov.reserve_funds
                    total_jul += jul
                    dayjul = prov.days_payroll
                if prov.month == 8:
                    if self.select_tenth == 'thirt':
                        ago = prov.thirteenth
                    elif self.select_tenth == 'fourt':
                        ago = prov.fourteenth
                    else:
                        ago = prov.reserve_funds
                    total_ago += ago
                    dayago = prov.days_payroll
                if prov.month == 9:
                    if self.select_tenth == 'thirt':
                        sep = prov.thirteenth
                    elif self.select_tenth == 'fourt':
                        sep = prov.fourteenth
                    else:
                        sep = prov.reserve_funds
                    total_sep += sep
                    daysep = prov.days_payroll
                if prov.month == 10:
                    if self.select_tenth == 'thirt':
                        oct = prov.thirteenth
                    elif self.select_tenth == 'fourt':
                        oct = prov.fourteenth
                    else:
                        oct = prov.reserve_funds
                    total_oct += oct
                    dayoct = prov.days_payroll
                if prov.month == 11:
                    if self.select_tenth == 'thirt':
                        nov = prov.thirteenth
                    elif self.select_tenth == 'fourt':
                        nov = prov.fourteenth
                    else:
                        nov = prov.reserve_funds
                    total_nov += nov
                    daynov = prov.days_payroll
            total = ene + feb + marz + abr + may + jun + jul + ago + sep + oct + nov + dic
            totald = dayene + dayfeb + daymarz + dayabr + daymay + dayjun + dayjul + dayago + daysep + dayoct + daynov + daydic
            total_val += total
            anticipo = 0.00
            total_ant += anticipo
            report.append({'employee': str(exp.name.upper()),
                           'identification': str(exp.employee_id.identification_id),
                           'department': str(exp.department_id.name.upper()),
                           'dic': dic,  # hay que ver que desarolla harry
                           'ene': ene,
                           'feb': feb,
                           'marz': marz,
                           'abr': abr,
                           'may': may,
                           'jun': jun,
                           'jul': jul,
                           'ago': ago,
                           'sep': sep,
                           'oct': oct,
                           'nov': nov,
                           'daydic': daydic,  # hay que ver que desarolla harry
                           'dayene': dayene,
                           'dayfeb': dayfeb,
                           'daymarz': daymarz,
                           'dayabr': dayabr,
                           'daymay': daymay,
                           'dayjun': dayjun,
                           'dayjul': dayjul,
                           'dayago': dayago,
                           'daysep': daysep,
                           'dayoct': dayoct,
                           'daynov': daynov,
                           'total_year': total,
                           'total_days': totald,
                           'anticipo': anticipo,  # igual
                           'liquido': round((total - anticipo), 2),  # igual
                           })
        totales.append({'total_dic': total_dic,
                        'total_ene': total_ene,
                        'total_feb': total_feb,
                        'total_marz': total_marz,
                        'total_abr': total_abr,
                        'total_may': total_may,
                        'total_jun': total_jun,
                        'total_jul': total_jul,
                        'total_ago': total_ago,
                        'total_sep': total_sep,
                        'total_oct': total_oct,
                        'total_nov': total_nov,
                        'total_val': total_val,
                        'total_ant': total_ant,
                        'total_liq': round((total_val - total_ant), 2),
                        })
        report = sorted(report, key=lambda i: i['employee'])
        data.update({'reporte': report,
                     'totales': totales[0],
                     'd_type': self.select_tenth,
                     'current_date': datetime.today(),
                     'period_year': int(self.year_acum.name)
                     })
        return self.env.ref('ec_payroll_advance.action_report_employee_accumulated_benefits').report_action([], data=data)
    	


    def print_xls_report(self):

        if self.select_tenth == 'thirt':
            employees = self.env['hr.contract'].search([('thirteenth_payment', '=', 'accumulated')])
        elif self.select_tenth == 'fourt':
            employees = self.env['hr.contract'].search([('fourteenth_payment', '=', 'accumulated')])
        else:
            employees = self.env['hr.contract'].search([('reserve_payment', '=', 'accumulated')])
        report = []
        totales = []
        total_dic = 0.00
        total_ene = 0.00
        total_feb = 0.00
        total_marz = 0.00
        total_abr = 0.00
        total_may = 0.00
        total_jun = 0.00
        total_jul = 0.00
        total_ago = 0.00
        total_sep = 0.00
        total_oct = 0.00
        total_nov = 0.00
        total_val = 0.00
        total_ant = 0.00
        data = {}
        for exp in employees:
            provisions = self.env['payroll.provision'].search([('employee_id', '=', exp.employee_id.id),
                                                               ('year', '=', int(self.year_acum.name))])
            dic = 0.00
            ene = 0.00
            feb = 0.00
            marz = 0.00
            abr = 0.00
            may = 0.00
            jun = 0.00
            jul = 0.00
            ago = 0.00
            sep = 0.00
            oct = 0.00
            nov = 0.00
            daydic = 0.00
            dayene = 0.00
            dayfeb = 0.00
            daymarz = 0.00
            dayabr = 0.00
            daymay = 0.00
            dayjun = 0.00
            dayjul = 0.00
            dayago = 0.00
            daysep = 0.00
            dayoct = 0.00
            daynov = 0.00
            total = 0.00
            if len(provisions) > 0:
                year_dic = provisions[0].year - 1
                provision = self.env['payroll.provision'].search([('employee_id', '=', exp.employee_id.id),
                                                                  ('year', '=', year_dic),
                                                                  ('month', '=', 12)])
                if len(provision) > 0:
                    if self.select_tenth == 'thirt':
                        dic = provision[0].thirteenth
                    elif self.select_tenth == 'fourt':
                        dic = provision[0].fourteenth
                    else:
                        dic = provision[0].reserve_funds
                    total_dic += dic
                    daydic = provision[0].days_payroll

            for prov in provisions:
                if prov.month == 1:
                    if self.select_tenth == 'thirt':
                        ene = prov.thirteenth
                    elif self.select_tenth == 'fourt':
                        ene = prov.fourteenth
                    else:
                        ene = prov.reserve_funds
                    total_ene += ene
                    dayene = prov.days_payroll
                if prov.month == 2:
                    if self.select_tenth == 'thirt':
                        feb = prov.thirteenth
                    elif self.select_tenth == 'fourt':
                        feb = prov.fourteenth
                    else:
                        feb = prov.reserve_funds
                    total_feb += feb
                    dayfeb = prov.days_payroll
                if prov.month == 3:
                    if self.select_tenth == 'thirt':
                        marz = prov.thirteenth
                    elif self.select_tenth == 'fourt':
                        marz = prov.fourteenth
                    else:
                        marz = prov.reserve_funds
                    total_marz += marz
                    daymarz = prov.days_payroll
                if prov.month == 4:
                    if self.select_tenth == 'thirt':
                        abr = prov.thirteenth
                    elif self.select_tenth == 'fourt':
                        abr = prov.fourteenth
                    else:
                        abr = prov.reserve_funds
                    total_abr += abr
                    dayabr = prov.days_payroll
                if prov.month == 5:
                    if self.select_tenth == 'thirt':
                        may = prov.thirteenth
                    elif self.select_tenth == 'fourt':
                        may = prov.fourteenth
                    else:
                        may = prov.reserve_funds
                    total_may += may
                    daymay = prov.days_payroll
                if prov.month == 6:
                    if self.select_tenth == 'thirt':
                        jun = prov.thirteenth
                    elif self.select_tenth == 'fourt':
                        jun = prov.fourteenth
                    else:
                        jun = prov.reserve_funds
                    total_jun += jun
                    dayjun = prov.days_payroll
                if prov.month == 7:
                    if self.select_tenth == 'thirt':
                        jul = prov.thirteenth
                    elif self.select_tenth == 'fourt':
                        jul = prov.fourteenth
                    else:
                        jul = prov.reserve_funds
                    total_jul += jul
                    dayjul = prov.days_payroll
                if prov.month == 8:
                    if self.select_tenth == 'thirt':
                        ago = prov.thirteenth
                    elif self.select_tenth == 'fourt':
                        ago = prov.fourteenth
                    else:
                        ago = prov.reserve_funds
                    total_ago += ago
                    dayago = prov.days_payroll
                if prov.month == 9:
                    if self.select_tenth == 'thirt':
                        sep = prov.thirteenth
                    elif self.select_tenth == 'fourt':
                        sep = prov.fourteenth
                    else:
                        sep = prov.reserve_funds
                    total_sep += sep
                    daysep = prov.days_payroll
                if prov.month == 10:
                    if self.select_tenth == 'thirt':
                        oct = prov.thirteenth
                    elif self.select_tenth == 'fourt':
                        oct = prov.fourteenth
                    else:
                        oct = prov.reserve_funds
                    total_oct += oct
                    dayoct = prov.days_payroll
                if prov.month == 11:
                    if self.select_tenth == 'thirt':
                        nov = prov.thirteenth
                    elif self.select_tenth == 'fourt':
                        nov = prov.fourteenth
                    else:
                        nov = prov.reserve_funds
                    total_nov += nov
                    daynov = prov.days_payroll
            total = ene + feb + marz + abr + may + jun + jul + ago + sep + oct + nov + dic
            totald = dayene + dayfeb + daymarz + dayabr + daymay + dayjun + dayjul + dayago + daysep + dayoct + daynov + daydic
            total_val += total
            anticipo = 0.00
            total_ant += anticipo
            report.append({'employee': str(exp.name.upper()),
                           'identification': str(exp.employee_id.identification_id),
                           'department': str(exp.department_id.name.upper()),
                           'dic': dic,  # hay que ver que desarolla harry
                           'ene': ene,
                           'feb': feb,
                           'marz': marz,
                           'abr': abr,
                           'may': may,
                           'jun': jun,
                           'jul': jul,
                           'ago': ago,
                           'sep': sep,
                           'oct': oct,
                           'nov': nov,
                           'daydic': daydic,  # hay que ver que desarolla harry
                           'dayene': dayene,
                           'dayfeb': dayfeb,
                           'daymarz': daymarz,
                           'dayabr': dayabr,
                           'daymay': daymay,
                           'dayjun': dayjun,
                           'dayjul': dayjul,
                           'dayago': dayago,
                           'daysep': daysep,
                           'dayoct': dayoct,
                           'daynov': daynov,
                           'total_year': total,
                           'total_days': totald,
                           'anticipo': anticipo,  # igual
                           'liquido': round((total - anticipo), 2),  # igual
                           })
        totales.append({'total_dic': total_dic,
                        'total_ene': total_ene,
                        'total_feb': total_feb,
                        'total_marz': total_marz,
                        'total_abr': total_abr,
                        'total_may': total_may,
                        'total_jun': total_jun,
                        'total_jul': total_jul,
                        'total_ago': total_ago,
                        'total_sep': total_sep,
                        'total_oct': total_oct,
                        'total_nov': total_nov,
                        'total_val': total_val,
                        'total_ant': total_ant,
                        'total_liq': round((total_val - total_ant), 2),
                        })
        report = sorted(report, key=lambda i: i['employee'])
        data.update({'reporte': report,
                     'totales': totales[0],
                     'd_type': self.select_tenth,
                     'current_date': datetime.today(),
                     'period_year': int(self.year_acum.name)
                     })
        return {
            'type': 'ir_actions_xlsx_download',
            'data': {'model': 'report.employee.accumulated.benefits.wizard',
                     'options': json.dumps(data, default=date_utils.json_default),
                     'output_format': 'xlsx',
                     'report_name': 'Reporte de Beneficios Sociales',
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

        sheet = workbook.add_worksheet(u'REPORTE DE BENEFICIOS SOCIALES')
        headers={}
        if data['d_type'] == 'fourt':
            sheet.write(3, 0, _('Empleado'), report_format2)
            sheet.write(3, 1, _(u'Identificación'), report_format2)
            sheet.write(3, 2, _(u'Clasificación'), report_format2)
            sheet.write(3, 3, _('Departamento'), report_format2)
            sheet.write(3, 4, _('Monto'), report_format2)
            sheet.write(3, 5, _(u'Días'), report_format2)
            sheet.write(3, 6, _('Monto'), report_format2)
            sheet.write(3, 7, _(u'Días'), report_format2)
            sheet.write(3, 8, _('Monto'), report_format2)
            sheet.write(3, 9, _(u'Días'), report_format2)
            sheet.write(3, 10, _('Monto'), report_format2)
            sheet.write(3, 11, _(u'Días'), report_format2)
            sheet.write(3, 12, _('Monto'), report_format2)
            sheet.write(3, 13, _(u'Días'), report_format2)
            sheet.write(3, 14, _('Monto'), report_format2)
            sheet.write(3, 15, _(u'Días'), report_format2)
            sheet.write(3, 16, _('Monto'), report_format2)
            sheet.write(3, 17, _(u'Días'), report_format2)
            sheet.write(3, 18, _('Monto'), report_format2)
            sheet.write(3, 19, _(u'Días'), report_format2)
            sheet.write(3, 20, _('Monto'), report_format2)
            sheet.write(3, 21, _(u'Días'), report_format2)
            sheet.write(3, 22, _('Monto'), report_format2)
            sheet.write(3, 23, _(u'Días'), report_format2)
            sheet.write(3, 24, _('Monto'), report_format2)
            sheet.write(3, 25, _(u'Días'), report_format2)
            sheet.write(3, 26, _('Monto'), report_format2)
            sheet.write(3, 27, _(u'Días'), report_format2)
            sheet.write(3, 28, _('Monto'), report_format2)
            sheet.write(3, 29, _(u'Días'), report_format2)
            sheet.merge_range(2, 4, 2, 5, _('Diciembre'), report_format2)
            sheet.merge_range(2, 6, 2, 7, _('Enero'), report_format2)
            sheet.merge_range(2, 8, 2, 9, _('Febrero'), report_format2)
            sheet.merge_range(2, 10, 2, 11, _('Marzo'), report_format2)
            sheet.merge_range(2, 12, 2, 13, _('Abril'), report_format2)
            sheet.merge_range(2, 14, 2, 15, _('Mayo'), report_format2)
            sheet.merge_range(2, 16, 2, 17, _('Junio'), report_format2)
            sheet.merge_range(2, 18, 2, 19, _('Julio'), report_format2)
            sheet.merge_range(2, 20, 2, 21, _('Agosto'), report_format2)
            sheet.merge_range(2, 22, 2, 23, _('Septiembre'), report_format2)
            sheet.merge_range(2, 24, 2, 25, _('Octubre'), report_format2)
            sheet.merge_range(2, 26, 2, 27, _('Noviembre'), report_format2)
            sheet.merge_range(2, 28, 2, 29, _('Total Anual'), report_format2)
            sheet.write(3, 30, _('Anticipos'), report_format2)
            sheet.write(3, 31, _('Líquido'), report_format2)
        else:

            sheet.write(3, 0, _('Empleado'), report_format2)
            sheet.write(3, 1, _(u'Identificación'), report_format2)
            sheet.write(3, 2, _(u'Clasificación'), report_format2)
            sheet.write(3, 3, _('Departamento'), report_format2)
            sheet.write(3, 4, _('Diciembre'), report_format2)
            sheet.write(3, 5, _('Enero'), report_format2)
            sheet.write(3, 6, _('Febrero'), report_format2)
            sheet.write(3, 7, _('Marzo'), report_format2)
            sheet.write(3, 8, _('Abril'), report_format2)
            sheet.write(3, 9, _('Mayo'), report_format2)
            sheet.write(3, 10, _('Junio'), report_format2)
            sheet.write(3, 11, _('Julio'), report_format2)
            sheet.write(3, 12, _('Agosto'), report_format2)
            sheet.write(3, 13, _('Septiembre'), report_format2)
            sheet.write(3, 14, _('Octubre'), report_format2)
            sheet.write(3, 15, _('Noviembre'), report_format2)
            sheet.write(3, 16, _('Total Anual'), report_format2)
            sheet.write(3, 17, _('Anticipos'), report_format2)
            sheet.write(3, 18, _('Líquido'), report_format2)




        if data['d_type'] == 'thirt':
            sheet.merge_range(0, 0, 0, 18, _(u'REPORTE DE ACUMULACIONES DE DÉCIMOS TERCEROS' + ' - ' + str(data['current_date'])), report_format)
            sheet.merge_range(1, 0, 1, 18, _(u'PERIODO: 01/12/' + str(data['period_year'] - 1) + ' - 31/11/' + str(
                data['period_year'])), report_format)
        elif data['d_type'] == 'fourt':
            sheet.merge_range(0, 0, 0, 31, _(u'REPORTE DE ACUMULACIONES DE DÉCIMOS CUARTOS' +  ' - ' + str(data['current_date'])), report_format)
            sheet.merge_range(1, 0, 1, 31, _(u'PERIODO: 01/12/' + str(data['period_year'] - 1) + ' - 31/11/' + str(
                data['period_year'])), report_format)
        else:
            sheet.merge_range(0, 0, 0, 18, _(u'REPORTE DE ACUMULACIONES DE FONDOS DE RESERVA' + ' - ' + str(data['current_date'])), report_format)
            sheet.merge_range(1, 0, 1, 18, _(u'PERIODO: 01/12/' + str(data['period_year']-1) + ' - 31/11/' + str(data['period_year'])), report_format)


        obj = self.env['report.ec_payroll_advance.report_employee_accumulated_benefits']._get_report_values(docids,data)

        for line in obj:
            r=line

        row=4
        if obj:
            if data['d_type'] == 'fourt':
                for lrow in obj['vals']:
                    sheet.write(row, 0, lrow['employee'], )
                    sheet.write(row, 1, lrow['identification'], )
                    sheet.write(row, 3, lrow['department'], )
                    sheet.write(row, 4, lrow['dic'], )
                    sheet.write(row, 5, lrow['daydic'], )
                    sheet.write(row, 6, lrow['ene'], )
                    sheet.write(row, 7, lrow['dayene'], )
                    sheet.write(row, 8, lrow['feb'], )
                    sheet.write(row, 9, lrow['dayfeb'], )
                    sheet.write(row, 10, lrow['marz'], )
                    sheet.write(row, 11, lrow['daymarz'], )
                    sheet.write(row, 12, lrow['abr'], )
                    sheet.write(row, 13, lrow['dayabr'], )
                    sheet.write(row, 14, lrow['may'], )
                    sheet.write(row, 15, lrow['daymay'], )
                    sheet.write(row, 16, lrow['jun'], )
                    sheet.write(row, 17, lrow['dayjun'], )
                    sheet.write(row, 18, lrow['jul'], )
                    sheet.write(row, 19, lrow['dayjul'], )
                    sheet.write(row, 20, lrow['ago'], )
                    sheet.write(row, 21, lrow['dayago'], )
                    sheet.write(row, 22, lrow['sep'], )
                    sheet.write(row, 23, lrow['daysep'], )
                    sheet.write(row, 24, lrow['oct'], )
                    sheet.write(row, 25, lrow['dayoct'], )
                    sheet.write(row, 26, lrow['nov'], )
                    sheet.write(row, 27, lrow['daynov'], )
                    sheet.write(row, 28, lrow['total_year'], )
                    sheet.write(row, 29, lrow['total_days'], )
                    sheet.write(row, 30, lrow['anticipo'], )
                    sheet.write(row, 31, lrow['liquido'], )
                    row += 1
                sheet.merge_range(row, 0, row, 3, _('TOTALES'), report_format2)
                sheet.merge_range(row, 4, row, 5, '$ ' + str(round(obj['total_dic'], 2)), report_format2)
                sheet.merge_range(row, 6, row, 7, '$ ' + str(round(obj['total_ene'], 2)), report_format2)
                sheet.merge_range(row, 8, row, 9, '$ ' + str(round(obj['total_feb'], 2)), report_format2)
                sheet.merge_range(row, 10, row, 11, '$ ' + str(round(obj['total_marz'], 2)), report_format2)
                sheet.merge_range(row, 12, row, 13, '$ ' + str(round(obj['total_abr'], 2)), report_format2)
                sheet.merge_range(row, 14, row, 15, '$ ' + str(round(obj['total_may'], 2)), report_format2)
                sheet.merge_range(row, 16, row, 17, '$ ' + str(round(obj['total_jun'], 2)), report_format2)
                sheet.merge_range(row, 18, row, 19, '$ ' + str(round(obj['total_jul'], 2)), report_format2)
                sheet.merge_range(row, 20, row, 21, '$ ' + str(round(obj['total_ago'], 2)), report_format2)
                sheet.merge_range(row, 22, row, 23, '$ ' + str(round(obj['total_sep'], 2)), report_format2)
                sheet.merge_range(row, 24, row, 25, '$ ' + str(round(obj['total_oct'], 2)), report_format2)
                sheet.merge_range(row, 26, row, 27, '$ ' + str(round(obj['total_nov'], 2)), report_format2)
                sheet.merge_range(row, 28, row, 29, '$ ' + str(round(obj['total_val'], 2)), report_format2)
                sheet.write(row, 30, '$ ' + str(round(obj['total_ant'], 2)), report_format2)
                sheet.write(row, 31, '$ ' + str(round(obj['total_liq'], 2)), report_format2)
            else:
                for lrow in obj['vals']:
                    sheet.write(row, 0, lrow['employee'], )
                    sheet.write(row, 1, lrow['identification'], )
                    sheet.write(row, 3, lrow['department'], )
                    sheet.write(row, 4, lrow['dic'], )
                    sheet.write(row, 5, lrow['ene'], )
                    sheet.write(row, 6, lrow['feb'], )
                    sheet.write(row, 7, lrow['marz'], )
                    sheet.write(row, 8, lrow['abr'], )
                    sheet.write(row, 9, lrow['may'], )
                    sheet.write(row, 10, lrow['jun'], )
                    sheet.write(row, 11, lrow['jul'], )
                    sheet.write(row, 12, lrow['ago'], )
                    sheet.write(row, 13, lrow['sep'], )
                    sheet.write(row, 14, lrow['oct'], )
                    sheet.write(row, 15, lrow['nov'], )
                    sheet.write(row, 16, lrow['total_year'], )
                    sheet.write(row, 17, lrow['anticipo'], )
                    sheet.write(row, 18, lrow['liquido'], )
                    # sheet.write(row, headers['7'], '$ ' + str(round(lrow['amount'], 2)), )
                    row += 1
                sheet.merge_range(row, 0, row, 3, _('TOTALES'), report_format2)
                sheet.write(row, 4, '$ ' + str(round(obj['total_dic'], 2)), report_format2)
                sheet.write(row, 5, '$ ' + str(round(obj['total_ene'], 2)), report_format2)
                sheet.write(row, 6, '$ ' + str(round(obj['total_feb'], 2)), report_format2)
                sheet.write(row, 7, '$ ' + str(round(obj['total_marz'], 2)), report_format2)
                sheet.write(row, 8, '$ ' + str(round(obj['total_abr'], 2)), report_format2)
                sheet.write(row, 9, '$ ' + str(round(obj['total_may'], 2)), report_format2)
                sheet.write(row, 10, '$ ' + str(round(obj['total_jun'], 2)), report_format2)
                sheet.write(row, 11, '$ ' + str(round(obj['total_jul'], 2)), report_format2)
                sheet.write(row, 12, '$ ' + str(round(obj['total_ago'], 2)), report_format2)
                sheet.write(row, 13, '$ ' + str(round(obj['total_sep'], 2)), report_format2)
                sheet.write(row, 14, '$ ' + str(round(obj['total_oct'], 2)), report_format2)
                sheet.write(row, 15, '$ ' + str(round(obj['total_nov'], 2)), report_format2)
                sheet.write(row, 16, '$ ' + str(round(obj['total_val'], 2)), report_format2)
                sheet.write(row, 17, '$ ' + str(round(obj['total_ant'], 2)), report_format2)
                sheet.write(row, 18, '$ ' + str(round(obj['total_liq'], 2)), report_format2)

        if data['d_type'] == 'fourt':
            COLUM_SIZES = [35, 18, 25, 35, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 10, 10, 25, 25, 25, 25]
            for position in range(len(COLUM_SIZES)):
                sheet.set_column(position, position, COLUM_SIZES[position])


        else:
            COLUM_SIZES = [35, 18, 25, 35, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 20, 25, 25, 25, 25]
            for position in range(len(COLUM_SIZES)):
                sheet.set_column(position, position, COLUM_SIZES[position])

        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()
