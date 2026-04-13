# -*- encoding: utf-8 -*-
from odoo import models, api, fields, _
from odoo.tools import float_is_zero, float_compare
from odoo.exceptions import AccessError, UserError, ValidationError


class PosSession(models.Model):
    _inherit = 'pos.session'

    def show_move_deposits(self):
        self.ensure_one()
        move_deposit_ids = []
        for deposit in self.deposit_ids:
            if deposit.move_id:
                move_deposit_ids.append(deposit.move_id.id)
            if deposit.move_surplus_id:
                move_deposit_ids.append(deposit.move_surplus_id.id)
            if deposit.move_missing_id:
                move_deposit_ids.append(deposit.move_missing_id.id)
        return {
            'name': _('Asiento de Depositos'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', move_deposit_ids)],
        }

    def name_get(self):
        res = []
        for r in self:
            stop_at = r.stop_at if r.stop_at else ''
            name = "%s: %s - %s" % (r.name, r.start_at, stop_at)
            res.append((r.id, name))
        return res


    def _compute_amount_residual_deposit(self):
        for rec in self:
            amount_total = 0
            payments = self.env['pos.payment'].search([('session_id', '=', rec.id)])
            for payment in payments:
                if payment.payment_method_id.journal_id.type == 'cash':
                    amount_total += payment.amount
            for deposit in rec.deposit_ids:
                amount_total -= deposit.total_amount
            rec.amount_residual_deposit = amount_total

    warehouse_id = fields.Many2one('stock.warehouse', string='Bodega', related='config_id.picking_type_id.warehouse_id', store=True)
    state_deposit = fields.Selection([('none', 'Sin Deposito'),
                                      ('partial', 'Parcialmente Depositado'),
                                      ('done', 'Depositado')], string='Estado de Deposito', default='none')
    amount_residual_deposit = fields.Monetary(string='Monto Residual de Deposito', compute='_compute_amount_residual_deposit')
    move_deposit_id = fields.Many2one('account.move', string='Asiento de Deposito')
    deposit_ids = fields.Many2many('account.cash.deposit', string='Depositos')

    def set_action_desposit_cash(self):
        for rec in self:
            if rec.state_deposit == 'done':
                raise UserError(_('Ya se realizo un deposito de efectivo para esta sesion'))
        
        return {
            'name': _('Deposito de Efectivo'),
            'type': 'ir.actions.act_window',
            'res_model': 'pos.deposit.cash',
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'new',
            'context': {
                'default_pos_session_ids': self.ids,
            },
        }



    def _get_pos_ui_res_company(self, params):
        company = self.env['res.company'].search_read(**params['search_params'])[0]
        params_country = self._loader_params_res_country()
        if company['country_id']:
            params_country['search_params']['domain'] = [('id', '=', company['country_id'][0])]
            company['country'] = self.env['res.country'].search_read(**params_country['search_params'])[0]
        else:
            company['country'] = None
        company['fallback_nomenclature_id'] = self._get_pos_fallback_nomenclature()
        if company['partner_id']:
            partner_id = self.env['res.partner'].browse(company['partner_id'][0])
            if partner_id.business_name:
                company['business_name'] = partner_id.business_name
        else:
            company['business_name'] = None
        return company

    def _loader_params_res_partner(self):
        result = super()._loader_params_res_partner()
        result['search_params']['fields'].extend(['l10n_latam_identification_type_id'])
        result['search_params']['fields'].extend(['city_id'])
        result['search_params']['fields'].extend(['credit', 'debit'])
        result['search_params']['limit'] = 1000
        result['search_params']['order'] = 'write_date desc'
        return result

    def _loader_params_product_product(self):
        result = super()._loader_params_product_product()
        result['search_params']['fields'].append('x_pos_note')
        return result
    def _pos_ui_models_to_load(self):
        result = super()._pos_ui_models_to_load()
        new_model = 'l10n_latam.identification.type'
        result.append(new_model)
        new_model = 'res.city'
        result.append(new_model)
        return result
    def _loader_params_l10n_latam_identification_type(self):
        return {'search_params': {'fields': ['id', 'name']}}

    def _loader_params_res_city(self):
        domain = [('zipcode', '!=', False)]
        if self.company_id.country_id:
            domain.append(('country_id', '=', self.company_id.country_id.id))
        return {'search_params': {'fields': ['id', 'name','zipcode','state_id','country_id'], 'domain': domain}}

    def _get_pos_ui_l10n_latam_identification_type(self, params):
        l10n_latam_identification_types = self.env['l10n_latam.identification.type'].search_read(**params['search_params'])
        return l10n_latam_identification_types

    def _get_pos_ui_res_city(self, params):
        res_citys = []
        res_citys_large = self.env['res.city'].search_read(**params['search_params'])
        for res_city in res_citys_large:
            # The domain already filters zipcode != False, but we keep the length check as per original logic
            if res_city.get('zipcode') and len(res_city['zipcode']) == 4:
                res_citys.append(res_city)
        return res_citys

    def _loader_params_pos_payment_method(self):
        result = super()._loader_params_pos_payment_method()
        result['search_params']['fields'].extend(['x_ask_reference', 'x_surcharge_percentage', 'x_surcharge_product_id', 'x_ask_lote_auth'])
        return result



    def _get_invoice_total_list(self):
        invoice_list = []
        for order in self.order_ids.filtered(lambda o: o.is_invoiced):
            invoice_date = order.account_move.invoice_date or order.account_move.date
            invoice = {
                'total': order.account_move.amount_total,
                'name': order.account_move.name,
                'order_ref': order.pos_reference,
                'date': invoice_date.strftime('%Y-%m-%d') if invoice_date else '',
            }
            invoice_list.append(invoice)
        return invoice_list

    def _create_combine_account_payment(self, payment_method, amounts, diff_amount):
        outstanding_account = payment_method.outstanding_account_id or self.company_id.account_journal_payment_debit_account_id
        destination_account = self._get_receivable_account(payment_method)

        if float_compare(amounts['amount'], 0, precision_rounding=self.currency_id.rounding) < 0:
            # revert the accounts because account.payment doesn't accept negative amount.
            outstanding_account, destination_account = destination_account, outstanding_account

        # Collect payment references
        pos_payments = self.env['pos.payment'].search([('session_id', '=', self.id), ('payment_method_id', '=', payment_method.id)])
        payment_references = [p.x_payment_reference for p in pos_payments if p.x_payment_reference]
        x_payment_reference = " - ".join(payment_references) if payment_references else False

        account_payment = self.env['account.payment'].create({
            'amount': abs(amounts['amount']),
            'journal_id': payment_method.journal_id.id,
            'force_outstanding_account_id': outstanding_account.id,
            'destination_account_id':  destination_account.id,
            'ref': _('Combine %s POS payments from %s') % (payment_method.name, self.name),
            'pos_payment_method_id': payment_method.id,
            'pos_session_id': self.id,
            'forma_pago_id': payment_method.journal_id.forma_pago_id.id if payment_method.journal_id.forma_pago_id else self.company_id.forma_pago_id.id,
            'payment_reference': x_payment_reference,
        })

        diff_amount_compare_to_zero = self.currency_id.compare_amounts(diff_amount, 0)
        if diff_amount_compare_to_zero != 0:
            self._apply_diff_on_account_payment_move(account_payment, payment_method, diff_amount)

        account_payment.action_post()
        return account_payment.move_id.line_ids.filtered(lambda line: line.account_id == account_payment.destination_account_id)


class PosDepositCash(models.Model):
    _name = 'pos.deposit.cash'

    amount_total = fields.Float(string='Total', required=True)
    amount_surplus = fields.Float(string='Sobrante', required=True)
    amount_missing = fields.Float(string='Faltante', required=True)
    bank_journal_id = fields.Many2one('account.journal', string='Banco', required=True, domain="[('type', '=', 'bank')]")
    pos_session_ids = fields.Many2many('pos.session', string='Sesiones de TPV', domain="[('state', '=', 'closed'), ('state_deposit', '!=', 'done')]")
    pos_method_ids = fields.Many2many('pos.payment.method', string='Metodos de Pago')
    description = fields.Text(string='Descripción')
    date = fields.Date(string='Fecha', default=lambda self: self.env['ec.tools'].get_date_now())
    number_ref = fields.Char(string='Número de Referencia/Deposito', required=True)
    account_id = fields.Many2one('account.account', "Cuenta Contable para Faltante")

    @api.model
    def default_get(self, fields_list):
        """Calcular valores por defecto basados en las sesiones seleccionadas"""
        res = super(PosDepositCash, self).default_get(fields_list)
        
        # Si hay sesiones en el contexto, calcular los valores
        if self.env.context.get('default_pos_session_ids'):
            session_ids = self.env.context.get('default_pos_session_ids')
            sessions = self.env['pos.session'].browse(session_ids)
            
            import logging
            _logger = logging.getLogger(__name__)
            _logger.info(f"=== DEPOSIT CASH DEBUG ===")
            _logger.info(f"Session IDs: {session_ids}")
            _logger.info(f"Sessions found: {len(sessions)}")
            
            amount_total = 0
            amount_surplus = 0
            amount_missing = 0
            pos_method_ids = []
            
            for session in sessions:
                _logger.info(f"Processing session: {session.name}")
                
                payments = self.env['pos.payment'].search([('session_id', '=', session.id)])
                _logger.info(f"  Payments found: {len(payments)}")
                
                for payment in payments:
                    _logger.info(f"    Payment: {payment.amount}, Method: {payment.payment_method_id.name}, Journal Type: {payment.payment_method_id.journal_id.type}")
                    if payment.payment_method_id.journal_id.type == 'cash':
                        amount_total += payment.amount
                        if payment.payment_method_id.id not in pos_method_ids:
                            pos_method_ids.append(payment.payment_method_id.id)
                
                _logger.info(f"  Statement lines: {len(session.statement_line_ids)}")
                for cash in session.statement_line_ids:
                    _logger.info(f"    Statement line: {cash.amount}")
                    amount_total += cash.amount
                
                _logger.info(f"  Cash difference: {session.cash_register_difference}")
                if session.cash_register_difference > 0:
                    amount_surplus += abs(session.cash_register_difference)
                elif session.cash_register_difference < 0:
                    amount_missing += abs(session.cash_register_difference)
            
            _logger.info(f"FINAL - Total: {amount_total}, Surplus: {amount_surplus}, Missing: {amount_missing}")
            _logger.info(f"Payment methods: {pos_method_ids}")
            
            res['amount_total'] = amount_total
            res['amount_surplus'] = amount_surplus
            res['amount_missing'] = amount_missing
            res['pos_method_ids'] = [(6, 0, pos_method_ids)]
        
        return res

    @api.onchange('pos_session_ids')
    def _onchange_pos_session_ids(self):
        if self.pos_session_ids:
            amount_total = 0
            amount_surplus = 0
            amount_missing = 0
            pos_method_ids = []
            
            # Obtener IDs reales de las sesiones (pueden ser NewId en onchange)
            real_ids = []
            for s in self.pos_session_ids:
                if isinstance(s.id, int):
                    real_ids.append(s.id)
                elif hasattr(s, '_origin') and s._origin and isinstance(s._origin.id, int):
                    real_ids.append(s._origin.id)
            
            if not real_ids:
                return
            
            existing_sessions = self.env['pos.session'].browse(real_ids)
            
            for rec in existing_sessions:
                payments = self.env['pos.payment'].search([('session_id', '=', rec.id)])
                for payment in payments:
                    if payment.payment_method_id.journal_id.type == 'cash':
                        amount_total += payment.amount
                        if payment.payment_method_id.id not in pos_method_ids:
                            pos_method_ids.append(payment.payment_method_id.id)
                
                for cash in rec.statement_line_ids:
                    amount_total += cash.amount
                
                if rec.cash_register_difference > 0:
                    amount_surplus += abs(rec.cash_register_difference)
                elif rec.cash_register_difference < 0:
                    amount_missing += abs(rec.cash_register_difference)
            
            self.amount_total = amount_total
            self.amount_surplus = amount_surplus
            self.amount_missing = amount_missing
            self.pos_method_ids = [(6, 0, pos_method_ids)]

    def action_deposit(self):
        if not self.pos_session_ids:
            raise UserError(_('Debe seleccionar al menos una sesión para realizar el depósito'))
        
        # if len(self.pos_method_ids) != 1:
        #     raise UserError(_('Solo puede realizar un deposito por metodo de pago'))
        cash_journal_id = self.pos_method_ids[0].journal_id
        depostit_cash = self.env['account.cash.deposit'].create({
            'cash_journal_id': cash_journal_id.id,
            'bank_journal_id': self.bank_journal_id.id,
            'operation_type': 'deposit',
            'from_pos': True,
            'date': self.date,
            'notes': self.description,
            'sesion_ids': [(6, 0, self.pos_session_ids.ids)],
        })
        total = round(self.amount_total, 2) + round(self.amount_surplus, 2)
        total = str(total).split(".")
        total_entero = total[0]
        total_decimal = total[1] if len(total) > 1 else '00'
        total_entero = int(total_entero)
        # Asegurarnos que total_decimal tenga siempre 2 dígitos
        total_decimal = int(total_decimal.ljust(2, '0')[:2])
        
        # Obtener la moneda USD
        usd_currency = self.env.ref('base.USD')
        
        cash_unit_id = self.env['cash.unit'].search([
            ('value','=',1),
            ('cash_type','=','coin'),
            ('currency_id','=',usd_currency.id)
        ], limit=1)
        acount_cash_deposit_line = self.env['account.cash.deposit.line'].create({
            'parent_id': depostit_cash.id,
            'qty': total_entero,
            'cash_unit_id': cash_unit_id.id,
        })
        cash_unit_id = self.env['cash.unit'].search([
            ('value', '=', 0.01),
            ('cash_type','=','coin'),
            ('currency_id','=',usd_currency.id)
        ], limit=1)
        acount_cash_deposit_line = self.env['account.cash.deposit.line'].create({
            'parent_id': depostit_cash.id,
            'qty': total_decimal,
            'cash_unit_id': cash_unit_id.id,
        })
        depostit_cash.with_context(amount_surplus=round(self.amount_surplus,2),amount_missing=round(self.amount_missing,2)).validate(self.date)

        for session in self.pos_session_ids:
            session.deposit_ids = [(4, depostit_cash.id)]
            session.state_deposit = 'done'
            # session._compute_amount_residual_deposit()
            # if session.amount_residual_deposit == 0:
            #     session.state_deposit = 'done'
            # else:
            #     session.state_deposit = 'partial'
        return {
            'name': _('Sesiones Depositadas'),
            'type': 'ir.actions.act_window',
            'res_model': 'pos.session',
            'view_mode': 'tree,form',
            'view_type': 'tree',
            'domain': [('id', 'in', self.pos_session_ids.ids)],
            'target': 'current',
        }
