# -*- coding: utf-8 -*-
"""
Modelos persistentes para los reportes del Ministerio de Trabajo (Décimos y Utilidades).

Contiene:
- ec.payroll.report: cabecera del reporte (uno por generación)
- ec.payroll.report.line: línea por empleado procesado (incluidos y excluidos)
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import base64
import io
import csv
import calendar
from datetime import date

try:
    import pandas as pd
except ImportError:
    pd = None


class EcPayrollReport(models.Model):
    """Cabecera persistente de un reporte de décimos o utilidades."""

    _name = 'ec.payroll.report'
    _description = 'Reporte de Nómina Ministerio de Trabajo'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    # -------------------------------------------------------------------------
    # Campos principales
    # -------------------------------------------------------------------------
    name = fields.Char(
        string='Nombre',
        compute='_compute_name',
        store=True,
    )
    report_type = fields.Selection([
        ('13th', 'Décimo Tercero'),
        ('14th_sierra', 'Décimo Cuarto - Sierra'),
        ('14th_costa', 'Décimo Cuarto - Costa'),
    ], string='Tipo de Reporte', required=True, default='13th')

    fiscalyear_config_id = fields.Many2one(
        'hr.fiscalyear.config',
        string='Año Fiscal',
        required=True,
        ondelete='restrict',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
    )

    date_start = fields.Date(
        string='Desde',
        compute='_compute_dates',
        store=True,
    )
    date_end = fields.Date(
        string='Hasta',
        compute='_compute_dates',
        store=True,
    )

    sbu_used = fields.Float(
        string='SBU Año de Pago',
        digits=(10, 2),
        readonly=True,
        help='SBU vigente al cierre del período (año de pago). El cálculo aplica el SBU '
             'correspondiente a cada segmento anual dentro del período.',
    )

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('calculated', 'Calculado'),
        ('exported', 'Exportado'),
    ], string='Estado', default='draft', required=True, tracking=True)

    line_ids = fields.One2many(
        'ec.payroll.report.line',
        'report_id',
        string='Líneas',
    )
    included_line_ids = fields.One2many(
        'ec.payroll.report.line',
        'report_id',
        string='Empleados Incluidos',
        domain=[('included', '=', True)],
    )
    excluded_line_ids = fields.One2many(
        'ec.payroll.report.line',
        'report_id',
        string='Empleados Excluidos',
        domain=[('included', '=', False)],
    )

    # Resumen
    total_employees = fields.Integer(
        string='Empleados Incluidos',
        compute='_compute_totals',
        store=True,
    )
    total_excluded = fields.Integer(
        string='Empleados Excluidos',
        compute='_compute_totals',
        store=True,
    )
    total_amount = fields.Float(
        string='Total a Pagar',
        digits=(10, 2),
        compute='_compute_totals',
        store=True,
    )
    total_cash_management = fields.Float(
        string='Total Cash Management',
        digits=(10, 2),
        compute='_compute_totals',
        store=True,
    )

    notes = fields.Text(string='Observaciones')

    # Datos para Cash Management
    company_partner_bank_id = fields.Many2one(
        'res.partner.bank',
        string='Cuenta Bancaria Empresa',
        domain="[('partner_id.company_ids', 'in', [company_id])]",
        help='Cuenta bancaria de la empresa desde donde se realizarán los pagos.',
    )
    payment_date = fields.Date(
        string='Fecha de Pago',
        default=fields.Date.today,
        help='Fecha en que se realizarán los pagos.',
    )

    # -------------------------------------------------------------------------
    # Métodos compute
    # -------------------------------------------------------------------------

    @api.depends('report_type', 'fiscalyear_config_id', 'company_id')
    def _compute_name(self):
        """Genera el nombre descriptivo del reporte, p. ej. 'Décimo Tercero – 2025 – MiEmpresa'."""
        labels = {
            '13th': 'Décimo Tercero',
            '14th_sierra': 'Décimo Cuarto Sierra',
            '14th_costa': 'Décimo Cuarto Costa',
        }
        for rec in self:
            tipo = labels.get(rec.report_type, rec.report_type or '')
            year = ''
            if rec.fiscalyear_config_id and rec.fiscalyear_config_id.fiscalyear_id:
                year = str(rec.fiscalyear_config_id.fiscalyear_id.date_stop.year)
            company = rec.company_id.name or ''
            parts = [p for p in [tipo, year, company] if p]
            rec.name = ' – '.join(parts) if parts else _('Nuevo Reporte')

    @api.depends('report_type', 'fiscalyear_config_id')
    def _compute_dates(self):
        """Calcula date_start y date_end según el tipo de reporte y el año fiscal."""
        for rec in self:
            if rec.report_type and rec.fiscalyear_config_id and rec.fiscalyear_config_id.fiscalyear_id:
                year = rec.fiscalyear_config_id.fiscalyear_id.date_stop.year
                ds, de = rec._get_date_range(rec.report_type, year)
                rec.date_start = ds
                rec.date_end = de
            else:
                rec.date_start = False
                rec.date_end = False

    @api.depends('line_ids.valor_pago', 'line_ids.valor_cash_management', 'line_ids.included')
    def _compute_totals(self):
        """Calcula totales de empleados incluidos, excluidos y montos a pagar."""
        for rec in self:
            incluidas = rec.line_ids.filtered(lambda l: l.included)
            excluidas = rec.line_ids.filtered(lambda l: not l.included)
            rec.total_employees = len(incluidas)
            rec.total_excluded = len(excluidas)
            rec.total_amount = sum(incluidas.mapped('valor_pago'))
            rec.total_cash_management = sum(incluidas.mapped('valor_cash_management'))

    # -------------------------------------------------------------------------
    # Métodos de negocio
    # -------------------------------------------------------------------------

    def _get_date_range(self, report_type, year):
        """
        Retorna (date_start, date_end) según el tipo de reporte y el año.

        :param report_type: str — '13th', '14th_sierra', '14th_costa'
        :param year: int — año de corte
        :return: tuple(date, date)
        """
        if report_type == '13th':
            return date(year - 1, 12, 1), date(year, 11, 30)
        elif report_type == '14th_sierra':
            return date(year - 1, 8, 1), date(year, 7, 31)
        elif report_type == '14th_costa':
            last_day_feb = 29 if calendar.isleap(year) else 28
            return date(year - 1, 3, 1), date(year, 2, last_day_feb)
        return False, False

    def _get_report_name(self, report_type):
        """Retorna el identificador de nombre de archivo para el tipo de reporte."""
        mapping = {
            '13th': 'DECIMO_TERCERO',
            '14th_sierra': 'DECIMO_CUARTO_SIERRA',
            '14th_costa': 'DECIMO_CUARTO_COSTA',
        }
        return mapping.get(report_type, 'REPORTE')

    def action_calculate(self):
        """
        Lanza el cálculo completo del reporte.

        Pasos:
        1. Validar estado draft.
        2. Validar tipo de reporte soportado.
        3. Eliminar líneas previas.
        4. Obtener SBU de referencia y guardarlo.
        5. Llamar _prepare_report_items() y crear ec.payroll.report.line.
        6. Cambiar state a 'calculated'.
        """
        self.ensure_one()

        if self.state != 'draft':
            raise UserError(_('Solo se puede calcular un reporte en estado Borrador.'))

        if self.report_type == 'profits':
            raise UserError(_('El cálculo de Utilidades no está disponible en esta versión.'))

        if not self.fiscalyear_config_id or not self.fiscalyear_config_id.fiscalyear_id:
            raise UserError(_('Debe seleccionar un año fiscal válido.'))

        # Borrar líneas previas
        self.line_ids.unlink()

        # Obtener SBU de referencia (al final del período)
        sbu_ref = 0.0
        if self.date_end and self.company_id:
            try:
                sbu_ref = self.company_id.get_sbu(self.date_end)
            except Exception:
                sbu_ref = 0.0
        self.sbu_used = sbu_ref

        # Preparar y crear líneas
        items = self._prepare_report_items()
        for item in items:
            self.env['ec.payroll.report.line'].create(item)

        self.state = 'calculated'
        return False

    def _prepare_report_items(self):
        """
        Recopila y procesa todos los datos de nómina para el período del reporte.

        Retorna una lista de dicts listos para crear ec.payroll.report.line.
        Incluye tanto empleados procesados (included=True) como excluidos (included=False).
        """
        self.ensure_one()

        if pd is None:
            raise UserError(_('La librería pandas no está instalada en el sistema.'))

        report_type = self.report_type
        date_start = self.date_start
        date_end = self.date_end
        company_id = self.company_id.id

        # Códigos de reglas salariales por tipo de reporte
        target_codes = []
        if report_type == '13th':
            target_codes = ['DTERCERO', 'DTERCEROMEN', 'DTERCEROANUAL']
        elif report_type in ['14th_costa', '14th_sierra']:
            target_codes = ['DCUARTO', 'DCUARTOMEN']

        # ------------------------------------------------------------------ #
        # 1. Ingresos por empleado (todas las regiones, se filtra por región  #
        #    únicamente para 14th después de obtener contratos)               #
        # ------------------------------------------------------------------ #
        income_domain = [
            ('slip_id.date_from', '>=', date_start),
            ('slip_id.date_to', '<=', date_end),
            ('company_id', '=', company_id),
            ('slip_id.state', 'in', ['done', 'paid']),
            ('category_id.code', 'in', ['INGR', 'OINGR']),
        ]
        if report_type == '14th_sierra':
            income_domain.append(('contract_id.region_decimos', '=', 'sierra'))
        elif report_type == '14th_costa':
            income_domain.append(('contract_id.region_decimos', '=', 'costa'))

        income_groups = self.env['hr.payslip.line'].read_group(
            domain=income_domain,
            fields=['employee_id', 'total'],
            groupby=['employee_id'],
        )
        income_map = {g['employee_id'][0]: g['total'] for g in income_groups if g['employee_id']}

        # ------------------------------------------------------------------ #
        # 2. Líneas objetivo por empleado (para pivot)                        #
        # ------------------------------------------------------------------ #
        lines_data = []
        if target_codes:
            lines_domain = [
                ('slip_id.date_from', '>=', date_start),
                ('slip_id.date_to', '<=', date_end),
                ('company_id', '=', company_id),
                ('slip_id.state', 'in', ['done', 'paid']),
                ('code', 'in', target_codes),
            ]
            if report_type == '14th_sierra':
                lines_domain.append(('contract_id.region_decimos', '=', 'sierra'))
            elif report_type == '14th_costa':
                lines_domain.append(('contract_id.region_decimos', '=', 'costa'))
            lines_data = self.env['hr.payslip.line'].search_read(
                lines_domain, ['employee_id', 'code', 'total']
            )

        # ------------------------------------------------------------------ #
        # 3. Contratos activos — primero TODOS, luego separar por región      #
        # ------------------------------------------------------------------ #
        base_contract_domain = [
            ('company_id', '=', company_id),
            ('state', '=', 'open'),
            ('date_start', '<=', date_end),
            '|',
            ('date_end', '=', False),
            ('date_end', '>=', date_end),
        ]
        all_active_contracts = self.env['hr.contract'].search(base_contract_domain)

        # Separar contratos según región si aplica
        if report_type == '14th_sierra':
            valid_contracts = all_active_contracts.filtered(
                lambda c: c.region_decimos == 'sierra'
            )
            wrong_region_contracts = all_active_contracts.filtered(
                lambda c: c.region_decimos != 'sierra'
            )
        elif report_type == '14th_costa':
            valid_contracts = all_active_contracts.filtered(
                lambda c: c.region_decimos == 'costa'
            )
            wrong_region_contracts = all_active_contracts.filtered(
                lambda c: c.region_decimos != 'costa'
            )
        else:
            valid_contracts = all_active_contracts
            wrong_region_contracts = self.env['hr.contract']

        # Empleados de región incorrecta → excluir
        wrong_region_emp_ids = set(wrong_region_contracts.mapped('employee_id').ids)
        valid_emp_ids = set(valid_contracts.mapped('employee_id').ids)

        # ------------------------------------------------------------------ #
        # 4. Clasificar empleados según su situación contractual             #
        # ------------------------------------------------------------------ #
        all_emp_from_income = set(income_map.keys())
        emp_ids_with_valid_contract = valid_emp_ids
        emp_ids_wrong_region = wrong_region_emp_ids - valid_emp_ids

        # Empleados que tuvieron nómina en el período pero NO tienen contrato
        # activo al cierre: fueron liquidados durante el período y sus décimos
        # se pagaron en el finiquito → excluir con razón visible.
        already_classified = valid_emp_ids | wrong_region_emp_ids
        emp_ids_liquidated = all_emp_from_income - already_classified

        # ------------------------------------------------------------------ #
        # 5. Pivot de líneas objetivo                                         #
        # ------------------------------------------------------------------ #
        df_pivot = pd.DataFrame()
        if lines_data:
            df = pd.DataFrame(lines_data)
            df['emp_id_val'] = df['employee_id'].apply(lambda x: x[0] if x else False)
            df_pivot = df.pivot_table(
                index='emp_id_val',
                columns='code',
                values='total',
                aggfunc='sum',
                fill_value=0,
            )
        for code in target_codes:
            if code not in df_pivot.columns:
                df_pivot[code] = 0.0

        # ------------------------------------------------------------------ #
        # 6. Verificar empleados con payslip lines en el período              #
        # ------------------------------------------------------------------ #
        payslip_line_emp_ids = set()
        if not df_pivot.empty:
            payslip_line_emp_ids = set(df_pivot.index.tolist())
        # También incluir los de income_map
        payslip_line_emp_ids.update(all_emp_from_income)

        # ------------------------------------------------------------------ #
        # 7. Construir map contrato por empleado (de contratos válidos)       #
        # ------------------------------------------------------------------ #
        contract_by_emp = {}
        for contract in valid_contracts:
            emp_id = contract.employee_id.id
            if emp_id not in contract_by_emp:
                contract_by_emp[emp_id] = contract

        # ------------------------------------------------------------------ #
        # 8. Procesar empleados con contratos válidos                         #
        # ------------------------------------------------------------------ #
        result_items = []
        employees = self.env['hr.employee'].browse(list(emp_ids_with_valid_contract))

        for emp in employees:
            emp_id = emp.id
            row_data = (
                df_pivot.loc[emp_id]
                if (not df_pivot.empty and emp_id in df_pivot.index)
                else pd.Series(dtype=float)
            )
            contract = contract_by_emp.get(emp_id)
            if not contract:
                contract = self.env['hr.contract'].search(
                    [('employee_id', '=', emp_id), ('state', 'in', ['open', 'close'])], limit=1
                )

            # ---- Nombre ----
            full_name = emp.name or ''
            parts = full_name.strip().split()
            if len(parts) >= 3:
                nombres = ' '.join(parts[-2:])
                apellidos = ' '.join(parts[:-2])
            elif len(parts) == 2:
                apellidos = parts[0]
                nombres = parts[1]
            else:
                nombres, apellidos = full_name, ''

            # ---- Política de pago ----
            # payment_policy se lee del contrato solo para detectar exclusión ('no')
            # mensualiza se deriva de los datos reales del período para reflejar
            # correctamente casos donde el empleado cambió de política a mitad de año.
            payment_policy = ''
            if contract:
                if report_type == '13th':
                    payment_policy = contract.thirteenth_payment or ''
                elif report_type in ['14th_sierra', '14th_costa']:
                    payment_policy = contract.fourteenth_payment or ''

            if payment_policy == 'no':
                result_items.append({
                    'report_id': self.id,
                    'employee_id': emp_id,
                    'cedula': emp.identification_id or '',
                    'nombres': nombres,
                    'apellidos': apellidos,
                    'sexo': 'M' if emp.gender == 'male' else ('F' if emp.gender == 'female' else ''),
                    'cargo': emp.cod_sectorial_iess or '',
                    'ingresos': 0.0,
                    'dias': 0,
                    'horas_sem': '',
                    'jorred': False,
                    'discapc': False,
                    'mensualiza': False,
                    'valor_acumulado': 0.0,
                    'valor_teorico': 0.0,
                    'valor_pago': 0.0,
                    'included': False,
                    'exclusion_reason': _('Política de pago: No aplica'),
                    'warning': '',
                })
                continue

            # ---- Sin nómina en el período ----
            tiene_payslip = emp_id in payslip_line_emp_ids
            if not tiene_payslip:
                result_items.append({
                    'report_id': self.id,
                    'employee_id': emp_id,
                    'cedula': emp.identification_id or '',
                    'nombres': nombres,
                    'apellidos': apellidos,
                    'sexo': 'M' if emp.gender == 'male' else ('F' if emp.gender == 'female' else ''),
                    'cargo': emp.cod_sectorial_iess or '',
                    'ingresos': 0.0,
                    'dias': 0,
                    'horas_sem': '',
                    'jorred': False,
                    'discapc': False,
                    'mensualiza': False,
                    'valor_acumulado': 0.0,
                    'valor_teorico': 0.0,
                    'valor_pago': 0.0,
                    'included': False,
                    'exclusion_reason': _('Sin líneas de nómina en el período'),
                    'warning': '',
                })
                continue

            # ---- Días comerciales ----
            entry_date = contract.date_start if contract else False
            calc_start = max(date_start, entry_date) if entry_date else date_start
            dias = self._get_commercial_days(calc_start, date_end)

            # ---- Horas mensuales contratadas y jornada reducida ----
            # Lógica: type_day='partial' con contracted_hours > 0 → jornada parcial
            #         type_day='complete' o sin datos → jornada completa, factor 1.0
            horas_mensuales = 240.0
            jorred = False
            horas_sem_str = ''
            if (contract
                    and getattr(contract, 'type_day', None) == 'partial'
                    and contract.contracted_hours
                    and contract.contracted_hours > 0):
                horas_mensuales = contract.contracted_hours
                jorred = True
                horas_sem_str = str(round(horas_mensuales, 1))

            # Factor de jornada: fórmula legal SBU × (días/360) × (horas_mensuales/240)
            horas_factor = min(horas_mensuales, 240.0) / 240.0

            # ---- Ingresos ----
            total_ingresos = income_map.get(emp_id, 0.0)

            # ---- Cálculo de valor a pagar ----
            valor_acumulado = 0.0
            valor_teorico = 0.0
            valor_pago = 0.0

            if report_type == '13th':
                valor_pago = round(total_ingresos / 12.0, 2)
                valor_teorico = valor_pago

            elif report_type in ['14th_costa', '14th_sierra']:
                # Cálculo segmentado por año: el SBU puede cambiar en enero de
                # cada año dentro del período (ej. Costa: Mar2024–Feb2025 usa
                # SBU2024 para los días de 2024 y SBU2025 para los de 2025).
                valor_teorico = self._get_fourteenth_expected_amount(calc_start, date_end, horas_factor)
                valor_acumulado = float(row_data.get('DCUARTOMEN', 0.0) or 0.0)
                # valor_pago = décimo cuarto completo (independiente del acumulado)
                valor_pago = valor_teorico

            # ---- Valor cash management = saldo neto a transferir ----
            # Para 14vo: valor_teorico - lo ya mensualizado en nómina
            # Para 13vo: igual al valor_pago (no hay acumulado mensual a descontar)
            valor_neto_transferir = max(0.0, round(valor_pago - valor_acumulado, 2))

            # ---- Mensualiza: refleja realidad histórica del período ----
            # Se deriva de los datos reales de nómina, no del estado actual del
            # contrato, para manejar correctamente cambios de política a mitad de año.
            if report_type == '13th':
                mensualiza = float(row_data.get('DTERCEROMEN', 0.0) or 0.0) > 0
            elif report_type in ['14th_costa', '14th_sierra']:
                mensualiza = valor_acumulado > 0
            else:
                mensualiza = False

            # ---- Advertencias (empleado incluido con datos incompletos) ----
            warnings = []
            if emp.payment_method == 'CUE' and not emp.account_number:
                warnings.append(_('Sin cuenta bancaria registrada'))
            if valor_neto_transferir == 0.0 and valor_acumulado > 0.0:
                warnings.append(_('Décimo cubierto por mensualización'))
            elif valor_pago == 0.0:
                warnings.append(_('Valor a pagar es $0.00'))
            if not emp.cod_sectorial_iess:
                warnings.append(_('Sin código sectorial IESS'))

            result_items.append({
                'report_id': self.id,
                'employee_id': emp_id,
                'cedula': emp.identification_id or '',
                'nombres': nombres,
                'apellidos': apellidos,
                'sexo': 'M' if emp.gender == 'male' else ('F' if emp.gender == 'female' else ''),
                'cargo': emp.cod_sectorial_iess or '',
                'ingresos': total_ingresos,
                'dias': dias,
                'horas_sem': horas_sem_str,
                'jorred': jorred,
                'discapc': emp.is_discapacitado or False,
                'mensualiza': mensualiza,
                'contract_date_start': contract.date_start if contract else False,
                'contract_date_end': contract.date_end if contract else False,
                'valor_acumulado': valor_acumulado,
                'valor_teorico': valor_teorico,
                'valor_pago': valor_pago,
                'valor_cash_management': valor_neto_transferir if (emp.payment_method == 'CUE' and emp.account_number) else 0.0,
                'included': True,
                'exclusion_reason': '',
                'warning': ' | '.join(warnings),
            })

        # ------------------------------------------------------------------ #
        # 9. Empleados de región incorrecta → excluidos                       #
        # ------------------------------------------------------------------ #
        if wrong_region_emp_ids:
            wrong_region_employees = self.env['hr.employee'].browse(list(wrong_region_emp_ids))
            for emp in wrong_region_employees:
                full_name = emp.name or ''
                parts = full_name.strip().split()
                if len(parts) >= 3:
                    nombres = ' '.join(parts[-2:])
                    apellidos = ' '.join(parts[:-2])
                elif len(parts) == 2:
                    apellidos = parts[0]
                    nombres = parts[1]
                else:
                    nombres, apellidos = full_name, ''

                result_items.append({
                    'report_id': self.id,
                    'employee_id': emp.id,
                    'cedula': emp.identification_id or '',
                    'nombres': nombres,
                    'apellidos': apellidos,
                    'sexo': 'M' if emp.gender == 'male' else ('F' if emp.gender == 'female' else ''),
                    'cargo': emp.cod_sectorial_iess or '',
                    'ingresos': 0.0,
                    'dias': 0,
                    'horas_sem': '',
                    'jorred': False,
                    'discapc': False,
                    'mensualiza': False,
                    'valor_acumulado': 0.0,
                    'valor_teorico': 0.0,
                    'valor_pago': 0.0,
                    'included': False,
                    'exclusion_reason': _('Región del contrato no corresponde al reporte'),
                    'warning': '',
                })

        # ------------------------------------------------------------------ #
        # 10. Empleados liquidados durante el período → excluidos             #
        #     Tuvieron nómina en el período pero no tienen contrato activo    #
        #     al cierre: sus décimos fueron pagados en el finiquito.          #
        # ------------------------------------------------------------------ #
        if emp_ids_liquidated:
            liquidated_employees = self.env['hr.employee'].browse(list(emp_ids_liquidated))
            # Pre-cargar el último contrato de cada empleado para obtener fecha de salida
            liquidated_contracts = self.env['hr.contract'].search([
                ('employee_id', 'in', list(emp_ids_liquidated)),
                ('company_id', '=', company_id),
                ('date_start', '<=', date_end),
            ], order='date_end desc')
            last_contract_by_emp = {}
            for contract in liquidated_contracts:
                emp_id = contract.employee_id.id
                if emp_id not in last_contract_by_emp:
                    last_contract_by_emp[emp_id] = contract

            for emp in liquidated_employees:
                full_name = emp.name or ''
                parts = full_name.strip().split()
                if len(parts) >= 3:
                    nombres = ' '.join(parts[-2:])
                    apellidos = ' '.join(parts[:-2])
                elif len(parts) == 2:
                    apellidos = parts[0]
                    nombres = parts[1]
                else:
                    nombres, apellidos = full_name, ''

                last_contract = last_contract_by_emp.get(emp.id)
                fecha_salida = (
                    last_contract.date_end.strftime('%d/%m/%Y')
                    if last_contract and last_contract.date_end
                    else ''
                )
                reason = _('Liquidado durante el período – décimos pagados en finiquito')
                if fecha_salida:
                    reason = _('Liquidado el %s – décimos pagados en finiquito') % fecha_salida

                result_items.append({
                    'report_id': self.id,
                    'employee_id': emp.id,
                    'cedula': emp.identification_id or '',
                    'nombres': nombres,
                    'apellidos': apellidos,
                    'sexo': 'M' if emp.gender == 'male' else ('F' if emp.gender == 'female' else ''),
                    'cargo': emp.cod_sectorial_iess or '',
                    'ingresos': income_map.get(emp.id, 0.0),
                    'dias': 0,
                    'horas_sem': '',
                    'jorred': False,
                    'discapc': False,
                    'mensualiza': False,
                    'contract_date_start': last_contract.date_start if last_contract else False,
                    'contract_date_end': last_contract.date_end if last_contract else False,
                    'valor_acumulado': 0.0,
                    'valor_teorico': 0.0,
                    'valor_pago': 0.0,
                    'included': False,
                    'exclusion_reason': reason,
                    'warning': '',
                })

        return result_items

    def _get_commercial_days(self, start, end):
        """
        Calcula días comerciales (30 días por mes) entre dos fechas.

        Utiliza la convención bancaria: el día 31 y el último día del mes se cuentan como 30.
        Máximo 360 días.
        """
        if not start or not end or start > end:
            return 0

        def adjust_day(d):
            last_day = calendar.monthrange(d.year, d.month)[1]
            return 30 if d.day == last_day else (30 if d.day == 31 else d.day)

        day_from = adjust_day(start)
        day_to = adjust_day(end)
        calculated_days = (
            (end.year - start.year) * 360
            + (end.month - start.month) * 30
            + (day_to - day_from)
            + 1
        )
        return max(0, min(360, calculated_days))

    def _get_fourteenth_expected_amount(self, start, end, horas_factor=1.0):
        """
        Calcula el valor teórico del décimo cuarto prorrateado con SBU por año
        dentro del rango [start, end], usando días comerciales.

        Itera año por año para aplicar el SBU correcto a cada segmento.

        :param horas_factor: proporción de jornada (ej. 0.5 para 20h semanales).
                             Para jornada completa usar 1.0 (valor por defecto).
        """
        if not start or not end or start > end:
            return 0.0

        total = 0.0
        current_year = start.year
        end_year = end.year

        while current_year <= end_year:
            year_start = date(current_year, 1, 1)
            year_end = date(current_year, 12, 31)
            segment_start = max(start, year_start)
            segment_end = min(end, year_end)
            if segment_start <= segment_end:
                segment_days = self._get_commercial_days(segment_start, segment_end)
                sbu = self.company_id.get_sbu(segment_end)
                total += sbu * (segment_days / 360.0) * horas_factor
            current_year += 1

        return round(total, 2)

    def action_export_csv(self):
        """
        Exporta las líneas incluidas en formato CSV compatible con el Ministerio de Trabajo.

        Genera el archivo y lo retorna como descarga directa.
        Cambia el estado a 'exported' si aún no lo estaba.
        """
        self.ensure_one()

        if self.state == 'draft':
            raise UserError(_('Debe calcular el reporte antes de exportar.'))

        included_lines = self.line_ids.filtered(lambda l: l.included)
        if not included_lines:
            raise UserError(_('No hay empleados incluidos en el reporte para exportar.'))

        # Validaciones de datos obligatorios
        errors = []
        for line in included_lines:
            missing = []
            if not line.cedula:
                missing.append('Cédula')
            if not line.nombres and not line.apellidos:
                missing.append('Nombre')
            if not line.sexo:
                missing.append('Género')
            if not line.cargo:
                missing.append('Código Sectorial')
            if missing:
                emp_name = line.employee_id.name or line.nombres or '(sin nombre)'
                errors.append(f'- {emp_name}: {", ".join(missing)}')
        if errors:
            raise UserError(_('Faltan datos obligatorios:\n\n') + '\n'.join(errors))

        output = io.StringIO()
        writer = csv.writer(output, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)

        report_type = self.report_type
        report_name = self._get_report_name(report_type)

        if report_type == '13th':
            headers = [
                'cedula', 'nombres', 'apellidos', 'sexo', 'cargo',
                'ingresos', 'dias', 'forpag', 'jorred', 'horas_sem',
                'discapc', 'dec_13', 'mensualiza',
            ]
        else:  # 14th_sierra o 14th_costa
            headers = [
                'Cedula', 'Nombres', 'Apellidos', 'Genero', 'Ocupacion',
                'Dias laborados', 'Tipo de Pago', 'JORNADA PARCIAL PERMANENTE',
                'HORAS SEMANAL', 'discapacidad', 'Fecha de Jubilacion',
                'valor Retencion', 'MENSUALIZA',
            ]

        writer.writerow(headers)

        for line in included_lines:
            jorred_str = 'X' if line.jorred else ''
            discapc_str = 'X' if line.discapc else ''
            mensualiza_str = 'X' if line.mensualiza else ''

            if report_type == '13th':
                row = [
                    line.cedula, line.nombres, line.apellidos, line.sexo, line.cargo,
                    f'{line.ingresos:.2f}', line.dias, 'A', jorred_str, line.horas_sem,
                    discapc_str, f'{line.valor_pago:.2f}', mensualiza_str,
                ]
            else:
                row = [
                    line.cedula, line.nombres, line.apellidos, line.sexo, line.cargo,
                    line.dias, 'A', jorred_str, line.horas_sem,
                    discapc_str, '0', '0', mensualiza_str,
                ]
            writer.writerow(row)

        content = base64.b64encode(output.getvalue().encode('utf-8')).decode('utf-8')
        output.close()

        if self.state != 'exported':
            self.state = 'exported'

        filename = f'{report_name}.csv'
        return self._return_download_action(filename, content)

    def action_export_cash_management(self):
        """
        Genera el archivo TXT de Cash Management para Banco Pichincha o Banco de Guayaquil.

        Valida que estén configurados la cuenta bancaria empresa y la fecha de pago.
        """
        self.ensure_one()

        if self.state == 'draft':
            raise UserError(_('Debe calcular el reporte antes de exportar.'))

        if not self.company_partner_bank_id:
            raise UserError(_('Debe seleccionar una Cuenta Bancaria de la Empresa.'))

        if not self.payment_date:
            raise UserError(_('Debe ingresar la Fecha de Pago.'))

        included_lines = self.line_ids.filtered(lambda l: l.included)
        if not included_lines:
            raise UserError(_('No hay empleados incluidos en el reporte para generar el pago.'))

        bank_obj = self.company_partner_bank_id
        bic = bank_obj.bank_id.bic or ''

        if bic == '00000010':
            result = self._generate_pichincha_file(included_lines)
        elif bic == '00000017':
            result = self._generate_guayaquil_file(included_lines)
        else:
            bank_name = bank_obj.bank_id.name or 'S/N'
            raise UserError(
                _('Banco no soportado para Cash Management: %s') % bank_name
            )

        if self.state != 'exported':
            self.state = 'exported'

        return result

    def _generate_pichincha_file(self, lines):
        """Genera el archivo TXT para transferencias Banco Pichincha."""
        acc_type = {'checking': 'CTE', 'savings': 'AHO'}
        file_lines = []

        for line in lines:
            emp = line.employee_id
            if emp.payment_method != 'CUE':
                continue
            if line.valor_pago <= 0:
                continue
            if line.mensualiza:
                continue

            bank_code = self._get_employee_bank_code(emp, default='45')
            cedula = line.cedula or ''
            line_parts = [
                'PA',
                '',  # secuencia, se llena al ordenar
                'USD',
                '{:.0f}'.format(line.valor_pago * 100),
                'CTA',
                acc_type.get(emp.type_account, 'AHO'),
                emp.account_number or '',
                ('PAGO ' + self.report_type.upper())[:20],
                'C' if len(cedula) == 10 else 'R',
                '{:0>13}'.format(cedula),
                self._clean_not_unicode(emp.name or ''),
                bank_code or '45',
            ]
            file_lines.append((emp.name.lower() if emp.name else '', line_parts))

        file_lines.sort(key=lambda x: x[0])
        file_str = ''
        for i, (_, lp) in enumerate(file_lines, 1):
            lp[1] = str(i)
            file_str += '\t'.join(lp) + '\n'

        report_name = self._get_report_name(self.report_type)
        company_name = (self.company_id.name or 'EMPRESA').replace(' ', '_')
        filename = f'{company_name}_PICHINCHA_{report_name}_{date.today()}.txt'

        return self._return_download_action(
            filename, base64.b64encode(file_str.encode('utf-8')).decode('utf-8')
        )

    def _generate_guayaquil_file(self, lines):
        """Genera el archivo TXT para transferencias Banco de Guayaquil."""
        acc_type_mapping = {'checking': 'CTE', 'savings': 'AHO'}
        company_acc = (self.company_partner_bank_id.acc_number or '').replace(' ', '').replace('-', '')
        company_acc_fmt = f'{company_acc:0>10}'

        file_lines = []
        seq = 0

        for line in lines:
            emp = line.employee_id
            if emp.payment_method != 'CUE':
                continue
            if line.valor_pago <= 0:
                continue
            if line.mensualiza:
                continue

            seq += 1
            bank_code = self._get_employee_bank_code(emp, default='17')
            bank_code_digits = ''.join(ch for ch in str(bank_code) if ch.isdigit())[-2:] or '17'

            cedula = line.cedula or ''
            vat_clean = cedula.replace('-', '').replace(' ', '')
            type_vat = 'C' if len(vat_clean) == 10 else 'R'

            email = emp.email_private or emp.work_email or 'sin-email@empresa.com'
            emp_acc = (emp.account_number or '').replace(' ', '').replace('-', '')
            emp_acc_fmt = f'{emp_acc:0>10}' if bank_code_digits == '17' else emp_acc

            line_parts = [
                'PA',
                company_acc_fmt,
                f'{seq:07d}',
                ('PAGO ' + self.report_type.upper())[:20],
                emp_acc,
                'USD',
                f'{int(line.valor_pago * 100):013d}',
                'CTA',
                bank_code_digits.zfill(2),
                acc_type_mapping.get(emp.type_account, 'AHO'),
                emp_acc_fmt,
                type_vat,
                vat_clean,
                self._clean_not_unicode((emp.name or '').upper())[:40],
                '', '', '', '',
                'PAGO ' + self.report_type.upper(),
                email,
            ]
            file_lines.append('\t'.join(line_parts))

        report_name = self._get_report_name(self.report_type)
        company_name = (self.company_id.name or 'EMPRESA').replace(' ', '_')
        filename = f'{company_name}_GUAYAQUIL_{report_name}_{date.today()}.txt'
        file_content = '\n'.join(file_lines)
        return self._return_download_action(
            filename, base64.b64encode(file_content.encode('utf-8')).decode('utf-8')
        )

    def _get_employee_bank_code(self, employee, default='10'):
        """
        Obtiene el código de banco del empleado para cash management.

        Prioriza el BIC del banco del empleado. Si no existe, intenta el modelo
        res.bank.code. Finalmente cae al valor por defecto.
        """
        bank = employee.bank_id
        if bank and bank.bic:
            bank_bic_digits = ''.join(ch for ch in str(bank.bic) if ch.isdigit())
            if bank_bic_digits:
                return bank_bic_digits[-2:].zfill(2)

        bank_code_model = self.env.get('res.bank.code')
        if (
            bank_code_model
            and bank
            and self.company_partner_bank_id
            and self.company_partner_bank_id.bank_id
        ):
            try:
                mapped_code = bank_code_model.get_bank_code(
                    self.company_partner_bank_id.bank_id, bank
                )
            except Exception:
                mapped_code = False
            if mapped_code:
                mapped_digits = ''.join(ch for ch in str(mapped_code) if ch.isdigit())
                if mapped_digits:
                    return mapped_digits[-2:].zfill(2)

        default_digits = ''.join(ch for ch in str(default) if ch.isdigit())
        return default_digits[-2:].zfill(2) if default_digits else '00'

    def _clean_not_unicode(self, text):
        """Reemplaza caracteres especiales del español por sus equivalentes ASCII."""
        if not text:
            return ''
        chars = {
            'Ñ': 'N', 'ñ': 'n', 'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
            'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U', 'ü': 'u', 'Ü': 'U',
        }
        for k, v in chars.items():
            text = text.replace(k, v)
        return text

    def action_reset_to_draft(self):
        """Regresa el reporte a Borrador y elimina las líneas para permitir recalcular."""
        self.ensure_one()
        self.line_ids.unlink()
        self.state = 'draft'

    def _return_download_action(self, filename, content):
        """Crea un adjunto y retorna la acción de descarga directa."""
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': content,
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/octet-stream',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }


class EcPayrollReportLine(models.Model):
    """Línea de un reporte de nómina — un registro por empleado procesado."""

    _name = 'ec.payroll.report.line'
    _description = 'Línea de Reporte de Nómina Ministerio'
    _order = 'included desc, apellidos, nombres'

    report_id = fields.Many2one(
        'ec.payroll.report',
        string='Reporte',
        required=True,
        ondelete='cascade',
        index=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        index=True,
    )

    # Datos personales / laborales (desnormalizados para snapshot histórico)
    cedula = fields.Char(string='Cédula')
    nombres = fields.Char(string='Nombres')
    apellidos = fields.Char(string='Apellidos')
    sexo = fields.Char(string='Género', size=1)
    cargo = fields.Char(string='Código Sectorial IESS')

    # Datos de nómina
    ingresos = fields.Float(string='Ingresos', digits=(10, 2))
    dias = fields.Integer(string='Días Laborados')
    horas_sem = fields.Char(string='Horas Semanales')
    jorred = fields.Boolean(string='Jornada Reducida')
    discapc = fields.Boolean(string='Discapacidad')
    mensualiza = fields.Boolean(string='Mensualizado')

    # Valores monetarios
    valor_acumulado = fields.Float(string='Valor Acumulado en Nómina', digits=(10, 2))
    valor_teorico = fields.Float(string='Valor Teórico', digits=(10, 2))
    valor_pago = fields.Float(string='Valor a Pagar', digits=(10, 2))
    valor_cash_management = fields.Float(
        string='Valor Cash Management', digits=(10, 2),
        help='Monto a transferir por banco. Solo aplica para empleados con pago por cuenta bancaria.',
    )

    # Contrato vigente al momento del cálculo
    contract_date_start = fields.Date(string='Contrato desde')
    contract_date_end = fields.Date(string='Contrato hasta')

    # Control de inclusión
    included = fields.Boolean(string='Incluido', default=True, index=True)
    exclusion_reason = fields.Char(string='Razón de Exclusión')
    warning = fields.Char(string='Advertencia')
