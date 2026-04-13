#-*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api
from datetime import date, datetime, time, timedelta

class EcReportSessionPinpad(models.AbstractModel):
    _name = 'report.ec_payment_medianet_pos.ec_report_session_pinpad'

    @api.model
    def _get_report_values(self, docids, data):
        payments = []
        session_id = self.env['pos.session'].browse(docids)
        payments_data = self.env['pos.payment'].search([('session_id', '=', session_id.id)])
        total = 0
        type_red = []
        for payment in payments_data:
            if payment.is_medianet:
                payments.append(payment)
                grupo_tarjeta = 'Desconocido'
                if payment.trama_medianet:
                    grupo_tarjeta = payment.trama_medianet[212:237].strip()
                total += payment.amount
                type_net = payment.type_net.upper() if payment.type_net else 'Desconocido'
                if not any(type_net == e['type_net'] for e in type_red):
                    type_red.append({'type_net': type_net,
                                     'grupo_tarjeta': [],
                                     'total': 0.00})
                index_red = next((index_red for (index_red, d) in enumerate(type_red) if d['type_net'] == type_net), None)
                type_red[index_red]['total'] += round(payment.amount,2)
                if not any(grupo_tarjeta == e['grupo_tarjeta'] for e in type_red[index_red]['grupo_tarjeta']):
                    type_red[index_red]['grupo_tarjeta'].append({'grupo_tarjeta': grupo_tarjeta,
                                                                 'payments': [],
                                                                 'total': 0.00})
                index_grupo_tarjeta = next((index_grupo_tarjeta for (index_grupo_tarjeta, d) in enumerate(type_red[index_red]['grupo_tarjeta']) if d['grupo_tarjeta'] == grupo_tarjeta), None)
                type_red[index_red]['grupo_tarjeta'][index_grupo_tarjeta]['total'] += round(payment.amount,2)
                type_red[index_red]['grupo_tarjeta'][index_grupo_tarjeta]['payments'].append(payment)
        for red in type_red:
            red['total'] = round(red['total'],2)
        return {
            'docs': self.env['pos.session'].browse(docids),
            'payments': payments,
            'total': round(total,2),
            'type_red': type_red,
            'start_at': session_id.start_at - timedelta(hours=5),
            'stop_at': session_id.stop_at - timedelta(hours=5) if session_id.stop_at else False,
        }