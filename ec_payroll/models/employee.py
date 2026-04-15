# -*- coding: utf-8 -*-
from odoo import models, fields, registry, api
from odoo.tools.translate import _
from odoo.exceptions import RedirectWarning, UserError, ValidationError
from odoo.osv import expression
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class res_partner_bank(models.Model):

    _inherit = 'res.partner.bank'

    def _get_partner(self):

        if self.env.context.get('hr',False):
            return self.env['res.partner'].browse(self.env.context.get('hr',False))
        return None

    partner_id = fields.Many2one('res.partner', 'Account Holder', ondelete='cascade', index=True, domain=['|', ('is_company', '=', True), ('parent_id', '=', False)], required=True,default=_get_partner)

class SalaryHistory(models.Model):
    _inherit = 'salary.history'
    _description = 'Historial Salarial'

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency of the Payment Transaction",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    sueldo = fields.Monetary(string="Sueldo", currency_field="currency_id")
    cargo_id=fields.Many2one("hr.job","Cargo")
    contrato_id = fields.Many2one("hr.contract", "Contrato")


class ContractHistory(models.Model):
    _inherit = 'contract.history'
    _description='Historial de Contratos'



    select_Contrato=[
        ('EVENTUAL', 'EVENTUAL'),
        ('INDEFINIDO', 'INDEFINIDO'),
    ]

    select_adendum=[
        ('SUELDO', 'POR SUELDO'),
        ('HORARIO', 'POR HORARIO'),
    ]

    tipo_documento=fields.Selection([('contrato', 'Contrato'),
                                     ('adendum', 'Adendum'),
                                     ],string="Tipo de Documento")
    observacion = fields.Selection(selection = select_adendum+select_Contrato, string='Observación', groups="hr.group_hr_user",  tracking=True)
    contrato_id=fields.Many2one('hr.contract','Nuevo Contrato')

    @api.onchange('observacion')
    def validar_contrato(self):
        for l in self:
            l.employee_id=self._context['active_id']
            contrato_id = self.env['hr.contract'].search(
                [('employee_id', '=', self._context['active_id']), ('state', '=', 'open')], limit=1)
            if self.tipo_documento=='adendum':
                if l.observacion in ['SUELDO','HORARIO']:
                    if contrato_id:
                        new_contrato = contrato_id.copy()
                        contrato_id.state='close'
                        self.contrato_id=new_contrato.id
                    else:
                        raise ValidationError("No cuenta con un contrato activo para realizar el proceso de Adenda.")
                else:
                    raise UserError("Para el tipo de Documento Adendum como observación puede seleccionar POR SUELDO u HORARIO")
            elif self.tipo_documento=='contrato':
                if l.observacion in ['EVENTUAL','INDEFINIDO']:
                    if contrato_id:
                        raise UserError("Mantiene un contrato activo para este colaborador. Por favor realice los procesos respectivos y puede retomar a ingresar este registro.")
                else:
                    raise UserError("Para el tipo de Documento Contrato como observación puede seleccionar EVENTUAL o INDEFINIDO")


class HrContract(models.Model):
    _name = "hr.contract"
    _inherit = ["hr.contract", "analytic.mixin"]

    analytic_distribution = fields.Json()

    @api.onchange('wage')
    def onchange_wage(self):
        vals = {
            'employee_id': self.employee_id.id,
            'employee_name': self.employee_id,
            'updated_date': datetime.today(),
            'current_value': self.wage,
            'sueldo': self.wage,
            'cargo_id': self.job_id.id,
            'contrato_id': self.id,

        }
        self.env['salary.history'].sudo().create(vals)

    @api.onchange('job_id')
    def onchange_job_id(self):
        employee_id = self.env['hr.employee'].search([('id', '=', self.employee_id.id)])
        vals = {
            'employee_id': self._origin.id,
            'employee_name': employee_id.name,
            'updated_date': datetime.today(),
            'changed_field': 'Posición',
            'current_value': self.job_id.name,
            'departamento_id': self.department_id.id,
            'cargo_id': self.job_id.id,
            'area_id': self.department_id.parent_id.id,
        }
        self.env['department.history'].sudo().create(vals)

class DepartmentHistory(models.Model):
    _inherit = 'department.history'
    _description='Historial Laboral'

    departamento_id=fields.Many2one("hr.department","Departamento")
    area_id=fields.Many2one("hr.department","Área")
    cargo_id=fields.Many2one("hr.job","Cargo")


class HrHorarioDocente(models.Model):
    _name = 'cen.horario.docente'
    _rec_name="display_name"
    _description="Horarios Docentes"

    name=fields.Char("Nombre",required=True)
    display_name=fields.Char(compute="obtener_name")
    numero_horas=fields.Float("Número de horas a la semana.")

    @api.depends("name","numero_horas")
    def obtener_name(self):
        nombre=""
        for l in self:
            if l.name:
                nombre+=l.name
            if l.numero_horas:
                nombre+=str(l.numero_horas)+" Horas"
        self.display_name=nombre

class HrEmployee(models.Model):

    _inherit = 'hr.employee'

    street = fields.Char(string="Dirección")
    identification_id = fields.Char(string=u'Cédula / Pasaporte', required=False)
    foreign = fields.Boolean(string=u'Extranjero?')
    asumir_antiguedad = fields.Boolean(string=u'Asumir Antiguedad', readonly=False, states={}, help=u"")
    wife_id = fields.Many2one('hr.family.burden', string=u'Esposo(a) / Conviviente',
                              required=False, readonly=False, states={}, help=u"", ondelete="restrict")
    family_burden_ids = fields.One2many('hr.family.burden', 'employee_id', u'Hijos / Parientes', domain=[('relationship', '!=', 'wife_husband')])
    pay_with_check = fields.Boolean(string=u'Pagar con Cheque', readonly=False, states={}, help=u"")
    payment_method = fields.Selection([('CUE', 'Deposito a cuenta'),
                                       # ('EFE', 'Tarjeta de pago'),
                                       ('EFE', 'Efectivo'),
                                       # ('COB', 'Credito a cuenta'),
                                       # ('TRA','Transferencia'),
                                       ('CHE','Cheque'),
                                       ], string='Forma de pago', track_visibility='onchange', default='CUE')
    bank_id = fields.Many2one('res.bank', u'Banco',  track_visibility='onchange')
    account_number = fields.Char(u'Número de cuenta',  track_visibility='onchange')
    type_account = fields.Selection([('savings', 'Ahorros'),
                                     ('current', 'Corriente'),
                                     ('virtual', 'Virtual'),
                                     ], string='Tipo de Cuenta Bancaria',  track_visibility='onchange', readonly=False, required=False,
                                    default='savings')
    third_payment = fields.Boolean(string="Pago a terceros?", default=False)
    supplier = fields.Boolean('Proveedor')
    customer=fields.Boolean('Cliente')
    is_discapacitado = fields.Boolean(u'Presenta Discapacidad?', required=False)
    discapacidad = fields.Float(u'Porcentaje de Discapacidad')
    state_id = fields.Many2one('res.country.state', 'Ciudad',
        domain="[('country_id', '=', country_id)]", required=False)
    nombre_discapacidad = fields.Char(u'Discapacidad')
    type_disability = fields.Selection([('visual', 'Visual'),
                                        ('auditiva', 'Auditiva'),
                                        ('fisica', 'Física'),
                                        ('intelectual', 'Intelectual'),
                                        ('sutituto', 'Sustituto'),
                                        ('psicosocial', 'Psicosocial'),
                                        ('multiple', 'Múltiple')],
                                       string='Tipo de Discapacidad', track_visibility='onchange')
    tipo_sangre = fields.Char(u'Tipo Sangre')
    email_private = fields.Char('Email Personal')
    gender = fields.Selection(selection = '_get_new_gender', string='Sexo', groups="hr.group_hr_user", tracking=True)
    marital = fields.Selection(selection = '_get_new_marital', string='Estado Civil', groups="hr.group_hr_user", default='single', tracking=True)
    cod_sectorial_iess = fields.Char('Código Sectorial IESS')


    contract_history_ids = fields.One2many(
        "contract.history", "employee_id",
        string="",
        readonly=True,
        copy=False,
    )
    horario_docente=fields.Many2one("cen.horario.docente")
    calificacion_docente=fields.Float("Calificación Docente")

    def contract_history(self):
        res_user = self.env['res.users'].search([('id', '=', self._uid)])
        if res_user.has_group('hr.group_hr_manager'):
            return {
                'name': _("Historial de Contratos"),
                'view_mode': 'tree',
                'res_model': 'contract.history',
                'type': 'ir.actions.act_window',
                'target': 'new',
                'domain': [('employee_id', '=', self.id)]
            }
        if self.id == self.env.user.employee_id.id:
            return {
                'name': _("Historial de Contratos"),
                'view_mode': 'tree',
                'res_model': 'contract.history',
                'type': 'ir.actions.act_window',
                'target': 'new'
            }
        else:
            raise UserError('You cannot access this field!!!!')

    def salary_history(self):
        res_user = self.env['res.users'].search([('id', '=', self._uid)])
        if res_user.has_group('hr.group_hr_manager'):
            return {
                'name': _("Historial Salarial"),
                'view_mode': 'tree',
                'res_model': 'salary.history',
                'type': 'ir.actions.act_window',
                'target': 'new',
                'domain': [('employee_id', '=', self.id)]
            }
        elif self.id == self.env.user.employee_id.id:
            return {
                'name': _("Historial Salarial"),
                'view_mode': 'tree',
                'res_model': 'salary.history',
                'type': 'ir.actions.act_window',
                'target': 'new'
            }
        else:
            raise UserError('You cannot access this field!!!!')

    def department_details(self):
        res_user = self.env['res.users'].search([('id', '=', self._uid)])
        view_id_tree = self.env.ref('history_employee.employee_department_history', False)
        if res_user.has_group('hr.group_hr_manager'):
            return {
                'name': _("Historial Laboral"),
                'view_mode': 'tree',
                'res_model': 'department.history',
                'type': 'ir.actions.act_window',
                'target': 'new',
                'domain': [('employee_id', '=', self.id)],
            }
        elif self.id == self.env.user.employee_id.id:
            return {
                'name': _("Historial Laboral"),
                'view_mode': 'tree',
                'res_model': 'department.history',
                'type': 'ir.actions.act_window',
                'target': 'new',
            }
        else:
            raise UserError('You cannot access this field!!!!')

    @api.onchange('department_id')
    def _onchange_department(self):
        employee_id = self.env['hr.employee'].search([('id', '=', self._origin.id)])
        contrato_id=self.env['hr.contract'].search([('employee_id', '=', self._origin.id),('state', '=', 'open')],limit=1)
        vals = {
            'employee_id': self._origin.id,
            'employee_name': employee_id.name,
            'updated_date': datetime.now(),
            'changed_field': 'Departamento',
            'current_value': self.department_id.name,
            'departamento_id':self.department_id.id,
            'cargo_id':contrato_id.job_id.id,
            'area_id': self.department_id.parent_id.id,
        }
        self.env['department.history'].sudo().create(vals)



    @api.model
    def _get_new_marital(self):
        selection = [
            ('single', 'Soltero(a)'),
            ('married', 'Casado(a)'),
            ('cohabitant', 'Union de Hecho'),
            ('habitant', 'Union Libre'),
            ('widower', 'Viudo(a)'),
            ('divorced', 'Divorciado')
        ]
        return selection

    @api.model
    def _get_new_gender(self):
        selection = [
            ('male', 'Hombre'),
            ('female', 'Mujer'),
        ]
        return selection
    @api.constrains('address_home_id')
    def _check_address_home_id(self):
        if self.address_home_id:
            other_employees = self.search([
                ('address_home_id', '=', self.address_home_id.id),
                ('id', '!=', self.id),
            ])
            # if other_employees:
            #     raise UserError(_(u'No puede asignar a la empresa %s a mas de un empleado, ya se encuentra asignado a %s') % (
            #         self.address_home_id.display_name,
            #         other_employees[0].display_name,
            #         ))


    @api.constrains('identification_id')
    def _check_document_number(self):
        partner_model = self.env['res.partner']
        if self.identification_id and self.identification_id !='000':
            if not self.foreign and not partner_model.verifica_cedula(self.identification_id):
                raise UserError(_(u'La identificación %s del empleado no es correcta, verifique por favor') % self.identification_id,)

    @api.model
    def create(self, vals):
        partner_model = self.env['res.partner']

        if not vals.get('address_home_id', False):
            finded_partner = partner_model.search([('vat', '=', vals.get('identification_id'))])
            if finded_partner:
                address_home_id = finded_partner.id
            else:
                partner_new = partner_model.create({
                    'vat': vals.get('identification_id'),
                    'name': vals.get('name'),
                    'foreign': vals.get('foreign'),
                    'is_company': False,
                })
                address_home_id = partner_new.id
            vals.update({
                'address_home_id': address_home_id
            })
        rec = super(HrEmployee, self).create(vals)
        if 'address_home_id' in vals:
            if vals.get('address_home_id'):
                rec.sudo().write({
                    'supplier': True,
                    'customer': True,
                })
        return rec


    def write(self, vals):
        burden_model = self.env['hr.family.burden']
        if 'name' in vals.keys():
            for employee in self:
                if employee.address_home_id:
                    employee.address_home_id.write({
                        'name': vals.get('name'),
                    })
        if 'wife_id' in vals.keys() and vals.get('wife_id'):
            wife = burden_model.browse(vals.get('wife_id'))
            for employee in self:
                wife.write({
                    'employee_id': employee.id
                })
        if 'address_home_id' in vals:
            if vals.get('address_home_id'):
                for rec in self:
                    rec.sudo().write({
                        'supplier': True,
                        'customer': True,
                    })
        return super(HrEmployee, self).write(vals)

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('identification_id', '=ilike', name + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        employees = self.search(domain + args, limit=limit)
        return employees.name_get()

    @api.onchange('user_id')
    def _onchange_user_id(self):
        if self.user_id:
            self.address_home_id = self.user_id.partner_id.id
        else:
            self.address_home_id = None

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        payslip_model = self.env['hr.payslip']
        employees = self.env['hr.employee'].browse()
        if self.env.context.get('date_start', False) and self.env.context.get('date_end', False):
            for employee in self.with_context(date_start=False, date_end=False).search([]):
                contracts = payslip_model.get_contract(employee, self.env.context.get('date_start', False), self.env.context.get('date_end', False))
                if not contracts:
                    employees |= employee
            if employees:
                args.append(('id', 'not in', employees.ids))
        return super(HrEmployee, self).search(args, offset, limit, order, count)


    def get_no_liquidated_contracts(self):
        self.ensure_one()
        contract_model = self.env['hr.contract']
        contracts = contract_model.browse()
        for contract in self.contract_ids:
            if not contract.hr_liquidation_ids:
                contracts |= contract
        return contracts
