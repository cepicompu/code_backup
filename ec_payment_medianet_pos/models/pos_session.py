##############################################################################
#
#    Copyright (C) 2022-Present Speeduplight (<https://speeduplight.com>)
#
##############################################################################
import subprocess
import os
import logging
_logger = logging.getLogger(__name__)
from odoo.exceptions import UserError, ValidationError
from odoo import api, Command, fields, models, _

class PosSession(models.Model):
    _inherit = 'pos.session'

    have_close_session_medianet = fields.Boolean(string='Cerrar Sesión Medianet', default=False)


    def report_session_pinpad(self):
        return self.env.ref('ec_payment_medianet_pos.ec_action_report_session_pinpad').report_action(None)

    def _pos_ui_models_to_load(self):
        result = super()._pos_ui_models_to_load()
        result.append('res.bank')
        return result

    def _loader_params_res_bank(self):
        return {
            'search_params': {
                'domain': [],
                'fields': ['id', 'name'],
            },
        }

    def _get_pos_ui_res_bank(self, params):
        interes = []
        bank_ids = self.env['res.bank'].search([])
        for bank_id in bank_ids:
            if bank_id.is_medianet:
                if bank_id.have_deferred:
                    for line in bank_id.line_interests_ids:
                        if line.actived:
                            interes.append({
                                'id': line.id,
                                'month_interest': line.month_interest,
                                'with_interest': line.with_interest,
                                'month_interest_free': line.month_interest_free if line.month_interest_free else 0,
                            })
        return interes

    def _loader_params_pos_payment_method(self):
        result = super()._loader_params_pos_payment_method()
        result['search_params']['fields'].extend(['payment_medianet'])
        return result


    def close_session_medianet(self):
        if self.have_close_session_medianet:
            raise UserError(_('Ya se ha cerrado la sesión medianet.'))
        medianet_id = self.env['ec.payment.medianet'].search([])
        mid = medianet_id.location_ids[0].mid
        tid = False
        for location in medianet_id.location_ids:
            if location.warehouse_id == self.config_id.picking_type_id.warehouse_id:
                tid = location.tid
                mid = location.mid
                ip = location.ip
        if not tid:
            raise UserError(_('No puede cerrar la sesión medianet sin un TID asignado.'))
        if not mid:
            raise UserError(_('No puede cerrar la sesión medianet sin un MID asignado.'))
        trama = "PC                        "+mid+"   "+tid+"                       CAJA100000000002"
        JAR_PATH = 'java/Medianet.jar'
        JAVA_CMD = 'java'
        java_path = os.path.join(os.path.dirname(__file__), JAR_PATH)
        command = [JAVA_CMD, '-Xms256m', '-Xmx512m', '-jar', java_path, trama, ip, medianet_id.port]
        p = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        ret = []
        while p.poll() is None:
            line = p.stdout.readline()
            ret.append(line)
        stdout, stderr = p.communicate()
        _logger.info("RESPUESTA DATAFAST")
        _logger.info(ret)
        result = ret
        self.have_close_session_medianet = True


