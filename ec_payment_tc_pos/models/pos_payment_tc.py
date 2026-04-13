##############################################################################
#
#    Copyright (C) 2022-Present Speeduplight (<https://speeduplight.com>)
#
##############################################################################
from docutils.parsers.rst.directives import percentage
from passlib.tests.utils import limit

from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.ec_remision.models.shop import sale_shop


class AccountPaymentTcWizard(models.Model):
    _inherit = 'account.payment.tc.wizard'

    def search_payment_2(self, lote, autorizacion, vale, amount):
        payments = self.env['pos.payment'].search([
            ('credit_card_lote', '=', lote),
            ('credit_card_authorization', '=', vale),
            ('credit_card_reference', '=', autorizacion),
            ('amount', '=', round(amount, 2))
        ])
        return payments

    def search_payment(self, lote, autorizacion, vale, amount):
        payments = self.env['pos.payment'].search([
            ('credit_card_lote', '=', lote),
            ('credit_card_authorization', '=', autorizacion),
            ('credit_card_reference', '=', vale),
            ('amount', '=', round(amount, 2))
        ])
        return payments

    def seach_data(self):
        datas = []
        if self.bank_id.type_load_tc == 'bolivariano':
            import base64
            self.ensure_one()
            datas = base64.decodestring(self.data_file).decode(encoding="latin1").split('\n')

            payment_file = self.env['account.payment.tc.files'].create({'name': self.filename,
                                                                        'payment_tc_cab_id': self.account_payment_tc_id.id,
                                                                        })
        if self.bank_id.type_load_tc == 'diners':
            import base64
            self.ensure_one()
            datas = base64.decodestring(self.data_file).decode(encoding="latin1").split('\n')
            payment_file = self.env['account.payment.tc.files'].create({'name': self.filename,
                                                                        'payment_tc_cab_id': self.account_payment_tc_id.id,
                                                                        })
        if self.bank_id.type_load_tc == 'guayaquil':
            import base64
            self.ensure_one()
            datas = base64.decodestring(self.data_file).decode(encoding="latin1").split('\n')

            payment_file = self.env['account.payment.tc.files'].create({'name': self.filename,
                                                                        'payment_tc_cab_id': self.account_payment_tc_id.id,
                                                                        })

        return datas,payment_file

    def check_if_line_valida(self, data):
        if data == "":
            return False
        if self.bank_id.type_load_tc == 'bolivariano':
            if len(data) == 0:
                return False
            if data[0] != '2':
                return False
        if self.bank_id.type_load_tc == 'diners':
            if data[0] not in ('2', '1'):
                return False
        if self.bank_id.type_load_tc == 'guayaquil':
            if len(data) == 0:
                return False
            if data[0] != '2':
                return False
        return True

    def load_file(self):
        cont = 0
        payment_data = []
        payment_pos_data = []
        results = []
        cont_found = 0
        total_comision = 0
        total_iva = 0
        total_renta = 0
        bank_payment = []
        invoices = []
        withholds = []

        datas, payment_file = self.seach_data()
        for data in datas:
            electronic_authorization = ''
            l10n_latam_document_number = ''
            numero_liquidacion = ''
            if not self.check_if_line_valida(data):
                continue
            have_withholding = False
            if self.bank_id.type_load_tc == 'bolivariano':
                local_trade = data[95:105].rstrip()
                sale_shop_id = self.env['sale.shop.local.trade'].search([('local_trade', '=', local_trade)])
                if sale_shop_id:
                    sale_shop_id = sale_shop_id.sale_shop_id.id
                else:
                    sale_shop_id = False
                bin = data[105:124].rstrip()
                invoice_date = self.account_payment_tc_id.date_move
                numero_liquidacion = data[218:227]
                name_code_bank = numero_liquidacion
                name_code_invoice = local_trade
                need_create_invoice = False
                journal_id = self.journal_id
                date = data[79:93]
                date = date[:-6]
                date = date[:4] + "-" + date[4:6] + "-" + date[6:]
                recap = data[4:18]
                recap = recap[-6:]
                lote = data[4:18]
                lote = lote[-6:]
                vale = data[18:32]
                vale = vale[-6:]
                autorizacion = data[46:60]
                autorizacion = autorizacion[-6:]
                valor_neto = data[124:139]
                decimal = valor_neto[len(valor_neto) - 2:]
                entero = valor_neto[:len(valor_neto) - 2]
                valor_neto = entero + "." + decimal
                if valor_neto == ".":
                    valor_neto = "0.00"
                valor_neto = float(valor_neto)
                iva = data[169:184]
                decimal = iva[len(iva) - 2:]
                entero = iva[:len(iva) - 2]
                iva = entero + "." + decimal
                if iva == ".":
                    iva = "0.00"
                iva = float(iva)
                amount = round((valor_neto + iva), 2)
                valor_comision_sin_iva = 0.00
                valor_comision = data[139:154]
                decimal = valor_comision[len(valor_comision) - 2:]
                entero = valor_comision[:len(valor_comision) - 2]
                valor_comision = entero + "." + decimal
                if valor_comision == ".":
                    valor_comision = "0.00"
                valor_comision = float(valor_comision)
                valor_iva = data[184:199]
                decimal = valor_iva[len(valor_iva) - 2:]
                entero = valor_iva[:len(valor_iva) - 2]
                valor_iva = entero + "." + decimal
                if valor_iva == ".":
                    valor_iva = "0.00"
                valor_iva = float(valor_iva)
                valor_renta = data[154:169]
                decimal = valor_renta[len(valor_renta) - 2:]
                entero = valor_renta[:len(valor_renta) - 2]
                valor_renta = entero + "." + decimal
                if valor_renta == ".":
                    valor_renta = "0.00"
                valor_renta = float(valor_renta)
                amount_pay = round((valor_neto - valor_renta - valor_iva), 2)
                valor_bank = round((amount - valor_comision - valor_renta - valor_iva),2)

            if self.bank_id.type_load_tc == 'diners':
                if data[0] == '1':
                    if len(data) == 25:
                        local_trade = data[9:24]
                        local_trade = local_trade.lstrip("0")
                        continue
                sale_shop_id = self.env['sale.shop.local.trade'].search([('local_trade', '=', local_trade)])
                if sale_shop_id:
                    sale_shop_id = sale_shop_id.sale_shop_id.id
                else:
                    sale_shop_id = False
                account_number_bank = data[176:198].lstrip("0")
                res_partner_bank = self.env['res.partner.bank'].search([('acc_number', '=', account_number_bank)])
                if not res_partner_bank:
                    raise UserError("No se encontró el banco con número de cuenta: " + account_number_bank)
                journal_id = self.env['account.journal'].search([('bank_account_id', '=', res_partner_bank.id)])
                if not journal_id:
                    raise UserError("No se encontró el diario con número de cuenta: " + account_number_bank)
                bin = data[9:25]
                numero_liquidacion = data[156:164]
                name_code_bank = numero_liquidacion
                date = data[25:33]
                date = date[:4] + "-" + date[4:6] + "-" + date[6:]
                invoice_date = self.account_payment_tc_id.date_move
                recap = data[134:141]
                recap = recap[-6:]
                lote = data[141:148]
                lote = lote[-6:]
                l10n_latam_document_number_txt = data[270:290]
                l10n_latam_document_number_txt = l10n_latam_document_number_txt.split("-")
                l10n_latam_document_number = l10n_latam_document_number_txt[0] + "-" + l10n_latam_document_number_txt[1] + "-" + l10n_latam_document_number_txt[2][-9:]
                name_code_invoice = l10n_latam_document_number
                need_create_invoice = False
                if lote == '000000':
                    lote = recap
                vale = data[1:9]
                vale = vale[-6:]
                autorizacion = data[164:174]
                autorizacion = autorizacion[-6:]
                amount = data[36:51]
                decimal = amount[len(amount) - 2:]
                entero = amount[:len(amount) - 2]
                amount = entero + "." + decimal
                if amount == ".":
                    amount = "0.00"
                amount = float(amount)

                valor_comision_sin_iva = data[238:254]
                decimal = valor_comision_sin_iva[len(valor_comision_sin_iva) - 2:]
                entero = valor_comision_sin_iva[:len(valor_comision_sin_iva) - 2]
                valor_comision_sin_iva = entero + "." + decimal
                if valor_comision_sin_iva == ".":
                    valor_comision_sin_iva = "0.00"
                valor_comision_sin_iva = float(valor_comision_sin_iva)
                valor_comision_sin_iva = round(valor_comision_sin_iva, 2)


                valor_comision = data[51:66]
                decimal = valor_comision[len(valor_comision) - 2:]
                entero = valor_comision[:len(valor_comision) - 2]
                valor_comision = entero + "." + decimal
                if valor_comision == ".":
                    valor_comision = "0.00"
                valor_comision = float(valor_comision)

                valor_neto = data[66:81]
                decimal = valor_neto[len(valor_neto) - 2:]
                entero = valor_neto[:len(valor_neto) - 2]
                valor_neto = entero + "." + decimal
                if valor_neto == ".":
                    valor_neto = "0.00"
                valor_neto = float(valor_neto)
                valor_neto = round(valor_neto,2)

                valor_iva = data[81:96]
                decimal = valor_iva[len(valor_iva) - 2:]
                entero = valor_iva[:len(valor_iva) - 2]
                valor_iva = entero + "." + decimal
                if valor_iva == ".":
                    valor_iva = "0.00"
                valor_iva = float(valor_iva)


                valor_renta = data[96:111]
                decimal = valor_renta[len(valor_renta) - 2:]
                entero = valor_renta[:len(valor_renta) - 2]
                valor_renta = entero + "." + decimal
                if valor_renta == ".":
                    valor_renta = "0.00"
                valor_renta = float(valor_renta)
                valor_bank = (valor_neto - valor_renta - valor_iva)
                amount_pay = round((valor_neto - valor_renta - valor_iva), 2)

            if self.bank_id.type_load_tc == 'guayaquil':
                if data[93:95] == '04':
                    continue
                account_number_bank = data[549:559].lstrip("0")
                res_partner_bank = self.env['res.partner.bank'].search([('acc_number', '=', account_number_bank)])
                if not res_partner_bank:
                    raise UserError("No se encontró el banco con número de cuenta: " + account_number_bank)
                journal_id = self.env['account.journal'].search([('bank_account_id', '=', res_partner_bank.id)])
                if not journal_id:
                    raise UserError("No se encontró el diario con número de cuenta: " + account_number_bank)

                local_trade = data[95:105].lstrip('0')
                sale_shop_id = self.env['sale.shop.local.trade'].search([('local_trade', '=', local_trade)])
                if sale_shop_id:
                    sale_shop_id = sale_shop_id.sale_shop_id.id
                else:
                    sale_shop_id = False

                bin = data[105:124].rstrip()
                l10n_latam_document_number = data[335:352]
                numero_liquidacion = l10n_latam_document_number
                name_code_invoice = l10n_latam_document_number
                name_code_bank = l10n_latam_document_number
                electronic_authorization = data[353:402]
                date = data[79:87]
                date = date[:4] + "-" + date[4:6] + "-" + date[6:]
                recap = data[4:18]
                recap = recap[-6:]
                lote = data[4:18]
                lote = lote[-6:]
                vale = data[18:32]
                vale = vale[-6:]
                autorizacion = data[291:297]
                invoice_date = data[297:308]
                invoice_date = invoice_date[:4] + "-" + invoice_date[4:6] + "-" + invoice_date[6:]
                autorizacion = autorizacion[-6:]
                need_create_invoice = True

                valor_neto = data[124:139]
                decimal = valor_neto[len(valor_neto) - 2:]
                entero = valor_neto[:len(valor_neto) - 2]
                valor_neto = entero + "." + decimal
                if valor_neto == ".":
                    valor_neto = "0.00"
                valor_neto = float(valor_neto)

                iva = data[169:184]
                decimal = iva[len(iva) - 2:]
                entero = iva[:len(iva) - 2]
                iva = entero + "." + decimal
                if iva == ".":
                    iva = "0.00"
                iva = float(iva)

                amount = round((valor_neto + iva), 2)
                if amount == ".":
                    amount = "0.00"
                amount = float(amount)

                valor_comision_iva = data[203:218]
                decimal = valor_comision_iva[len(valor_comision_iva) - 2:]
                entero = valor_comision_iva[:len(valor_comision_iva) - 2]
                valor_comision_iva = entero + "." + decimal
                if valor_comision_iva == ".":
                    valor_comision_iva = "0.00"
                valor_comision_iva = float(valor_comision_iva)

                valor_comision = data[139:154]
                decimal = valor_comision[len(valor_comision) - 2:]
                entero = valor_comision[:len(valor_comision) - 2]
                valor_comision = entero + "." + decimal
                if valor_comision == ".":
                    valor_comision = "0.00"
                valor_comision = float(valor_comision)
                valor_comision_sin_iva = valor_comision
                valor_comision = valor_comision + valor_comision_iva
                valor_comision = round(valor_comision, 2)

                #revisar si esta correcto
                valor_neto = data[60:75]
                decimal = valor_neto[len(valor_neto) - 2:]
                entero = valor_neto[:len(valor_neto) - 2]
                valor_neto = entero + "." + decimal
                if valor_neto == ".":
                    valor_neto = "0.00"
                valor_neto = float(valor_neto)
                valor_neto = round(valor_neto, 2)

                #cambio para validacion
                valor_neto = amount

                valor_iva = data[184:199]
                decimal = valor_iva[len(valor_iva) - 2:]
                entero = valor_iva[:len(valor_iva) - 2]
                valor_iva = entero + "." + decimal
                if valor_iva == ".":
                    valor_iva = "0.00"
                valor_iva = float(valor_iva)

                valor_renta = data[154:169]
                decimal = valor_renta[len(valor_renta) - 2:]
                entero = valor_renta[:len(valor_renta) - 2]
                valor_renta = entero + "." + decimal
                if valor_renta == ".":
                    valor_renta = "0.00"
                valor_renta = float(valor_renta)

                valor_bank = data[60:75]
                decimal = valor_bank[len(valor_bank) - 2:]
                entero = valor_bank[:len(valor_bank) - 2]
                valor_bank = entero + "." + decimal
                if valor_bank == ".":
                    valor_bank = "0.00"
                valor_bank = float(valor_bank)
                amount_pay = valor_bank

                have_withholding = True
                l10n_latam_document_number_withholding = data[402:419]
                electronic_authorization_withholding = data[419:469]
                base_iva = iva
                valor_consumo = data[124:139]
                decimal = valor_consumo[len(valor_consumo) - 2:]
                entero = valor_consumo[:len(valor_consumo) - 2]
                valor_consumo = entero + "." + decimal
                if valor_consumo == ".":
                    valor_consumo = "0.00"
                valor_consumo = float(valor_consumo)
                base_renta = valor_consumo - valor_comision_sin_iva

            # #Revisar solo esta para boliavariano
            # if cont == 0:
            #     cont += 1
            #     continue
            # # Revisar

            found_payment = False
            payments = self.search_payment(lote, autorizacion, vale, amount)
            if len(payments) != 0:
                for payment in payments:
                    if payment not in payment_pos_data:
                        payment_pos_data.append(payment)
                        found_payment = True
                        cont_found += 1
                        self.env['account.payment.tc.det'].create(
                            {'payment_cab_id': self.account_payment_tc_id.id,
                             'payment_rel_tc_pos_id': payment.id,
                             'payment_date': payment.pos_order_id.date_pos,
                             'partner_id': payment.partner_id.id,
                             'currency_id': payment.currency_id.id,
                             'amount_payment': valor_neto - valor_iva - valor_renta,
                             'amount': payment.amount,
                             'amount_net': valor_neto,
                             'date': payment.pos_order_id.date_pos,
                             'journal_id': payment.payment_method_id.journal_id.id,
                             # 'payment_conciliation_tc': line.payment_conciliation_tc.id,
                             'is_credit_card': payment.payment_method_id.journal_id.credit_card,
                             # 'state_conciliation_tc': line.state_conciliation_tc,
                             # 'type_card': line.type_card,
                             'lote_tc': payment.credit_card_lote,
                             'reference_tc': payment.credit_card_reference,
                             'auth_tc': payment.credit_card_authorization,
                             # 'select_row': True,
                             })
            if not found_payment:
                payments = self.search_payment_2(lote, vale, autorizacion, amount)
                if len(payments) != 0:
                    for payment in payments:
                        if payment not in payment_data:
                            payment_pos_data.append(payment)
                            found_payment = True
                            cont_found += 1
                            self.env['account.payment.tc.det'].create(
                                {'payment_cab_id': self.account_payment_tc_id.id,
                                 'payment_rel_tc_pos_id': payment.id,
                                 'payment_date': payment.pos_order_id.date_pos,
                                 'partner_id': payment.partner_id.id,
                                 'currency_id': payment.currency_id.id,
                                 'amount_payment': valor_neto - valor_iva - valor_renta,
                                 'amount': payment.amount,
                                 'amount_net': valor_neto,
                                 'date': payment.pos_order_id.date_pos,
                                 'journal_id': payment.payment_method_id.journal_id.id,
                                 # 'payment_conciliation_tc': line.payment_conciliation_tc.id,
                                 'is_credit_card': payment.payment_method_id.journal_id.credit_card,
                                 # 'state_conciliation_tc': line.state_conciliation_tc,
                                 # 'type_card': line.type_card,
                                 'lote_tc': payment.credit_card_lote,
                                 'reference_tc': payment.credit_card_reference,
                                 'auth_tc': payment.credit_card_authorization,
                                 # 'select_row': True,
                                 })
            if not any(journal_id.id == e['jorunal_id'] and name_code_bank == e['name_code_bank'] for e in bank_payment):
                bank_payment.append({'name_code_bank': name_code_bank,
                                     'jorunal_id': journal_id.id,
                                     'local_trade': local_trade,
                                     'sale_shop_id': sale_shop_id,
                                     'l10n_latam_document_number': l10n_latam_document_number,
                                     'numero_liquidacion': numero_liquidacion,
                                     'amount': 0.0})
            index = next((index for (index, d) in enumerate(bank_payment) if d["jorunal_id"] == journal_id.id and name_code_bank == d['name_code_bank']), None)
            bank_payment[index]['amount'] += round(valor_bank, 2)
            if not any(name_code_invoice == e['name_code'] for e in invoices):
                invoices.append({'name_code': name_code_invoice,
                                 'invoice_date': invoice_date,
                                 'l10n_latam_document_number': l10n_latam_document_number,
                                 'local_trade': local_trade,
                                 'sale_shop_id': sale_shop_id,
                                 'electronic_authorization': electronic_authorization,
                                 'amount_without_tax': 0.0,
                                 'amount_total': 0.0})
            index = next((index for (index, d) in enumerate(invoices) if name_code_invoice == d['name_code']), None)
            invoices[index]['amount_total'] += round((valor_comision), 2)
            invoices[index]['amount_without_tax'] += round((valor_comision_sin_iva), 2)

            if have_withholding:
                if not any(l10n_latam_document_number_withholding == e['l10n_latam_document_number'] for e in withholds):
                    withholds.append({'l10n_latam_document_number': l10n_latam_document_number_withholding,
                                      'electronic_authorization': electronic_authorization_withholding,
                                      'base_iva': 0.0,
                                      'percentage_iva': 0.0,
                                      'amount_iva': 0.0,
                                      'base_renta': 0.0,
                                      'percentage_renta': 0.0,
                                      'amount_renta': 0.0,
                                      'withhold_date': date,
                                      'local_trade': local_trade,
                                      'sale_shop_id': sale_shop_id,
                                      'file_id': payment_file.id,
                                      })
                index = next((index for (index, d) in enumerate(withholds) if l10n_latam_document_number_withholding == d['l10n_latam_document_number']), None)
                withholds[index]['base_iva'] += base_iva
                withholds[index]['amount_iva'] += valor_iva
                withholds[index]['base_renta'] += base_renta
                withholds[index]['amount_renta'] += valor_renta

            self.env['account.payment.tc.files.details'].create({'files_id': payment_file.id,
                                                                 'date': date,
                                                                 'bin': bin,
                                                                 'lote': lote,
                                                                 'referencia': vale,
                                                                 'autorizacion': autorizacion,
                                                                 'amount': amount,
                                                                 'amount_net': valor_neto,
                                                                 'amount_pay': amount_pay,
                                                                 'amount_iva': valor_iva,
                                                                 'amount_renta': valor_renta,
                                                                 'amount_commission': valor_comision,
                                                                 'found': found_payment,
                                                                 'local_trade': local_trade,
                                                                 'sale_shop_id': sale_shop_id,
                                                                 'l10n_latam_document_number': l10n_latam_document_number,
                                                                 })

            if not found_payment:
                results.append("No se encontró el pago con autorización: " + autorizacion + ", lote: " + lote + ", recap: " + recap + " y monto: " + str(amount))

            total_comision += round(valor_comision, 2)
            total_iva += round(valor_iva, 2)
            total_renta += round(valor_renta, 2)

        for bank in bank_payment:
            self.env['account.payment.bank.payment'].create({'name_code_bank': bank['name_code_bank'],
                                                             'payment_tc_cab_id': self.account_payment_tc_id.id,
                                                             'journal_id': bank['jorunal_id'],
                                                             'amount': bank['amount'],
                                                             'number_liq': bank['numero_liquidacion'],
                                                             'local_trade': bank['local_trade'],
                                                             'sale_shop_id': bank['sale_shop_id'],
                                                             'file_id': payment_file.id,
                                                             })

        for invoice in invoices:
            self.env['account.payment.tc.invoice'].create({'payment_tc_cab_id': self.account_payment_tc_id.id,
                                                           'amount_total': invoice['amount_total'],
                                                           'name_code': invoice['name_code'],
                                                           'amount_without_tax': invoice['amount_without_tax'],
                                                           'invoice_date': invoice['invoice_date'],
                                                           'l10n_latam_document_number': invoice['l10n_latam_document_number'],
                                                           'electronic_authorization': invoice['electronic_authorization'],
                                                           'file_id': payment_file.id,
                                                           'local_trade': invoice['local_trade'],
                                                           'sale_shop_id': invoice['sale_shop_id'],
                                                           'need_create_invoice': need_create_invoice,
                                                           })

        for withhold in withholds:
            self.account_payment_tc_id.have_withholding = True
            if withhold['l10n_latam_document_number']=='001-002-014731280':
                a = 1
            self.env['account.payment.tc.withhold'].create({'payment_tc_cab_id': self.account_payment_tc_id.id,
                                                            'l10n_latam_document_number': withhold['l10n_latam_document_number'],
                                                            'electronic_authorization': withhold['electronic_authorization'],
                                                            'base_iva': withhold['base_iva'],
                                                            'amount_iva': withhold['amount_iva'],
                                                            'percentage_iva': float(int(round(((withhold['amount_iva'] * 100) / withhold['base_iva']),0))),
                                                            'base_renta': withhold['base_renta'],
                                                            'amount_renta': withhold['amount_renta'],
                                                            'percentage_renta': float(int(round(((withhold['amount_renta'] * 100)/(withhold['base_renta'])),0))),
                                                            'withhold_date': withhold['withhold_date'],
                                                            'file_id': payment_file.id,
                                                            'local_trade': withhold['local_trade'],
                                                            'sale_shop_id':withhold['sale_shop_id'],
                                                            })
        self.account_payment_tc_id.amount_commission = round(total_comision, 2)
        self.account_payment_tc_id.amount_iva = round(total_iva, 2)
        self.account_payment_tc_id.amount_renta = round(total_renta, 2)
        results_str = ""
        if cont_found != 0:
            results_str = "Se encontraron " + str(cont_found) + " pagos"
            results.append(results_str)
        for result in results:
            if results_str == "":
                results_str = result
            else:
                results_str = results_str + "\n"
                results_str = results_str + result
        self.process = True
        self.results = results_str

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment.tc.wizard',
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
            'context':{'default_bank_id': self.bank_id.id}
        }


class AccountPaymentTc(models.Model):
    _inherit='account.payment.tc.det'

    payment_rel_tc_pos_id = fields.Many2one('pos.payment', 'Pago', store=True)
    pos_order_id = fields.Many2one('pos.order', 'Orden de Venta', related='payment_rel_tc_pos_id.pos_order_id', store=True)


class AccountPaymentTcCab(models.Model):
    _inherit = "account.payment.tc.cab"

    def get_lines(self):
        res = super(AccountPaymentTcCab, self).get_lines()
        search_domain = [('payment_method_id.credit_card_information', '=', True)]
        if self.is_range_date:
            search_domain.append(('pos_order_id.date_pos', '>=', self.date_start))
            search_domain.append(('pos_order_id.date_pos', '<=', self.date_end))
        if self.date:
            search_domain.append(('pos_order_id.date_pos', '=', self.date))
        if self.auth_tc:
            search_domain.append(('credit_card_authorization', '=', self.auth_tc))
        if self.lote_tc:
            search_domain.append(('credit_card_lote', '=', self.lote_tc))
        if self.reference_tc:
            search_domain.append(('credit_card_reference', '=', self.reference_tc))
        payments = self.env['pos.payment'].search(search_domain)
        for line in payments:
            # if line.pos_order_id.account_move.printer_id in self.printer_ids:
            if line.id not in self.line_ids.mapped('payment_rel_tc_pos_id').ids:
                self.env['account.payment.tc.det'].create({'payment_cab_id': self.id,
                                                           'payment_rel_tc_pos_id': line.id,
                                                           'payment_date': line.pos_order_id.date_pos,
                                                           'partner_id': line.partner_id.id,
                                                           'currency_id': line.currency_id.id,
                                                           'amount': line.amount,
                                                           'date': line.pos_order_id.date_pos,
                                                           'journal_id': line.payment_method_id.journal_id.id,
                                                           # 'payment_conciliation_tc': line.payment_conciliation_tc.id,
                                                           'is_credit_card': line.payment_method_id.journal_id.credit_card,
                                                           # 'state_conciliation_tc': line.state_conciliation_tc,
                                                           # 'type_card': line.type_card,
                                                           'lote_tc': line.credit_card_lote,
                                                           'reference_tc': line.credit_card_reference,
                                                           'auth_tc': line.credit_card_authorization,
                                                           })

