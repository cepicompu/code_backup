# -*- coding: utf-8 -*-
import json
from collections import OrderedDict
from datetime import date as dt_date

from dateutil.relativedelta import relativedelta

from odoo import fields, models, _
from odoo.tools.misc import format_date


class RequestOvertimeReportXlsx(models.AbstractModel):
    _name = 'report.ec_payroll.request_overtime_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Reporte XLSX de Horas Extras'

    def _get_month_sequence(self, date_from, date_to):
        month_list = []
        start = dt_date(date_from.year, date_from.month, 1)
        end = dt_date(date_to.year, date_to.month, 1)
        cursor = start
        while cursor <= end:
            key = cursor.strftime('%Y-%m')
            label = format_date(self.env, cursor, date_format='MMMM yyyy')
            month_list.append((key, label))
            cursor = cursor + relativedelta(months=1)
        return month_list

    def _empty_month_bucket(self):
        return {
            'hours_ext': 0.0,
            'hours_suple': 0.0,
            'hours_night': 0.0,
            'value_ext': 0.0,
            'value_suple': 0.0,
            'value_night': 0.0,
        }

    def _get_analytic_labels(self, contract):
        labels = []
        if not contract:
            return labels
        distribution = contract.analytic_distribution or {}
        if isinstance(distribution, str):
            try:
                distribution = json.loads(distribution)
            except ValueError:
                distribution = {}
        if distribution:
            analytic_model = self.env['account.analytic.account']
            for analytic_id, percentage in distribution.items():
                try:
                    analytic_id = int(analytic_id)
                except (TypeError, ValueError):
                    continue
                account = analytic_model.browse(analytic_id)
                if not account.exists():
                    continue
                label = account.display_name
                if percentage:
                    label = '%s (%s%%)' % (label, percentage)
                labels.append(label)
        elif contract.analytic_account_id:
            labels.append(contract.analytic_account_id.display_name)
        return labels

    def _collect_lines(self, requests, month_keys):
        lines = OrderedDict()
        totals = {key: self._empty_month_bucket() for key in month_keys}

        for request in requests:
            employee = request.employee_id
            emp_id = employee.id
            if emp_id not in lines:
                lines[emp_id] = {
                    'employee': employee,
                    'department': employee.department_id,
                    'identification': employee.identification_id or '',
                    'analytic_accounts': set(),
                    'months': {mk: self._empty_month_bucket() for mk in month_keys},
                }
            entry = lines[emp_id]
            for label in self._get_analytic_labels(request.contract_id):
                entry['analytic_accounts'].add(label)
            month_key = request.date_from.strftime('%Y-%m')
            if month_key not in entry['months']:
                continue
            current = entry['months'][month_key]
            current['hours_ext'] += request.cant_hours_ext or 0.0
            current['hours_suple'] += request.cant_hours_suple or 0.0
            current['hours_night'] += request.cant_hours_night or 0.0
            current['value_ext'] += request.wage_hours_ext or 0.0
            current['value_suple'] += request.wage_hours_suple or 0.0
            current['value_night'] += request.wage_hours_night or 0.0

            total_bucket = totals[month_key]
            total_bucket['hours_ext'] += request.cant_hours_ext or 0.0
            total_bucket['hours_suple'] += request.cant_hours_suple or 0.0
            total_bucket['hours_night'] += request.cant_hours_night or 0.0
            total_bucket['value_ext'] += request.wage_hours_ext or 0.0
            total_bucket['value_suple'] += request.wage_hours_suple or 0.0
            total_bucket['value_night'] += request.wage_hours_night or 0.0

        ordered_lines = sorted(lines.values(), key=lambda l: l['employee'].name or '')
        return ordered_lines, totals

    def generate_xlsx_report(self, workbook, data, wizard):
        date_from = fields.Date.from_string(data.get('date_from'))
        date_to = fields.Date.from_string(data.get('date_to'))

        domain = [
            ('state', '=', 'done'),
            ('date_from', '>=', fields.Date.to_string(date_from)),
            ('date_from', '<=', fields.Date.to_string(date_to)),
        ]
        employee_ids = data.get('employee_ids') or []
        department_ids = data.get('department_ids') or []
        if employee_ids:
            domain.append(('employee_id', 'in', employee_ids))
        if department_ids:
            domain.append(('department_id', 'in', department_ids))

        requests = self.env['request.overtime'].search(domain, order='employee_id, date_from')
        month_seq = self._get_month_sequence(date_from, date_to)
        month_keys = [mk for mk, _ in month_seq]
        lines, totals = self._collect_lines(requests, month_keys)

        sheet = workbook.add_worksheet(_('Horas Extras'))
        title_format = workbook.add_format({'bold': True, 'font_size': 14, 'align': 'center', 'valign': 'vcenter'})
        header_format = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter',
            'bg_color': '#d9e1f2', 'border': 1, 'text_wrap': True,
        })
        sub_header_format = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter',
            'bg_color': '#f2f2f2', 'border': 1, 'text_wrap': True,
        })
        text_format = workbook.add_format({'border': 1})
        number_format = workbook.add_format({'border': 1, 'num_format': '#,##0.00'})
        total_label_format = workbook.add_format({'bold': True, 'border': 1, 'bg_color': '#e2efda'})

        base_headers = [
            (_('Nombre completo'), 25),
            (_('Identificación (DNI/ID)'), 18),
            (_('Área / Departamento'), 25),
            (_('Cuenta analítica'), 25),
        ]
        month_subheaders = [
            _('Horas Extraordinarias'),
            _('Valor Extraordinarias USD'),
            _('Horas Suplementarias'),
            _('Valor Suplementarias USD'),
            _('Horas Nocturnas'),
            _('Valor Nocturnas USD'),
            _('Total horas'),
            _('Valor total USD'),
        ]

        total_section_label = _('Totalizado')
        total_columns = len(base_headers) + len(month_subheaders) * (len(month_seq) + 1)
        sheet.merge_range(0, 0, 0, total_columns - 1, _('Reporte de Horas Extras por Empleado'), title_format)
        period_label = _('Período: %s - %s') % (
            format_date(self.env, date_from, date_format='dd MMMM yyyy'),
            format_date(self.env, date_to, date_format='dd MMMM yyyy'),
        )
        sheet.write(1, 0, period_label)
        sheet.write(
            1,
            len(base_headers),
            _('Generado el: %s') % format_date(self.env, fields.Date.context_today(self), date_format='dd/MM/yyyy'),
        )

        header_row = 3
        sub_header_row = header_row + 1
        col = 0
        for header, width in base_headers:
            sheet.merge_range(header_row, col, sub_header_row, col, header, header_format)
            sheet.set_column(col, col, width)
            col += 1

        for key, label in month_seq:
            span = len(month_subheaders)
            sheet.merge_range(header_row, col, header_row, col + span - 1, label, header_format)
            for idx, sub_label in enumerate(month_subheaders):
                sheet.write(sub_header_row, col + idx, sub_label, sub_header_format)
            col += span
        # aggregated header
        sheet.merge_range(header_row, col, header_row, col + len(month_subheaders) - 1, total_section_label, header_format)
        for idx, sub_label in enumerate(month_subheaders):
            sheet.write(sub_header_row, col + idx, sub_label, sub_header_format)

        data_row = sub_header_row + 1
        month_positions = {mk: idx for idx, (mk, _) in enumerate(month_seq)}
        for line in lines:
            sheet.write(data_row, 0, line['employee'].name or '', text_format)
            sheet.write(data_row, 1, line['identification'], text_format)
            department = line['department'].name if line['department'] else ''
            sheet.write(data_row, 2, department, text_format)
            analytic_label = ', '.join(sorted(line['analytic_accounts'])) if line['analytic_accounts'] else ''
            sheet.write(data_row, 3, analytic_label, text_format)
            for month_key, position in month_positions.items():
                month_data = line['months'][month_key]
                base_col = len(base_headers) + position * len(month_subheaders)
                hours_ext = month_data['hours_ext']
                hours_suple = month_data['hours_suple']
                hours_night = month_data['hours_night']
                total_hours = hours_ext + hours_suple + hours_night
                total_value = month_data['value_ext'] + month_data['value_suple'] + month_data['value_night']
                sheet.write_number(data_row, base_col, hours_ext, number_format)
                sheet.write_number(data_row, base_col + 1, month_data['value_ext'], number_format)
                sheet.write_number(data_row, base_col + 2, hours_suple, number_format)
                sheet.write_number(data_row, base_col + 3, month_data['value_suple'], number_format)
                sheet.write_number(data_row, base_col + 4, hours_night, number_format)
                sheet.write_number(data_row, base_col + 5, month_data['value_night'], number_format)
                sheet.write_number(data_row, base_col + 6, total_hours, number_format)
                sheet.write_number(data_row, base_col + 7, total_value, number_format)
            # Aggregated section
            aggregated_values = self._empty_month_bucket()
            for month_data in line['months'].values():
                aggregated_values['hours_ext'] += month_data['hours_ext']
                aggregated_values['hours_suple'] += month_data['hours_suple']
                aggregated_values['hours_night'] += month_data['hours_night']
                aggregated_values['value_ext'] += month_data['value_ext']
                aggregated_values['value_suple'] += month_data['value_suple']
                aggregated_values['value_night'] += month_data['value_night']
            agg_base = len(base_headers) + len(month_seq) * len(month_subheaders)
            agg_total_hours = aggregated_values['hours_ext'] + aggregated_values['hours_suple'] + aggregated_values['hours_night']
            agg_total_value = aggregated_values['value_ext'] + aggregated_values['value_suple'] + aggregated_values['value_night']
            sheet.write_number(data_row, agg_base, aggregated_values['hours_ext'], number_format)
            sheet.write_number(data_row, agg_base + 1, aggregated_values['value_ext'], number_format)
            sheet.write_number(data_row, agg_base + 2, aggregated_values['hours_suple'], number_format)
            sheet.write_number(data_row, agg_base + 3, aggregated_values['value_suple'], number_format)
            sheet.write_number(data_row, agg_base + 4, aggregated_values['hours_night'], number_format)
            sheet.write_number(data_row, agg_base + 5, aggregated_values['value_night'], number_format)
            sheet.write_number(data_row, agg_base + 6, agg_total_hours, number_format)
            sheet.write_number(data_row, agg_base + 7, agg_total_value, number_format)
            data_row += 1

        if month_seq:
            sheet.write(data_row, 0, _('TOTAL'), total_label_format)
            for i in range(1, len(base_headers)):
                sheet.write_blank(data_row, i, None, total_label_format)
            for month_key, position in month_positions.items():
                bucket = totals[month_key]
                base_col = len(base_headers) + position * len(month_subheaders)
                total_hours = bucket['hours_ext'] + bucket['hours_suple'] + bucket['hours_night']
                total_value = bucket['value_ext'] + bucket['value_suple'] + bucket['value_night']
                sheet.write_number(data_row, base_col, bucket['hours_ext'], total_label_format)
                sheet.write_number(data_row, base_col + 1, bucket['value_ext'], total_label_format)
                sheet.write_number(data_row, base_col + 2, bucket['hours_suple'], total_label_format)
                sheet.write_number(data_row, base_col + 3, bucket['value_suple'], total_label_format)
                sheet.write_number(data_row, base_col + 4, bucket['hours_night'], total_label_format)
                sheet.write_number(data_row, base_col + 5, bucket['value_night'], total_label_format)
                sheet.write_number(data_row, base_col + 6, total_hours, total_label_format)
                sheet.write_number(data_row, base_col + 7, total_value, total_label_format)
            agg_base = len(base_headers) + len(month_seq) * len(month_subheaders)
            total_bucket = self._empty_month_bucket()
            for bucket in totals.values():
                total_bucket['hours_ext'] += bucket['hours_ext']
                total_bucket['hours_suple'] += bucket['hours_suple']
                total_bucket['hours_night'] += bucket['hours_night']
                total_bucket['value_ext'] += bucket['value_ext']
                total_bucket['value_suple'] += bucket['value_suple']
                total_bucket['value_night'] += bucket['value_night']
            agg_total_hours = total_bucket['hours_ext'] + total_bucket['hours_suple'] + total_bucket['hours_night']
            agg_total_value = total_bucket['value_ext'] + total_bucket['value_suple'] + total_bucket['value_night']
            sheet.write_number(data_row, agg_base, total_bucket['hours_ext'], total_label_format)
            sheet.write_number(data_row, agg_base + 1, total_bucket['value_ext'], total_label_format)
            sheet.write_number(data_row, agg_base + 2, total_bucket['hours_suple'], total_label_format)
            sheet.write_number(data_row, agg_base + 3, total_bucket['value_suple'], total_label_format)
            sheet.write_number(data_row, agg_base + 4, total_bucket['hours_night'], total_label_format)
            sheet.write_number(data_row, agg_base + 5, total_bucket['value_night'], total_label_format)
            sheet.write_number(data_row, agg_base + 6, agg_total_hours, total_label_format)
            sheet.write_number(data_row, agg_base + 7, agg_total_value, total_label_format)
