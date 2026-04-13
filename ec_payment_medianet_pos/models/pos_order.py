##############################################################################
#
#    Copyright (C) 2022-Present Speeduplight (<https://speeduplight.com>)
#
##############################################################################
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero
from odoo.tools import float_is_zero, float_compare, float_round

class PosOrder(models.Model):
    _inherit = "pos.order"

    @api.model
    def get_info_medianet(self, orders):
        data_medianet = []
        pos_order = False
        if len(orders) != 0:
            order = orders[0]
            pos_order = self.env['pos.order'].search([('id', '=', order['id'])])
            if len(pos_order) != 0:
                pos_order = pos_order[0]
        if pos_order:
            for payment in pos_order.payment_ids:
                if payment.payment_method_id.payment_medianet:
                    if not payment.trama_medianet:
                        return {'data_medianet': False}
                    medianet_id = self.env['ec.payment.medianet'].search([])
                    sesson_id = pos_order.session_id
                    line_medinanet = False
                    for line in medianet_id.location_ids:
                        if line.warehouse_id.id == sesson_id.config_id.picking_type_id.warehouse_id.id:
                            line_medinanet = line
                    if not line_medinanet:
                        raise ValidationError(_('No se ha configurado la ubicación de Medianet para la tienda'))
                        return False
                    trama = payment.trama_medianet
                    medianet_code = 'MANUAL'
                    if trama[237:239] == '01':
                        medianet_code = 'MANUAL'
                    if trama[237:239] == '02':
                        medianet_code = 'BANDA'
                    if trama[237:239] == '03':
                        medianet_code = 'CHIP'
                    if trama[237:239] == '04':
                        medianet_code = 'FALLBACK MANUAL (CHIP)'
                    if trama[237:239] == '05':
                        medianet_code = 'FALLBACK BANDA (CHIP)'
                    if trama[237:239] == '07':
                        medianet_code = 'CTL CHIP'
                    medianet_type_red = 'MEDIANET'
                    if trama[8:10] == '01':
                        medianet_type_red = 'DATAFAST'
                    if trama[8:10] == '02':
                        medianet_type_red = 'MEDIANET'
                    if trama[8:10] == '03':
                        medianet_type_red = 'AUSTRO'
                    tax_ids = payment.pos_order_id.lines[0].tax_ids
                    medianet_tax_base_diff_0_name = ''
                    medianet_tax_base_diff_0 = '0.00'
                    medianet_tax_base_0 = '0.00'
                    medianet_tax_diff_0_name = ''
                    medianet_tax_diff_0 = '0.00'
                    medianet_interest_amount = '0.00'
                    medianet_amount_subtotal = '0.00'
                    interes = 0
                    if payment.with_interest:
                        medianet_interest_amount = trama[87:99]
                        decimal = trama[87:99][-2:]
                        entero = trama[87:99][:10]
                        medianet_interest_amount = entero + '.' + decimal
                        interes = float(medianet_interest_amount)
                        medianet_interest_amount = '%.2f' % (interes)
                    total = payment.amount + interes
                    have_tax_0 = False
                    have_tax_diff_0 = False
                    tax_id = False
                    for tax in tax_ids:
                        if tax.amount != 0:
                            medianet_tax_base_diff_0_name = str(int(tax.amount))
                            medianet_tax_diff_0_name = tax.description
                            have_tax_diff_0 = True
                            tax_id = tax
                        else:
                            tax_id = tax
                            have_tax_0 = True
                    if have_tax_0:
                        medianet_tax_base_0 = '%.2f' % (float_round(payment.amount,2))
                    if have_tax_diff_0:
                        medianet_tax_diff_0 = '%.2f' % (float_round(payment.amount,2) - (float_round(payment.amount,2) / (1 +(tax_id.amount / 100))))
                        medianet_tax_base_diff_0 = '%.2f' % (float_round(payment.amount,2) / (1 +(tax_id.amount / 100)))
                    data_medianet.append({
                        'payment_id': payment.id,
                        'medianet_code': medianet_code,
                        'medianet_reference': payment.credit_card_reference,
                        'medianet_authorization': payment.credit_card_authorization,
                        'medianet_lote': payment.credit_card_lote,
                        'medianet_tid': trama[64:72],
                        'medianet_mid_base': line_medinanet.mid,
                        'medianet_mid': trama[72:87],
                        'medianet_number_card': trama[398:423],
                        'medianet_name_card': trama[212:237],
                        'medianet_type_red': medianet_type_red,
                        'medianet_date': trama[56:58]+'/'+trama[54:56]+'/'+trama[50:54],
                        'medianet_time': trama[44:46]+':'+trama[46:48]+':'+trama[48:50],
                        'medianet_aid_label': trama[291:311],
                        'medianet_aid': trama[311:331],
                        'medianet_amount_subtotal': '%.2f' % (pos_order.amount_total),
                        'medianet_amount_total': '%.2f' % (total),
                        'medianet_tax_base_diff_0_name': medianet_tax_base_diff_0_name,
                        'medianet_tax_base_diff_0': medianet_tax_base_diff_0,
                        'medianet_tax_base_0': medianet_tax_base_0,
                        'medianet_tax_diff_0_name': medianet_tax_diff_0_name,
                        'medianet_tax_diff_0': medianet_tax_diff_0,
                        'medianet_have_deferred': payment.have_deferred,
                        'medianet_month_interest': payment.month_interest,
                        'medianet_month_interest_free': payment.month_interest_free,
                        'medianet_with_interest': payment.with_interest,
                        'medianet_interest_amount': medianet_interest_amount,

                    })
        return {'data_medianet': data_medianet}


    def _payment_fields(self, order, ui_paymentline):
        res = super(PosOrder, self)._payment_fields(order, ui_paymentline)
        payment_method = self.env['pos.payment.method'].browse(ui_paymentline['payment_method_id'])
        if payment_method.payment_medianet == True:
            trama_medianet = ui_paymentline.get('trama_medianet')
            medianet_type_red = False
            if trama_medianet:
                medianet_type_red = 'medianet'
                if trama_medianet[8:10] == '01':
                    medianet_type_red = 'datafast'
                if trama_medianet[8:10] == '02':
                    medianet_type_red = 'medianet'
                if trama_medianet[8:10] == '03':
                    medianet_type_red = 'austro'
            res.update({'trama_medianet': ui_paymentline.get('trama_medianet'),
                        'have_deferred': ui_paymentline.get('have_deferred'),
                        'month_interest': ui_paymentline.get('month_interest'),
                        'month_interest_free': ui_paymentline.get('month_interest_free'),
                        'with_interest': ui_paymentline.get('with_interest'),
                        'type_net': medianet_type_red,
                        })
        return res

