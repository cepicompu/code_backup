# -*- coding: utf-8 -*-
from odoo import models, fields, registry, api
from odoo.tools.translate import _
from odoo.exceptions import RedirectWarning, UserError, ValidationError
import logging
import base64
from odoo.tools.float_utils import float_compare, float_is_zero
from odoo.tools.safe_eval import safe_eval
from datetime import datetime
from collections import defaultdict
from odoo.tools import float_compare, float_is_zero, plaintext2html
from markupsafe import Markup

_logger = logging.getLogger(__name__)


class hr_payslip(models.Model):
    _inherit = 'hr.payslip'

    def _prepare_adjust_line(self, line_ids, adjust_type, debit_sum, credit_sum, date):
        acc_id = self.company_id.account_salary_id.id
        if not acc_id:
            raise UserError(
                _('The Expense Journal "%s" has not properly configured the default Account!') % (self.journal_id.name))
        existing_adjustment_line = (
            line_id for line_id in line_ids if line_id['name'] == _('Adjustment Entry')
        )
        adjust_credit = next(existing_adjustment_line, False)

        if not adjust_credit:
            adjust_credit = {
                'name': _('Adjustment Entry'),
                'partner_id': False,
                'account_id': acc_id,
                'journal_id': self.journal_id.id,
                'date': date,
                'debit': 0.0 if adjust_type == 'credit' else credit_sum - debit_sum,
                'credit': debit_sum - credit_sum if adjust_type == 'credit' else 0.0,
            }
            line_ids.append(adjust_credit)
        else:
            adjust_credit['credit'] = debit_sum - credit_sum

    def action_payslip_done(self):
        for payslip in self:
            payslip.write({'state': 'done'})

    def _are_payslips_ready(self):
        return all(slip.state in ['done'] for slip in self.mapped('slip_ids'))

    def action_payslip_done_id(self):
        if any(slip.state == 'cancel' for slip in self):
            raise ValidationError(_("You can't validate a cancelled payslip."))
        self.write({'state': 'done'})
        self.mapped('payslip_run_id').action_close()
        if self.env.context.get('payslip_generate_pdf'):
            for payslip in self:
                if not payslip.struct_id or not payslip.struct_id.report_id:
                    report = self.env.ref('hr_payroll.action_report_payslip', False)
                else:
                    report = payslip.struct_id.report_id
                pdf_content, content_type = self.env['ir.actions.report'].sudo()._render_qweb_pdf(report, payslip.id)
                if payslip.struct_id.report_id.print_report_name:
                    pdf_name = safe_eval(payslip.struct_id.report_id.print_report_name, {'object': payslip})
                else:
                    pdf_name = _("Payslip")
                self.env['ir.attachment'].create({
                    'name': pdf_name,
                    'type': 'binary',
                    'datas': base64.encodestring(pdf_content),
                    'res_model': payslip._name,
                    'res_id': payslip.id
                })

    def _action_payslip_done(self):

        empleado = [x.employee_id.name for x in self.filtered(lambda l: l.payslip_net <= 0)]
        if any(empleado):
            raise ValidationError(_('Rol de pagos de %s con valor 0 o menor revise') % (" - ".join(empleado)))

        move = {}
        res = self.action_payslip_done_id()
        precision = self.env['decimal.precision'].precision_get('Payroll')

        # Add payslip without run
        payslips_to_post = self.filtered(lambda slip: not slip.payslip_run_id)

        # Adding pay slips from a batch and deleting pay slips with a batch that is not ready for validation.
        payslip_runs = (self - payslips_to_post).mapped('payslip_run_id')
        for run in payslip_runs:
            if run.type_slip_pay != "slip":
                return res
            if run._are_payslips_ready():
                payslips_to_post |= run.slip_ids

        # A payslip need to have a done state and not an accounting move.
        if self.env.context.get('tipo'):
            if self.env.context.get('tipo') == 'academic':
                tipo = "academic"
        else:
            tipo = ["admin", "rol_electronico"]
        payslips_to_post = payslips_to_post.filtered(
            lambda slip: slip.state == 'done' and not slip.move_id and slip.employee_id.employee_type in tipo)
        # Check that a journal exists on all the structures
        for payslip in payslips_to_post:
            if not payslip.struct_id:
                raise UserError(_('El contrato de %s no tiene estructura') % (payslip.employee_id.name))

        for structure in payslips_to_post.mapped('struct_id'):
            if not structure.journal_id:
                raise UserError(_('La estructura %s no tiene diario contable definido') % (structure.name))

        # Map all payslips by structure journal and pay slips month.
        # {'journal_id': {'month': [slip_ids]}}

        slip_mapped_data = {
            slip.struct_id.journal_id.id: {fields.Date().end_of(slip.date_to, 'month'): self.env['hr.payslip']} for slip
            in payslips_to_post}
        for slip in payslips_to_post:
            slip_mapped_data[slip.struct_id.journal_id.id][fields.Date().end_of(slip.date_to, 'month')] |= slip

        tipo_nomina = 'ACADÉMICA' if self.env.context.get('tipo') == 'academic' else 'ADMINISTRACIÓN'

        # slip_mapped_data.filtered(lambda x: x.line_ids.filtered(lambda x: x.employee_id.employee_type=='admin'))
        # analytic_tag_ids
        for journal_id in slip_mapped_data:  # For each journal_id.
            for slip_date in slip_mapped_data[journal_id]:  # For each month.
                line_ids = []
                debit_sum = 0.0
                credit_sum = 0.0
                date = slip_date
                move_dict = {
                    'narration': '',
                    'ref': 'Nómina Mensual Área ' + tipo_nomina + ' del ' + date.strftime('%B %Y'),
                    'journal_id': journal_id,
                    'date': date,
                }

                for slip in slip_mapped_data[journal_id][slip_date]:
                    move_dict['narration'] += slip.number or '' + ' - ' + slip.employee_id.name or ''
                    move_dict['narration'] += '\n'
                    for line in slip.line_ids.filtered(lambda line: line.category_id):
                        amount = -line.total if slip.credit_note else line.total
                        if line.employee_id.department_id.reparticion_nomina:
                            for sede in line.employee_id.department_id.analityc_department_id:
                                if line.code == 'NET':  # Check if the line is the 'Net Salary'.
                                    for tmp_line in slip.line_ids.filtered(lambda line: line.category_id):
                                        if tmp_line.salary_rule_id.not_computed_in_net:  # Check if the rule must be computed in the 'Net Salary' or not.
                                            if amount > 0:
                                                amount -= (abs(tmp_line.total) * (sede.porcentaje_nomina / 100))
                                            elif amount < 0:
                                                amount += (abs(tmp_line.total) * (sede.porcentaje_nomina / 100))
                                if float_is_zero(amount, precision_digits=precision):
                                    continue
                                debit_account_id = line.salary_rule_id.account_debit.id
                                credit_account_id = line.salary_rule_id.account_credit.id

                                if debit_account_id:  # If the rule has a debit account.
                                    # debit = amount if amount > 0.0 else 0.0
                                    # credit = -amount if amount < 0.0 else 0.0
                                    debit = round(abs(amount) * (sede.porcentaje_nomina / 100), 2)
                                    credit = 0.0

                                    existing_debit_lines = (
                                        line_id for line_id in line_ids if
                                        line_id['name'] == line.name
                                        and line_id['account_id'] == debit_account_id
                                        and line_id['analytic_account_id'] == sede.account_analytic_id.id
                                        and ((line_id['debit'] > 0 and credit <= 0) or (
                                                    line_id['credit'] > 0 and debit <= 0)))
                                    debit_line = next(existing_debit_lines, False)
                                    if not debit_line:
                                        debit_line = {
                                            'name': line.name,
                                            'partner_id': False,
                                            'account_id': debit_account_id,
                                            'journal_id': slip.struct_id.journal_id.id,
                                            'date': date,
                                            'debit': debit,
                                            'credit': credit,
                                            'analytic_account_id': sede.account_analytic_id.id,
                                        }
                                        line_ids.append(debit_line)
                                    else:
                                        debit_line['debit'] += debit
                                        debit_line['credit'] += credit

                                if credit_account_id:  # If the rule has a credit account.
                                    # debit = -amount if amount < 0.0 else 0.0
                                    # credit = amount if amount > 0.0 else 0.0
                                    debit = 0.0
                                    credit = round(abs(amount) * (sede.porcentaje_nomina / 100), 2)
                                    # import pdb
                                    # pdb.set_trace()

                                    existing_credit_line = (
                                        line_id for line_id in line_ids if
                                        line_id['name'] == line.name
                                        and line_id['account_id'] == credit_account_id
                                        and line_id['analytic_account_id'] == sede.account_analytic_id.id
                                        and ((line_id['debit'] > 0 and credit <= 0) or (
                                                    line_id['credit'] > 0 and debit <= 0))
                                    )
                                    credit_line = next(existing_credit_line, False)

                                    if not credit_line:
                                        credit_line = {
                                            'name': line.name,
                                            'partner_id': False,
                                            'account_id': credit_account_id,
                                            'journal_id': slip.struct_id.journal_id.id,
                                            'date': date,
                                            'debit': debit,
                                            'credit': credit,
                                            'analytic_account_id': sede.account_analytic_id.id,
                                        }
                                        line_ids.append(credit_line)
                                    else:
                                        credit_line['debit'] += debit
                                        credit_line['credit'] += credit
                        else:
                            cuenta_analitica_id = self.env["analityc.department"].search(
                                [("department_id", "=", line.employee_id.department_id.id),
                                 ("sede_id", "=", line.employee_id.sede_id.id)], limit=1)
                            if line.code == 'NET':  # Check if the line is the 'Net Salary'.
                                for tmp_line in slip.line_ids.filtered(lambda line: line.category_id):
                                    if tmp_line.salary_rule_id.not_computed_in_net:  # Check if the rule must be computed in the 'Net Salary' or not.
                                        if amount > 0:
                                            amount -= abs(tmp_line.total)
                                        elif amount < 0:
                                            amount += abs(tmp_line.total)
                            if float_is_zero(amount, precision_digits=precision):
                                continue
                            debit_account_id = line.salary_rule_id.account_debit.id
                            credit_account_id = line.salary_rule_id.account_credit.id

                            if debit_account_id:  # If the rule has a debit account.
                                # debit = amount if amount > 0.0 else 0.0
                                # credit = -amount if amount < 0.0 else 0.0
                                debit = abs(round(amount, 2))
                                credit = 0.0

                                existing_debit_lines = (
                                    line_id for line_id in line_ids if
                                    line_id['name'] == line.name
                                    and line_id['account_id'] == debit_account_id
                                    and line_id['analytic_account_id'] == cuenta_analitica_id.account_analytic_id.id
                                    and ((line_id['debit'] > 0 and credit <= 0) or (
                                            line_id['credit'] > 0 and debit <= 0)))
                                debit_line = next(existing_debit_lines, False)
                                if not debit_line:
                                    debit_line = {
                                        'name': line.name,
                                        'partner_id': False,
                                        'account_id': debit_account_id,
                                        'journal_id': slip.struct_id.journal_id.id,
                                        'date': date,
                                        'debit': debit,
                                        'credit': credit,
                                        'analytic_account_id': cuenta_analitica_id.account_analytic_id.id,
                                    }
                                    line_ids.append(debit_line)
                                else:
                                    debit_line['debit'] += debit
                                    debit_line['credit'] += credit

                            if credit_account_id:  # If the rule has a credit account.
                                # debit = -amount if amount < 0.0 else 0.0
                                # credit = amount if amount > 0.0 else 0.0
                                debit = 0.0
                                credit = abs(round(amount, 2))
                                # import pdb
                                # pdb.set_trace()

                                existing_credit_line = (
                                    line_id for line_id in line_ids if
                                    line_id['name'] == line.name
                                    and line_id['account_id'] == credit_account_id
                                    and line_id['analytic_account_id'] == cuenta_analitica_id.account_analytic_id.id
                                    and ((line_id['debit'] > 0 and credit <= 0) or (
                                            line_id['credit'] > 0 and debit <= 0))
                                )
                                credit_line = next(existing_credit_line, False)

                                if not credit_line:
                                    credit_line = {
                                        'name': line.name,
                                        'partner_id': False,
                                        'account_id': credit_account_id,
                                        'journal_id': slip.struct_id.journal_id.id,
                                        'date': date,
                                        'debit': debit,
                                        'credit': credit,
                                        'analytic_account_id': cuenta_analitica_id.account_analytic_id.id,
                                    }
                                    line_ids.append(credit_line)
                                else:
                                    credit_line['debit'] += debit
                                    credit_line['credit'] += credit
                for line_id in line_ids:  # Get the debit and credit sum.
                    debit_sum += line_id['debit']
                    credit_sum += line_id['credit']

                # The code below is called if there is an error in the balance between credit and debit sum.
                if float_compare(credit_sum, debit_sum, precision_digits=precision) == -1:
                    acc_id = slip.journal_id.default_credit_account_id.id
                    if not acc_id:
                        raise UserError(
                            _('The Expense Journal "%s" has not properly configured the Credit Account!') % (
                                slip.journal_id.name))
                    existing_adjustment_line = (
                        line_id for line_id in line_ids if line_id['name'] == _('Adjustment Entry')
                    )
                    adjust_credit = next(existing_adjustment_line, False)

                    if not adjust_credit:
                        adjust_credit = {
                            'name': _('Adjustment Entry'),
                            'partner_id': False,
                            'account_id': acc_id,
                            'journal_id': slip.journal_id.id,
                            'date': date,
                            'debit': 0.0,
                            'credit': debit_sum - credit_sum,
                        }
                        line_ids.append(adjust_credit)
                    else:
                        adjust_credit['credit'] = debit_sum - credit_sum

                elif float_compare(debit_sum, credit_sum, precision_digits=precision) == -1:
                    acc_id = slip.journal_id.default_debit_account_id.id
                    if not acc_id:
                        raise UserError(_('The Expense Journal "%s" has not properly configured the Debit Account!') % (
                            slip.journal_id.name))
                    existing_adjustment_line = (
                        line_id for line_id in line_ids if line_id['name'] == _('Adjustment Entry')
                    )
                    adjust_debit = next(existing_adjustment_line, False)

                    if not adjust_debit:
                        adjust_debit = {
                            'name': _('Adjustment Entry'),
                            'partner_id': False,
                            'account_id': acc_id,
                            'journal_id': slip.journal_id.id,
                            'date': date,
                            'debit': credit_sum - debit_sum,
                            'credit': 0.0,
                        }
                        line_ids.append(adjust_debit)
                    else:
                        adjust_debit['debit'] = credit_sum - debit_sum

                # Add accounting lines in the move

                move_dict['line_ids'] = [(0, 0, line_vals) for line_vals in line_ids]
                move = self.env['account.move'].with_context(from_rrhh=True).create(move_dict)
                for slip in slip_mapped_data[journal_id][slip_date]:
                    slip.write({'move_id': move.id, 'date': date})
                print(move)
        return res

    def send_mail(self):
        """Envía el rol de pagos por correo electrónico al empleado"""
        # Verificar que el empleado tenga correo privado configurado
        if not self.employee_id.email_private:
            raise UserError(
                f"El empleado {self.employee_id.name} no tiene configurado un correo electrónico personal (email_private).")

        _logger.info("Iniciando envío de rol para %s <%s>", self.employee_id.name, self.employee_id.email_private)

        util_model = self.env['ecua.utils']
        email_to = self.employee_id.email_private
        subject = f'Rol de Pagos: {self.name or ""} - {self.employee_id.name}'

        # Construcción del cuerpo HTML mejorado
        period_str = f"{self.date_from.strftime('%d/%m/%Y')} al {self.date_to.strftime('%d/%m/%Y')}"

        body_html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #2C5282;">Rol de Pagos</h2>
            <p>Estimado/a <strong>{self.employee_id.name}</strong>,</p>
            <p>Se adjunta su rol de pagos correspondiente al período <strong>{period_str}</strong>.</p>

            <div style="border: 1px solid #E2E8F0; border-radius: 5px; padding: 15px; margin: 20px 0; background-color: #F7FAFC;">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr style="background-color: #EDF2F7;">
                        <th style="padding: 8px; text-align: left; border-bottom: 1px solid #CBD5E0;">Empleado</th>
                        <th style="padding: 8px; text-align: left; border-bottom: 1px solid #CBD5E0;">Período</th>
                        <th style="padding: 8px; text-align: left; border-bottom: 1px solid #CBD5E0;">Concepto</th>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #E2E8F0;">{self.employee_id.name}</td>
                        <td style="padding: 8px; border-bottom: 1px solid #E2E8F0;">{period_str}</td>
                        <td style="padding: 8px; border-bottom: 1px solid #E2E8F0;">Rol de Pagos</td>
                    </tr>
                </table>
            </div>

            <p>Por favor revise el documento adjunto. Si tiene alguna pregunta, no dude en contactarnos.</p>

            <p>Saludos cordiales,<br>
            Departamento de Recursos Humanos</p>
        </div>
        """

        # Generar reporte PDF
        try:
            model_report = 'hr.payslip'
            name_report = 'ec_payroll.payslip_rol_report'
            ids_report = [self.id]
            reports = []

            for obj in self:
                filename = f"Rol_de_Pagos_{obj.employee_id.name}_{obj.date_from.strftime('%Y%m%d')}"
                report_data = util_model.create_report(ids_report, name_report, model_report, filename)
                if report_data:
                    reports.append(report_data[0])
                    _logger.info("Reporte PDF generado correctamente para %s", self.employee_id.name)
        except Exception as e:
            _logger.error("Error al generar reporte PDF para %s: %s", self.employee_id.name, e)
            raise UserError(f"No se pudo generar el reporte PDF para {self.employee_id.name}. Error: {str(e)}")

        attachment_vals = []
        if reports:
            try:
                pdf_data = base64.b64decode(reports[0][1])
                attachment_vals = [(0, 0, {
                    'name': f"Rol_de_Pagos_{self.employee_id.name}_{self.date_from.strftime('%Y%m%d')}.pdf",
                    'datas': base64.b64encode(pdf_data),
                    'type': 'binary',
                    'mimetype': 'application/pdf',
                })]
            except Exception as e:
                _logger.error("Error al procesar el archivo PDF para %s: %s", self.employee_id.name, e)
                raise UserError(f"Error al procesar el archivo PDF para {self.employee_id.name}. Error: {str(e)}")

        # ===== OPCIÓN 1: Usando la configuración SMTP de Odoo (comentado) =====
        # # Configuración del servidor de correo
        # # Estos valores se usarán para el remitente, pero el envío usará la configuración SMTP de Odoo
        # email_from = 'sgrandes@pluslogistics.com.ec'
        #
        # # Crear y enviar el correo usando mail.mail
        # try:
        #     mail = self.env['mail.mail'].create({
        #         'email_from': email_from,
        #         'email_to': email_to,
        #         'subject': subject,
        #         'body_html': body_html,
        #         'attachment_ids': attachment_vals,
        #     })
        #     # Enviar correo usando la configuración SMTP de Odoo
        #     mail.send()
        #     _logger.info("Correo enviado correctamente a %s <%s>", self.employee_id.name, email_to)
        #     return True
        # except Exception as e:
        #     _logger.error("Error al enviar correo a %s <%s>: %s", self.employee_id.name, email_to, e)
        #     raise UserError(f"No se pudo enviar el correo a {self.employee_id.name}. Error: {str(e)}")

        # ===== OPCIÓN 2: Usando smtplib directamente (activo) =====
        # Configuración del servidor de correo Gmail (independiente de la configuración de Odoo)
        smtp_server = 'smtp.gmail.com'
        smtp_port = 465
        smtp_user = 'sistemaspluslogistics@gmail.com'
        smtp_password = 'hnswdvtdcogpvazr'
        email_from = smtp_user

        try:
            # Importar las bibliotecas necesarias
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            from email.mime.application import MIMEApplication
            import smtplib
            import ssl

            # Crear mensaje multipart
            msg = MIMEMultipart()
            msg['From'] = email_from
            msg['To'] = email_to
            msg['Subject'] = subject

            # Adjuntar el cuerpo HTML
            msg.attach(MIMEText(body_html, 'html'))

            # Adjuntar el PDF si existe
            if reports:
                pdf_data = base64.b64decode(reports[0][1])
                pdf_attachment = MIMEApplication(pdf_data, _subtype='pdf')
                pdf_attachment.add_header('Content-Disposition', 'attachment',
                                          filename=f"Rol_de_Pagos_{self.employee_id.name}_{self.date_from.strftime('%Y%m%d')}.pdf")
                msg.attach(pdf_attachment)

            # Crear conexión segura y enviar el correo
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) as server:
                server.login(smtp_user, smtp_password)
                server.sendmail(email_from, email_to, msg.as_string())

            _logger.info("Correo enviado correctamente a %s <%s>", self.employee_id.name, email_to)
            return True
        except Exception as e:
            _logger.error("Error al enviar correo a %s <%s>: %s", self.employee_id.name, email_to, e)
            raise UserError(f"No se pudo enviar el correo a {self.employee_id.name}. Error: {str(e)}")

    def _prepare_slip_lines(self, date, line_ids, type=None):
        self.ensure_one()
        precision = self.env['decimal.precision'].precision_get('Payroll')
        new_lines = []
        for line in self.line_ids.filtered(lambda line: line.category_id):
            if type == 'normal':
                if line.salary_rule_id.category_id.code == 'CONT':
                    continue
            if type == 'provision':
                if line.salary_rule_id.category_id.code != 'CONT':
                    continue
            amount = line.total
            if line.code == 'NET':
                for tmp_line in self.line_ids.filtered(lambda line: line.category_id):
                    if tmp_line.salary_rule_id.not_computed_in_net:
                        if amount > 0:
                            amount -= abs(tmp_line.total)
                        elif amount < 0:
                            amount += abs(tmp_line.total)
            if float_is_zero(amount, precision_digits=precision):
                continue
            debit_account_id = line.salary_rule_id.account_debit.id
            credit_account_id = line.salary_rule_id.account_credit.id

            # Add employee information
            employee_partner_id = self.employee_id.address_home_id.id
            line_name = line.name

            if debit_account_id:
                debit = abs(amount)
                credit = 0.00
                debit_line = self._get_existing_lines(
                    line_ids + new_lines,
                    line,
                    debit_account_id,
                    debit,
                    credit,
                    employee_partner_id
                )

                if not debit_line:
                    debit_line = self._prepare_line_values(line, debit_account_id, date, debit, credit)
                    debit_line.update({
                        'name': line_name,
                        'partner_id': employee_partner_id,
                        'tax_ids': [(4, tax_id) for tax_id in line.salary_rule_id.account_debit.tax_ids.ids]
                    })
                    new_lines.append(debit_line)
                else:
                    debit_line['debit'] += debit
                    debit_line['credit'] += credit

            if credit_account_id:
                credit = abs(amount)
                debit = 0.00
                credit_line = self._get_existing_lines(
                    line_ids + new_lines,
                    line,
                    credit_account_id,
                    debit,
                    credit,
                    employee_partner_id
                )

                if not credit_line:
                    credit_line = self._prepare_line_values(line, credit_account_id, date, debit, credit)
                    credit_line.update({
                        'name': line_name,
                        'partner_id': employee_partner_id,
                        'tax_ids': [(4, tax_id) for tax_id in line.salary_rule_id.account_credit.tax_ids.ids]
                    })
                    new_lines.append(credit_line)
                else:
                    credit_line['debit'] += debit
                    credit_line['credit'] += credit

        return new_lines

    def _get_existing_lines(self, line_ids, line, account_id, debit, credit, partner_id=False):
        """
        Modified to consider partner_id and analytic distribution in line matching
        """
        for temp_line in line_ids:
            analytic_match = str(temp_line.get('analytic_distribution')) == str(self.contract_id.analytic_distribution)
            partner_match = temp_line.get('partner_id') == partner_id

            if (
                    temp_line['account_id'] == account_id
                    and analytic_match
                    and partner_match
                    and (
                    (line.salary_rule_id.category_id.code != 'NET' and line.code != 'NET')
                    or (line.salary_rule_id.category_id.code == 'NET' and line.code == 'NET')
            )
            ):
                return temp_line
        return False

    def _prepare_line_values(self, line, account_id, date, debit, credit):
        """
        Helper function to prepare line values with analytics
        """
        return {
            'name': line.name,
            'partner_id': False,  # Will be updated in _prepare_slip_lines
            'account_id': account_id,
            'journal_id': self.journal_id.id,
            'date': date,
            'debit': debit,
            'credit': credit,
            'analytic_distribution': self.contract_id.analytic_distribution,
            'salary_rule_id': line.salary_rule_id.id,
        }

    def action_create_account_move_draft(self):
        if not self:
            return

        payslips_to_post = self

        # ✅ Borrar solo los asientos en borrador vinculados con estos slips
        move_ids_1 = self.env['account.move'].search([(
            'hr_payslip_run_id', 'in', payslips_to_post.mapped('payslip_run_id').ids),
            ('state', '=', 'draft')
        ])

        move_ids_2 = self.env['account.move'].search([(
            'id', 'in', payslips_to_post.mapped('move_id').ids),
            ('state', '=', 'draft')
        ])

        # Si la acción se está ejecutando desde un lote, borra todos los relacionados al lote
        if len(payslips_to_post) > 1:
            all_draft_move_ids = list(set(move_ids_1.ids + move_ids_2.ids))
        else:
            all_draft_move_ids = move_ids_2.ids

        for i in range(0, len(all_draft_move_ids), 100):
            batch = self.env['account.move'].browse(all_draft_move_ids[i:i + 100])
            batch.unlink()

        company = self[0].company_id
        movement_in_lot = company.movement_in_lot
        grouping_method = company.grouping_method
        separate_for_supplies = company.separate_for_supplies
        precision = self.env['decimal.precision'].precision_get('Payroll')

        if any(not payslip.struct_id for payslip in payslips_to_post):
            raise ValidationError(_('One of the contracts has no structure type.'))
        if any(not structure.journal_id for structure in payslips_to_post.mapped('struct_id')):
            raise ValidationError(_('One of the payroll structures has no journal defined.'))

        slip_mapped_data = defaultdict(lambda: defaultdict(lambda: self.env['hr.payslip']))
        for slip in payslips_to_post:
            slip_mapped_data[slip.struct_id.journal_id.id][
                slip.date or fields.Date().end_of(slip.date_to, 'month')] |= slip

        for journal_id in slip_mapped_data:
            for slip_date in slip_mapped_data[journal_id]:
                slips_for_date = slip_mapped_data[journal_id][slip_date]
                date = slip_date

                if movement_in_lot:
                    # Determine which modes to process
                    modes_to_process = ['normal', 'provision'] if not separate_for_supplies else ['normal']
                    
                    combined_lines_by_key = {}

                    for slip in slips_for_date:
                        contract_analytics = slip.contract_id.analytic_distribution or {}
                        group_key = str(contract_analytics) if grouping_method == 'analytic' else slip.employee_id.id

                        for mode in modes_to_process:
                            lines = slip._prepare_slip_lines(date, [], mode)
                            for line in lines:
                                account_id = line['account_id']
                                key = (account_id, group_key)

                                if key not in combined_lines_by_key:
                                    line_data = {
                                        'name': line.get('salary_rule_name', line['name']),
                                        'debit': 0.0,
                                        'credit': 0.0,
                                        'account_id': account_id,
                                        'journal_id': journal_id,
                                        'date': date,
                                        'partner_id': slip.employee_id.address_home_id.id,
                                    }

                                    if grouping_method == 'analytic' or (movement_in_lot and not separate_for_supplies):
                                        if contract_analytics:
                                            line_data['analytic_distribution'] = contract_analytics

                                    if 'tax_ids' in line:
                                        line_data['tax_ids'] = line['tax_ids']

                                    combined_lines_by_key[key] = line_data

                                combined_lines_by_key[key]['debit'] += line['debit']
                                combined_lines_by_key[key]['credit'] += line['credit']

                    combined_line_ids = list(combined_lines_by_key.values())
                    debit_sum = sum(line['debit'] for line in combined_line_ids)
                    credit_sum = sum(line['credit'] for line in combined_line_ids)

                    if float_compare(credit_sum, debit_sum, precision_digits=precision) == -1:
                        slips_for_date[0]._prepare_adjust_line(combined_line_ids, 'credit', debit_sum, credit_sum, date)
                    elif float_compare(debit_sum, credit_sum, precision_digits=precision) == -1:
                        slips_for_date[0]._prepare_adjust_line(combined_line_ids, 'debit', debit_sum, credit_sum, date)

                    ref = "Rol + Provisión mes de " if not separate_for_supplies else "Rol consolidado mes de "
                    move_dict = {
                        'ref': ref + fields.Date().end_of(slip_date, 'month').strftime('%B %Y'),
                        'journal_id': journal_id,
                        'date': date,
                        'line_ids': [(0, 0, line) for line in combined_line_ids],
                        'hr_payslip_run_id': slips_for_date[0].payslip_run_id.id,
                    }
                    move = self._create_account_move(move_dict)
                    slips_for_date.write({
                        'date': date,
                        'move_id': move.id,
                    })
                    
                    # Create separate provision entry if separate_for_supplies is True
                    if separate_for_supplies:
                        provision_lines_by_key = {}
                        
                        for slip in slips_for_date:
                            contract_analytics = slip.contract_id.analytic_distribution or {}
                            group_key = str(contract_analytics) if grouping_method == 'analytic' else slip.employee_id.id

                            lines = slip._prepare_slip_lines(date, [], 'provision')
                            for line in lines:
                                account_id = line['account_id']
                                key = (account_id, group_key)

                                if key not in provision_lines_by_key:
                                    line_data = {
                                        'name': line.get('salary_rule_name', line['name']),
                                        'debit': 0.0,
                                        'credit': 0.0,
                                        'account_id': account_id,
                                        'journal_id': journal_id,
                                        'date': date,
                                        'partner_id': slip.employee_id.address_home_id.id,
                                    }

                                    if grouping_method == 'analytic':
                                        if contract_analytics:
                                            line_data['analytic_distribution'] = contract_analytics

                                    if 'tax_ids' in line:
                                        line_data['tax_ids'] = line['tax_ids']

                                    provision_lines_by_key[key] = line_data

                                provision_lines_by_key[key]['debit'] += line['debit']
                                provision_lines_by_key[key]['credit'] += line['credit']

                        if provision_lines_by_key:  # Only create if there are provision lines
                            provision_line_ids = list(provision_lines_by_key.values())
                            debit_sum = sum(line['debit'] for line in provision_line_ids)
                            credit_sum = sum(line['credit'] for line in provision_line_ids)

                            if float_compare(credit_sum, debit_sum, precision_digits=precision) == -1:
                                slips_for_date[0]._prepare_adjust_line(provision_line_ids, 'credit', debit_sum, credit_sum, date)
                            elif float_compare(debit_sum, credit_sum, precision_digits=precision) == -1:
                                slips_for_date[0]._prepare_adjust_line(provision_line_ids, 'debit', debit_sum, credit_sum, date)

                            provision_move_dict = {
                                'ref': "Provisión mes de " + fields.Date().end_of(slip_date, 'month').strftime('%B %Y'),
                                'journal_id': journal_id,
                                'date': date,
                                'line_ids': [(0, 0, line) for line in provision_line_ids],
                                'hr_payslip_run_id': slips_for_date[0].payslip_run_id.id,
                            }
                            provision_move = self._create_account_move(provision_move_dict)

                else:
                    for slip in slips_for_date:
                        contract_analytics = slip.contract_id.analytic_distribution or {}

                        # Determine which modes to process
                        modes_to_process = ['normal', 'provision'] if not separate_for_supplies else ['normal']
                        
                        combined_lines = []
                        for mode in modes_to_process:
                            lines = slip._prepare_slip_lines(date, [], mode)
                            for line in lines:
                                line['partner_id'] = slip.employee_id.address_home_id.id
                                if grouping_method == 'analytic':
                                    line['analytic_distribution'] = contract_analytics
                                line.pop('salary_rule_id', None)
                                combined_lines.append(line)

                        debit_sum = sum(line['debit'] for line in combined_lines)
                        credit_sum = sum(line['credit'] for line in combined_lines)

                        if float_compare(credit_sum, debit_sum, precision_digits=precision) == -1:
                            slip._prepare_adjust_line(combined_lines, 'credit', debit_sum, credit_sum, date)
                        elif float_compare(debit_sum, credit_sum, precision_digits=precision) == -1:
                            slip._prepare_adjust_line(combined_lines, 'debit', debit_sum, credit_sum, date)

                        ref = "Rol + Provisión" if not separate_for_supplies else "Rol"
                        move_dict = {
                            'ref': ref + " mes de " + fields.Date().end_of(slip_date, 'month').strftime('%B %Y'),
                            'journal_id': journal_id,
                            'date': date,
                            'line_ids': [(0, 0, line) for line in combined_lines],
                            'hr_payslip_run_id': slip.payslip_run_id.id,
                        }
                        move = self._create_account_move(move_dict)
                        slip.write({
                            'date': date,
                            'move_id': move.id,
                        })
                        
                        # Create separate provision entry if separate_for_supplies is True
                        if separate_for_supplies:
                            provision_lines = []
                            lines = slip._prepare_slip_lines(date, [], 'provision')
                            for line in lines:
                                line['partner_id'] = slip.employee_id.address_home_id.id
                                if grouping_method == 'analytic':
                                    line['analytic_distribution'] = contract_analytics
                                line.pop('salary_rule_id', None)
                                provision_lines.append(line)

                            if provision_lines:  # Only create if there are provision lines
                                debit_sum = sum(line['debit'] for line in provision_lines)
                                credit_sum = sum(line['credit'] for line in provision_lines)

                                if float_compare(credit_sum, debit_sum, precision_digits=precision) == -1:
                                    slip._prepare_adjust_line(provision_lines, 'credit', debit_sum, credit_sum, date)
                                elif float_compare(debit_sum, credit_sum, precision_digits=precision) == -1:
                                    slip._prepare_adjust_line(provision_lines, 'debit', debit_sum, credit_sum, date)

                                provision_move_dict = {
                                    'ref': "Provisión mes de " + fields.Date().end_of(slip_date, 'month').strftime('%B %Y'),
                                    'journal_id': journal_id,
                                    'date': date,
                                    'line_ids': [(0, 0, line) for line in provision_lines],
                                    'hr_payslip_run_id': slip.payslip_run_id.id,
                                }
                                provision_move = self._create_account_move(provision_move_dict)

        return


class AmountPaymentLine(models.Model):
    _name = 'hr.account.payment.line'

    hr_payment_id = fields.Many2one("hr.account.payment")


class hr_payslip_run(models.Model):
    _inherit = 'hr.payslip.run'

    account_payment_id = fields.Many2one('hr.account.payment', ondelete='restrict')
    account_move_count = fields.Integer(compute='_compute_account_move_count', string='Asientos Contables')
    payment_count = fields.Integer(string="Pagos", compute="_compute_payment_count")

    def _compute_payment_count(self):
        for record in self:
            payments = self.env['account.payment'].search([('slip_id', 'in', record.slip_ids.ids)])
            record.payment_count = len(payments)

    def action_open_move_ids(self):
        self.ensure_one()
        move_ids = self.env['account.move'].search([('hr_payslip_run_id', '=', self.id)])
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "views": [[False, "tree"], [False, "form"]],
            "domain": [['id', 'in', move_ids.ids]],
            "name": "Asientos Contables",
        }

    def action_open_payment_ids(self):
        self.ensure_one()
        payments = self.env['account.payment'].search([('slip_id', 'in', self.slip_ids.ids)])
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.payment",
            "views": [[False, "tree"], [False, "form"]],
            "domain": [('id', 'in', payments.ids)],
            "name": "Pagos",
        }

    def _compute_account_move_count(self):
        for run in self:
            # Buscar los asientos contables relacionados con este lote de nóminas
            run.account_move_count = self.env['account.move'].search_count([('hr_payslip_run_id', '=', run.id)])

    def action_create_account_move_draft(self):
        self.slip_ids.action_create_account_move_draft()
        return

    @api.model
    def default_get(self, fields):
        res = super(hr_payslip_run, self).default_get(fields)
        res["structure_type_id"] = False
        if self.env.company.structure_type_id:
            res["structure_type_id"] = self.env.company.structure_type_id.id
        return res

    analytic_account_id = fields.Many2one('account.analytic.account', string=u'Cuenta Analítica')
    move_id = fields.Many2one('account.move', string=u'Movimiento Contable',
                              required=False, readonly=False, states={}, help=u"", ondelete="restrict")
    note = fields.Text(string=u'Notas', required=False, readonly=False, states={}, help=u"")
    state = fields.Selection(selection_add=[
        ('posted', u'Contabilizado'),
        ('cancel', u'Cancelado'),
        ('paid', u'Pagado')
    ])

    journal_id = fields.Many2one('account.journal', 'Salary Journal', domain="[('company_id', '=', company_id)]")
    structure_type_id = fields.Many2one('hr.payroll.structure.type', 'Tipo Estructura', required=True)
    structure_id = fields.Many2one('hr.payroll.structure', 'Estructura Salarial', required=True)
    type_slip_pay = fields.Selection([('slip', 'Roles'), ('holiday', 'Vacaciones'), ('thirteenth', 'Décimo Tercero'),
                                      ('fourteenth', 'Décimo Cuarto')], string=u'Tipo de Nómina',
                                     default='slip')

    def action_validate(self):
        existing_moves = self.env['account.move'].search([('hr_payslip_run_id', 'in', self.ids)])
        if not existing_moves:
            raise ValidationError(_('No se encontraron asientos contables asociados a este lote de nóminas.'))
        self.slip_ids.action_payslip_done()
        self.action_close()
        return

    def action_verify(self):
        # Verifica si no hay slip_ids
        if len(self.slip_ids) == 0:
            raise UserError(_(u'Debe primero generar las nóminas.'))

        # Verifica que todas las slip_ids estén en estado "borrador"
        for slip in self.slip_ids:
            if slip.state != 'draft':
                raise UserError(_(u'Todas las nóminas deben estar en estado "borrador" para poder verificarlas.'))

        # Si todas están en estado "borrador", cambia el estado a "verify"
        self.state = 'verify'

        for slip in self.slip_ids:
            slip.state = 'verify'

    def action_post(self):
        for batch in self:
            existing_moves = self.env['account.move'].search([('hr_payslip_run_id', '=', batch.id)])
            if not existing_moves:
                raise ValidationError(_('No se encontraron asientos contables asociados a este lote de nóminas.'))
            for move in existing_moves:
                move.action_post()
            batch.write({"state": "posted"})
        return

        # def get_move(self):

    #     move_id=False
    #     move_academic_id=False
    #     for line in self.slip_ids.filtered(lambda slip: slip.employee_id.employee_type in ['admin','rol_electronico']):
    #         if line.move_id:
    #             move_id= line.move_id
    #     for line in self.slip_ids.filtered(lambda slip: slip.employee_id.employee_type == 'academic'):
    #         if line.move_id:
    #             move_academic_id= line.move_id
    #
    #     return move_id,move_academic_id

    def cancel_payslip_run(self):
        for run in self:
            run.slip_ids.action_payslip_cancel()
            run.move_id.button_cancel()
        self.write({"state": "cancel"})

    def send_mail_rol(self):
        """Envía los roles de pago por correo electrónico a todos los empleados del lote"""
        success_count = 0
        error_count = 0
        error_employees = []
        total_slips = len(self.slip_ids)

        if not self.slip_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Envío de Roles por Correo',
                    'message': 'No hay roles de pago en este lote.',
                    'type': 'warning',
                    'sticky': False,
                }
            }

        _logger.info("Iniciando envío masivo de %s roles de pago", total_slips)

        for line in self.slip_ids:
            try:
                # Verificar si el empleado tiene correo privado configurado
                if not line.employee_id.email_private:
                    error_msg = f"Sin correo electrónico personal configurado"
                    error_employees.append(f"{line.employee_id.name}: {error_msg}")
                    error_count += 1
                    _logger.warning("No se pudo enviar rol a %s: %s", line.employee_id.name, error_msg)
                    continue

                # Enviar el correo
                line.send_mail()
                success_count += 1

            except Exception as e:
                error_msg = str(e)
                error_employees.append(f"{line.employee_id.name}: {error_msg}")
                error_count += 1
                _logger.error("Error al enviar rol a %s: %s", line.employee_id.name, error_msg)

        # Preparar mensaje de resultado
        message = f"Proceso completado: {success_count} de {total_slips} correos enviados correctamente."
        if error_count > 0:
            message += f" {error_count} roles no pudieron ser enviados."

            # Limitar la cantidad de errores mostrados para evitar mensajes demasiado largos
            if error_employees:
                if len(error_employees) > 10:
                    error_detail = "\n- " + "\n- ".join(
                        error_employees[:10]) + f"\n- ... y {len(error_employees) - 10} más."
                else:
                    error_detail = "\n- " + "\n- ".join(error_employees)
                message += "\n\nDetalles de los errores:" + error_detail

        _logger.info("Finalizado envío masivo: %s éxitos, %s errores", success_count, error_count)

        # Mostrar notificación con los resultados
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Envío de Roles por Correo',
                'message': message,
                'sticky': True,
                'type': 'warning' if error_count else 'success',
            }
        }

    def clean_payroll(self):
        for line in self.slip_ids:
            if line.state != 'draft':
                raise UserError(_(u'No se puede limpiar la nómina, todas las nóminas deben estar en estado borrador.'))
        existing_moves = self.env['account.move'].search([('hr_payslip_run_id', 'in', self.ids)])
        if existing_moves:
            for move in existing_moves:
                if move.state != 'draft':
                    raise UserError(
                        _(u'No se puede limpiar la nómina, todos los asientos contables deben estar en estado borrador.'))
            existing_moves.unlink()
        for line in self.slip_ids:
            line.unlink()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def recalc_payslip_run(self):
        for batch in self:
            for slip in batch.slip_ids:
                if slip.contract_id.state != 'open':
                    raise UserError(_(u'El contrato del empleado %s no está activo.') % (slip.employee_id.name))
                slip.onchange_employee()
            batch.slip_ids.compute_sheet()
        return True

    #
    # def draft_payslip_run(self):
    #     res = super(hr_payslip_run, self).draft_payslip_run()
    #     for batch in self:
    #         if batch.move_id:
    #             batch.move_id.write({
    #                 'state': 'draft'
    #                 })
    #             move_id = batch.move_id
    #             batch.write({
    #                 'move_id': False,
    #                 })
    #             move_id.unlink()
    #         if batch.slip_ids:
    #             batch.slip_ids.action_payslip_cancel()
    #             batch.slip_ids.action_payslip_draft()
    #     return res

    def _get_account_data(self):
        self.ensure_one()
        account_model = self.env['account.account']
        company = self.env.company
        if not company.salarios_account_id:
            raise UserError(
                _(u'Debe configurar la cuenta general de sueldos de la compañía, configure en Nóminas / Configuración / Configuración'))
        batch = self
        move_dict = {
            'narration': self.note,
            'ref': self.name,
            'journal_id': self.journal_id.id,
            'date': self.date_end,
        }
        aml_lines = []
        groups = {}
        for slip in batch.slip_ids:
            grouped_line = {}
            account_data = slip.get_account_data()
            for l in account_data:
                l.update({'partner_id': False})
                account = account_model.browse(l.get('account_id'))
                if l.get('account_id') == company.salarios_account_id.id:
                    # if self.env.context.get('group_account'): ###COMENTADO PARA AGRUPAR CONTABILIZACION
                    if 1 == 1:
                        group = (account.id)
                        if group in groups:
                            if not groups[group]['name'].find(l['name'], 0, len(groups[group]['name'])) > -1:
                                groups[group]['name'] += ' / ' + l['name']
                            groups[group]['debit'] += l['debit']
                            groups[group]['credit'] += l['credit']
                            # groups[group]['force_base_amount'] += l['force_base_amount']
                            # groups[group]['force_tax_amount'] += l['force_tax_amount']
                        else:
                            l.pop('rule')
                            l.update({'analytic_account_id': False})
                            groups[group] = l
                    else:
                        if not grouped_line:
                            l.pop('rule')
                            l.update({'analytic_account_id': False})
                            grouped_line.update(l)
                            grouped_line.update({
                                # slip.employee_id.address_home_id.id, ###COMENTADO PARA AGRUPAR CONTABILIZACION
                                'name': _(u'Neto a pagar')
                            })
                        else:
                            grouped_line['debit'] += l['debit']
                            grouped_line['credit'] += l['credit']
                            # grouped_line['force_base_amount'] += l['force_base_amount']
                            # grouped_line['force_tax_amount'] += l['force_tax_amount']
                elif l.get('rule') and l.get('rule').group_move and not account.code.find('5', 0, 1) >= 0:
                    # group = (account.id, l.get('partner_id'), l.get('name'), l.get('force_base_code_id'), l.get('force_tax_code_id')) ###COMENTADO PARA AGRUPAR CONTABILIZACION
                    group = (account.id)
                    if group in groups:
                        if not groups[group]['name'].find(l['name'], 0, len(groups[group]['name'])) > -1:
                            groups[group]['name'] += ' / ' + l['name']
                        groups[group]['debit'] += l['debit']
                        groups[group]['credit'] += l['credit']
                        # groups[group]['force_base_amount'] += l['force_base_amount']
                        # groups[group]['force_tax_amount'] += l['force_tax_amount']
                    else:
                        if 'rule' in l:
                            l.pop('rule')
                        groups[group] = l
                else:
                    # if self.env.context.get('group_account'): ###COMENTADO PARA AGRUPAR CONTABILIZACION
                    if 1 == 1:
                        group = (account.id)
                        if group in groups:
                            if not groups[group]['name'].find(l['name'], 0, len(groups[group]['name'])) > -1:
                                groups[group]['name'] += ' / ' + l['name']
                            groups[group]['debit'] += l['debit']
                            groups[group]['credit'] += l['credit']
                            # if 'force_base_amount' in groups[group]:

                            #     groups[group]['force_base_amount'] += l['force_base_amount']
                            # if 'force_tax_amount' in groups[group]:
                            #     groups[group]['force_tax_amount'] += l['force_tax_amount']
                        else:
                            if 'rule' in l:
                                l.pop('rule')
                            groups[group] = l
                    else:
                        if 'rule' in l:
                            l.pop('rule')
                        aml_lines.append(l)
            if grouped_line:
                amount = grouped_line.get('debit') - grouped_line.get('credit')
                grouped_line.update({
                    'debit': amount > 0.0 and amount or 0.0,
                    'credit': amount < 0.0 and -amount or 0.0,
                })
                aml_lines.append(grouped_line)
        for group in groups.keys():
            amount = groups[group].get('debit') - groups[group].get('credit')
            groups[group].update({
                'debit': amount > 0.0 and amount or 0.0,
                'credit': amount < 0.0 and -amount or 0.0,
            })
            aml_lines.append(groups[group])
        # aml_lines.sort(key=lambda x: x['partner_id']) ###COMENTADO PARA AGRUPAR CONTABILIZACION
        aml_lines.sort(key=lambda x: x['account_id'])
        move_dict.update({
            'line_ids': [(0, 0, l) for l in aml_lines],
        })

        return move_dict

    def close_payslip_run(self):
        for batch in self:
            batch.slip_ids.action_payslip_done()
        return super(hr_payslip_run, self).close_payslip_run()

    def rebuild_account(self):
        self.ensure_one()
        am_model = self.env['account.move']
        aml_model = self.env['account.move.line']
        company = self.env.company
        if not company.salarios_account_id:
            raise UserError(_(u'Debe tener configurada la cuenta contable de sueldos para poder continuar'))
        if self.move_id:
            move_to_process = self.move_id
            self.move_id = False
            move_to_process.line_ids.remove_move_reconcile()
            move_to_process.button_cancel()
            move_to_process.unlink()
        move_dict = self._get_account_data()
        move = am_model.create(move_dict)
        move.post()
        self.write({
            'move_id': move.id,
        })
        for slip in self.slip_ids:
            aml_to_reconcile = aml_model.search([
                ('move_id', '=', move.id),
                ('account_id', '=', company.salarios_account_id.id),
                ('partner_id', '=', slip.employee_id.address_home_id.id),
            ])
            for payment in slip.payment_ids:
                if payment.state not in ('draft', 'cancelled') and aml_to_reconcile:
                    for paml in payment.move_line_ids:
                        if paml.account_id.id == company.salarios_account_id.id:
                            try:
                                aml_to_reconcile |= paml
                                aml_to_reconcile.reconcile()
                            except Exception as e:
                                _logger.warning(_(u'No se pudo conciliar el pago %s del empleado %s') % (
                                    payment.display_name,
                                    slip.employee_id.address_home_id.display_name))
        return True

    def print_slips(self):
        for batch in self:
            return batch.slip_ids.print_slip()

    def unlink(self):
        move_id = self.move_id if self.move_id else None

        for request in self:
            if request.state != 'draft':
                raise UserError(_(u'No puede borrar una Nómina, que no este en estado en borrador'))

        res = super(hr_payslip_run, self).unlink()

        if move_id:
            move_id.unlink()

        return res
