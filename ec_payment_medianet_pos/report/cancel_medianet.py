#-*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api
from datetime import date, datetime, time, timedelta

class EcReportCancelMedianet_pos(models.AbstractModel):
    _name = 'report.ec_payment_medianet_pos.ec_report_cancel_medianet_pos'

    @api.model
    def _get_report_values(self, docids, data):
        payment = self.env['pos.payment'].browse(docids)
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

        return {
            'docs': self.env['pos.payment'].browse(docids),
            'company': self.env.company,
            'medianet_code': medianet_code,
            'medianet_reference': payment.credit_card_reference,
            'medianet_number_card': trama[398:423],
            'medianet_name_card': trama[212:237],
            'medianet_type_red': medianet_type_red,
        }