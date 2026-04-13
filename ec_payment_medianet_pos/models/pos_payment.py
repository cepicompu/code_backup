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


class PosPaymentCancelMedianet(models.TransientModel):
    _name = 'pos.payment.cancel.medianet'

    def cancel_payment_medianet(self):
        return

class PosPayment(models.Model):
    _inherit = 'pos.payment'


    date_cancel = fields.Date(string='Fecha de Anulación', readonly=True)
    datetime_cancel = fields.Datetime(string='Fecha de Anulación', readonly=True)
    credit_card_authorization_cancel = fields.Char(string="Autorización Cancelacion")
    credit_card_lote_cancel = fields.Char(string="Lote Cancelacion")
    credit_card_reference_cancel = fields.Char(string="Referencia Cancelacion")
    trama_medianet = fields.Char(string="Trama Medianet")
    is_medianet = fields.Boolean(string="Es Medianet", related='payment_method_id.payment_medianet', store=True)
    have_deferred = fields.Boolean(string="Tiene Diferido")
    month_interest = fields.Char(string="Meses")
    month_interest_free = fields.Char(string="Meses")
    with_interest = fields.Boolean(string="Con Interes")
    is_canceled = fields.Boolean(string="Anulado", default=False)

    # def cancel_payment_medianet(self):
    #     return {
    #         'name': _('Anular Pago Medianet'),
    #         'type': 'ir.actions.act_window',
    #         'res_model': 'pos.payment.cancel.medianet',
    #         'view_mode': 'form',
    #         'view_type': 'form',
    #         'target': 'new',
    #     }

    def print_cancel_payment(self):
        return self.env.ref('ec_payment_medianet_pos.ec_action_report_cancel_medianet_pos').report_action(self)


    def reverse_payment_medianet(self):
        if not self.payment_method_id.payment_medianet:
            raise UserError(_('Solo se puede anular cuando sea pago mediante Medianet'))
        medianet_id = self.env['ec.payment.medianet'].search([])
        trama = 'PP'
        tipo_transaccion = '04'
        tipo_red = '1'  # 1: Datafast, 2: Medianet
        diferido = '00'
        plazo_diferido = '00'
        meses_gracia = '00'
        filler = ' '
        monto_order = ("{:.2f}".format(self.amount)).replace('.', '')
        monto = str(monto_order).zfill(12)
        monto_subtotal_order = self.amount - (self.amount * 0.15)
        monto_subtotal_order = ("{:.2f}".format(monto_subtotal_order)).replace('.', '')
        monto_subtotal = str(monto_subtotal_order).zfill(12)
        monto_iva_order = ("{:.2f}".format((self.amount * 0.15))).replace('.', '')
        monto_iva = str(monto_iva_order).zfill(12)
        monto_no_iva_order = 0.00
        monto_no_iva_order = ("{:.2f}".format(monto_no_iva_order)).replace('.', '')
        monto_no_iva = str(monto_no_iva_order).zfill(12)
        filler_todo = '                                    '
        credit_card_reference = self.credit_card_reference
        import pytz
        from datetime import datetime
        user_tz = pytz.timezone('America/Guayaquil')
        now = pytz.utc.localize(datetime.now()).astimezone(user_tz)
        fecha = str(now.year) + str(now.month).zfill(2) + str(now.day).zfill(2)
        hora = str(now.hour).zfill(2) + str(now.minute).zfill(2) + str(now.second).zfill(2)
        credit_card_authorization = self.credit_card_authorization
        mid = False
        filler_todo2 = '   '
        tid = False
        ip = False
        line_medinanet = False
        for line in medianet_id.location_ids:
            if line.warehouse_id.id == self.session_id.config_id.picking_type_id.warehouse_id.id:
                line_medinanet = line
        if not line_medinanet:
            raise ValidationError(_('No se ha configurado la ubicación de Medianet para la tienda'))
            return False
        tid = line_medinanet.tid
        mid = line_medinanet.mid
        ip = line_medinanet.ip
        if not tid:
            raise UserError(_('No puede anular el pago sin un TID asignado.'))
        if not mid:
            raise UserError(_('No puede anular el pagosin un TID asignado.'))
        if not ip:
            raise UserError(_('No puede anular el pago sin una IP asignada.'))
        name = 'CAJA1'.ljust(15, '0')
        filler_todo3 = '                    '
        trama = trama + tipo_transaccion + tipo_red + diferido + plazo_diferido + meses_gracia + filler + monto + monto_subtotal + monto_no_iva + monto_iva + filler_todo + credit_card_reference + hora + fecha + credit_card_authorization + mid + filler_todo2 + tid + name + filler_todo3
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
        # result = [0,0,0,b'DATA RECEIVED:0202PP00020000 AUTORIZACION OK. 0002660000182057072024080587679920414672000000888155   000000000450                                                                                                                 MASTERCARD/MAES          07                                                    MASTERCARD          A0000000041010      80                                   AE570D8F4A5CE7F00000008001E00053005400XXXX4502         2509216A18C24F7EAD9EB9B3062158A34D8E70BEF536267EB9FEE40D7FEB2D574ECE                           C6F22F1F02DD276927BF83128F256363',0,0,0]
        if len(result) > 5:
            if "DATA RECEIVED" in result[3].decode():
                result = result[3].decode().split(":")[1]
                respuesta = result[12:32]
                if 'OK' in respuesta:
                    referencia = result[32:38]
                    lote = result[38:44]
                    autorizacion = result[58:64]
                    self.date_cancel = fields.Datetime.now()
                    self.credit_card_authorization_cancel = autorizacion
                    self.credit_card_lote_cancel = lote
                    self.credit_card_reference_cancel = referencia
                    self.is_canceled = True

                    # creo transacion
                    self.env['ec.medianet.transaction'].create({'name': 'Transaccion Medianet',
                                                                'trama_send': trama,
                                                                'trama_result': result,
                                                                # 'date': now,
                                                                'pos_order_id': self.pos_order_id.id,
                                                                'payment_medianet_location_id': line_medinanet.id,
                                                                'payment_medianet_id': medianet_id.id,
                                                                'lote': lote,
                                                                'referencia': referencia,
                                                                'autorizacion': autorizacion,
                                                                })
                    return
                else:
                    raise ValidationError(_('Error al anular el pago'))
            else:
                raise ValidationError(_('Error al anular el pago'))
        else:
            raise ValidationError(_('Error al anular el pago'))


    def cancel_payment_medianet(self):
        if not self.payment_method_id.payment_medianet:
            raise UserError(_('Solo se puede anular cuando sea pago mediante Medianet'))
        medianet_id = self.env['ec.payment.medianet'].search([])
        trama = 'PP'
        tipo_transaccion = '03'
        tipo_red = '1'  # 1: Datafast, 2: Medianet
        diferido = '00'
        plazo_diferido = '00'
        meses_gracia = '00'
        filler = ' '
        monto_order = ("{:.2f}".format(self.amount)).replace('.', '')
        monto = str(monto_order).zfill(12)
        monto_subtotal_order = self.amount - (self.amount * 0.15)
        monto_subtotal_order = ("{:.2f}".format(monto_subtotal_order)).replace('.', '')
        monto_subtotal = str(monto_subtotal_order).zfill(12)
        monto_iva_order = ("{:.2f}".format((self.amount * 0.15))).replace('.', '')
        monto_iva = str(monto_iva_order).zfill(12)
        monto_no_iva_order = 0.00
        monto_no_iva_order = ("{:.2f}".format(monto_no_iva_order)).replace('.', '')
        monto_no_iva = str(monto_no_iva_order).zfill(12)
        filler_todo = '                                    '
        credit_card_reference = self.credit_card_reference
        import pytz
        from datetime import datetime
        user_tz = pytz.timezone('America/Guayaquil')
        now = pytz.utc.localize(datetime.now()).astimezone(user_tz)
        fecha = str(now.year) + str(now.month).zfill(2) + str(now.day).zfill(2)
        hora = str(now.hour).zfill(2) + str(now.minute).zfill(2) + str(now.second).zfill(2)
        credit_card_authorization = self.credit_card_authorization
        mid = False
        filler_todo2 = '   '
        tid = False
        ip = False
        line_medinanet = False
        for line in medianet_id.location_ids:
            if line.warehouse_id.id == self.session_id.config_id.picking_type_id.warehouse_id.id:
                line_medinanet = line
        if not line_medinanet:
            raise ValidationError(_('No se ha configurado la ubicación de Medianet para la tienda'))
            return False
        tid = line_medinanet.tid
        mid = line_medinanet.mid
        ip = line_medinanet.ip
        if not tid:
            raise UserError(_('No puede anular el pago sin un TID asignado.'))
        if not mid:
            raise UserError(_('No puede anular el pagosin un TID asignado.'))
        if not ip:
            raise UserError(_('No puede anular el pago sin una IP asignada.'))
        name = 'CAJA1'.ljust(15, '0')
        filler_todo3 = '                    '
        trama = trama + tipo_transaccion + tipo_red + diferido + plazo_diferido + meses_gracia + filler + monto + monto_subtotal + monto_no_iva + monto_iva + filler_todo + credit_card_reference + hora + fecha + credit_card_authorization + mid + filler_todo2 + tid + name + filler_todo3
        logging.info("TRAMA MEDIANET ANULACION A ENVIAR")
        logging.info(trama)
        JAR_PATH = 'java/Medianet.jar'
        JAVA_CMD = 'java'
        java_path = os.path.join(os.path.dirname(__file__), JAR_PATH)
        command = [JAVA_CMD,
                   '-XX:MaxMetaspaceSize=256M',
                   '-Xms512m',
                   '-Xmx1024m',
                   '-jar', java_path,  # Cambia -cp por -jar
                   trama, line_medinanet.ip, str(medianet_id.port)]
        ret = False
        timeout = 60
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,  # Lanza excepción si hay error
                text=True,
                timeout=timeout
            )
            ret = result.stdout.strip()
        except subprocess.TimeoutExpired:
            logging.error("Timeout: No se recibió respuesta dentro de %s segundos.", timeout)
            raise ValidationError(_('No se recibió respuesta y no se pudo anular'))
        _logger.info("RESPUESTA ANULACION DATAFAST")
        _logger.info(ret)
        result = ret
        # result = [0,0,0,b'DATA RECEIVED:0202PP00020000 AUTORIZACION OK. 0002660000182057072024080587679920414672000000888155   000000000450                                                                                                                 MASTERCARD/MAES          07                                                    MASTERCARD          A0000000041010      80                                   AE570D8F4A5CE7F00000008001E00053005400XXXX4502         2509216A18C24F7EAD9EB9B3062158A34D8E70BEF536267EB9FEE40D7FEB2D574ECE                           C6F22F1F02DD276927BF83128F256363',0,0,0]
        if result[6:8] == '20':
            raise ValidationError(_(result[8:38].strip()))
        else:
            respuesta = result[12:32]
            if 'OK' in respuesta:
                referencia = result[32:38]
                lote = result[38:44]
                autorizacion = result[58:64]
                self.date_cancel = fields.Datetime.now()
                self.credit_card_authorization_cancel = autorizacion
                self.credit_card_lote_cancel = lote

                transactions = self.env['ec.medianet.transaction'].search([('lote', '=', lote),
                                                                           ('payment_medianet_location_id', '=', line_medinanet.id),])
                if len(transactions) > 0:
                    transaction = transactions[-1]
                    referencia = int(transaction.referencia) + 1
                    referencia = str(referencia).zfill(6)

                self.credit_card_reference_cancel = referencia
                self.is_canceled = True

                # creo transacion
                self.env['ec.medianet.transaction'].create({'name': 'Transaccion Medianet',
                                                            'trama_send': trama,
                                                            'trama_result': result,
                                                            # 'date': now,
                                                            'pos_order_id': self.pos_order_id.id,
                                                            'payment_medianet_location_id': line_medinanet.id,
                                                            'payment_medianet_id': medianet_id.id,
                                                            'lote': lote,
                                                            'referencia': referencia,
                                                            'autorizacion': autorizacion,
                                                            })
                return
            else:
                raise ValidationError(_('Error al anular el pago'))
