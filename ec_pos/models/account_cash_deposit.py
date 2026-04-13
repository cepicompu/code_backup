# -*- encoding: utf-8 -*-
from odoo import models, api, fields, _
from odoo.tools import float_is_zero, float_compare
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import frozendict

class AccountCashDeposit(models.Model):
    _inherit = 'account.cash.deposit'

    sesion_ids = fields.Many2many('pos.session', string='Sesiones')
    from_pos = fields.Boolean('From POS', default=False)
    move_surplus_id = fields.Many2one('account.move', string='Asiento Sobrante')
    move_missing_id = fields.Many2one('account.move', string='Asiento Faltante')



    def validate(self, force_date=None):
        self.ensure_one()
        self._del_empty_lines()
        vals = self._prepare_validate(force_date=force_date)
        move_vals = self._prepare_account_move(vals)

        context_dict = dict(self.env.context)
        if 'default_amount_total' in context_dict:
            del context_dict['default_amount_total']
        new_context = frozendict(context_dict)
        move = self.env["account.move"].with_context(new_context).create(move_vals)
        move.action_post()
        vals["move_id"] = move.id
        self.write(vals)
        self.sesion_ids.write({'move_deposit_id': move.id})

    def _prepare_account_move(self, vals):
        amount_missing = 0.00
        name_sessions = ""
        for session in self.sesion_ids:
            name_sessions += session.name + ","
        self.ensure_one()
        date = vals.get("date") or self.date
        op_type = self.operation_type
        total_amount_comp_cur = self.currency_id._convert(
            self.total_amount, self.company_id.currency_id, self.company_id, date
        )
        total_amount_comp_cur_cash = total_amount_comp_cur
        #TODO: revisar si se puede mejorar por configuracion
        # if not self.company_id.transfer_account_id:
        #     raise UserError(_("The Inter-Banks Transfer Account is not configured."))
        bank_account_id = self.bank_journal_id.default_account_id.id

        cash_debit = cash_credit = bank_debit = bank_credit = 0.0
        total_amount = self.total_amount
        total_amount_cash = self.total_amount
        if 'amount_surplus' in self._context:
            if self._context['amount_surplus'] != 0.00:
                total_amount_comp_cur_cash = total_amount_comp_cur - self._context['amount_surplus']
                total_amount_cash = total_amount_cash - self._context['amount_surplus']
                surplus_vals = {
                    "account_id": self.company_id.account_journal_early_pay_discount_gain_account_id.id,
                    "partner_id": False,
                    "debit": 0.00,
                    "credit": self._context['amount_surplus'],
                    "currency_id": self.currency_id.id,
                    "amount_currency": self._context['amount_surplus'] * (op_type == "deposit" and -1 or 1),
                }
                data_line_ids = []
                account_debit_id = self.cash_journal_id.profit_account_id.id
                account_credit_id = self.cash_journal_id.default_account_id.id
                data_line_ids.append((0, 0, {'name': "Sobrante " + self.name,
                                             'debit': 0.00,
                                             'credit': self._context['amount_surplus'],
                                             # 'partner_id': self.partner_id.id,
                                             'account_id': account_credit_id,
                                             'date': fields.Date.context_today(self),
                                             'ref': self.name,
                                             'amount_currency': self._context['amount_surplus'] * -1,
                                             }))
                data_line_ids.append((0, 0, {'name': "Sobrante " + self.name,
                                             'debit': self._context['amount_surplus'],
                                             'credit': 0.00,
                                             # 'partner_id': self.partner_id.id,
                                             'account_id': account_debit_id,
                                             'date': fields.Date.context_today(self),
                                             'ref': self.name,
                                             'amount_currency': self._context['amount_surplus'] * 1,
                                             }))
                if len(data_line_ids) != 0:
                    move_vals_surplus = {
                        'date': fields.Date.context_today(self),
                        'ref': "Asiento Para Sobrante " + self.name + " Sesiones:" + name_sessions,
                        'journal_id': self.cash_journal_id.id,
                        # 'partner_id': move.partner_id.id,
                        'move_type': 'entry',
                        'line_ids': data_line_ids
                    }
                    move_id = self.env['account.move'].with_context(default_amount_total=self._context['amount_surplus']).create(move_vals_surplus)
                    move_id.action_post()
                    self.move_surplus_id = move_id.id
        if 'amount_missing' in self._context:
            if self._context['amount_missing'] != 0.00:
                amount_missing =  self._context['amount_missing']
        #         missing_vals = {
        #             "account_id": self.company_id.account_journal_early_pay_discount_loss_account_id.id,
        #             "partner_id": False,
        #             "debit": self._context['amount_missing'],
        #             "credit": 0.00,
        #             "currency_id": self.currency_id.id,
        #             # "amount_currency": self._context['amount_missing'] * (op_type == "deposit" and 1 or -1),
        #         }
        #         data_line_ids = []
        #         account_debit_id = self.cash_journal_id.default_account_id.id
        #         account_credit_id = self.cash_journal_id.loss_account_id.id
        #         data_line_ids.append((0, 0, {'name': "Faltante " + self.name,
        #                                      'debit': self._context['amount_missing'],
        #                                      'credit': 0.00,
        #                                      # 'partner_id': self.partner_id.id,
        #                                      'account_id': account_debit_id,
        #                                      'date': fields.Date.context_today(self),
        #                                      'ref': self.name,
        #                                      # 'amount_currency': self._context['amount_missing'] * 1,
        #                                      }))
        #         data_line_ids.append((0, 0, {'name': "Faltante " + self.name,
        #                                      'debit': 0.00,
        #                                      'credit': self._context['amount_missing'],
        #                                      # 'partner_id': self.partner_id.id,
        #                                      'account_id': account_credit_id,
        #                                      'date': fields.Date.context_today(self),
        #                                      'ref': self.name,
        #                                      # 'amount_currency': self._context['amount_missing'] * -1,
        #                                      }))
        #         if len(data_line_ids) != 0:
        #             move_vals_missing = {
        #                 'date': fields.Date.context_today(self),
        #                 'ref': "Asiento Para Faltante " + self.name + " Sesiones:" + name_sessions,
        #                 'journal_id': self.cash_journal_id.id,
        #                 # 'partner_id': move.partner_id.id,
        #                 'move_type': 'entry',
        #                 'line_ids': data_line_ids
        #             }
        #             move_id = self.env['account.move'].with_context(default_amount_total=self._context['amount_missing']).create(move_vals_missing)
        #             move_id.action_post()
        #             self.move_missing_id = move_id.id
        if op_type == "deposit":
            cash_credit = total_amount_comp_cur_cash
            bank_debit = total_amount_comp_cur
        else:
            cash_debit = total_amount_comp_cur_cash
            bank_credit = total_amount_comp_cur
        # Cash move line

        cash_credit = cash_credit - amount_missing
        bank_debit = bank_debit - amount_missing
        account_id = self.cash_journal_id.default_account_id.id
        cash_vals = {
            "account_id": account_id,
            "partner_id": False,
            "debit": cash_debit,
            "credit": cash_credit,
            "currency_id": self.currency_id.id,
        }
        # Bank move line
        bank_vals = {
            "account_id": bank_account_id,
            "partner_id": False,
            "debit": bank_debit,
            "credit": bank_credit,
            "currency_id": self.currency_id.id,
        }
        line_ids = [(0, 0, cash_vals), (0, 0, bank_vals)]
        if 'amount_surplus' in self._context:
            if self._context['amount_surplus'] != 0.00:
                line_ids.append((0, 0, surplus_vals))
        # if 'amount_missing' in self._context:
        #     if self._context['amount_missing'] != 0.00:
        #         line_ids.append((0, 0, missing_vals))
        move_vals = {
            "journal_id": self.cash_journal_id.id,
            "date": date,
            "ref": self.display_name + " Sesiones:" + name_sessions,
            "company_id": self.company_id.id,
            "line_ids": line_ids,
        }
        return move_vals
