# -*- coding: utf-8 -*-
import time

from odoo import models, fields, registry, api
import odoo.addons.decimal_precision as dp
from odoo.tools.translate import _
from odoo.exceptions import RedirectWarning, UserError, ValidationError, Warning
from odoo.tools import float_is_zero, float_compare, float_round
import logging
from odoo.addons.smile_amount_in_letters.tools.misc import split_integer_and_decimal
from num2words import num2words
from odoo.addons.smile_amount_in_letters.tools.misc import format_money_to_text
_logger = logging.getLogger(__name__)
import subprocess
import os

STATES = {'draft': [('readonly', False),]}

class EcPaymentMedianetBankInterests(models.Model):
    _name = 'ec.payment.medianet.bank.interests'

    bank_id = fields.Many2one('res.bank', string='Medio de Pago Medianet')
    with_interest = fields.Boolean(string='Con Intereses?')
    month_interest = fields.Selection([('3', '3 Meses'),
                                       ('6', '6 Meses'),
                                       ('9', '9 Meses'),
                                       ('12', '12 Meses'),
                                       ('24', '24 Meses')], string='Meses')
    month_interest_free = fields.Integer(string='Meses de Gracia')
    actived = fields.Boolean(string='Activo', default=False)

class ResBank(models.Model):
    _inherit = 'res.bank'

    is_medianet = fields.Boolean(string='Es Medianet?')
    have_deferred = fields.Boolean(string='Tiene Diferido?')
    line_interests_ids = fields.One2many('ec.payment.medianet.bank.interests', 'bank_id', string='Intereses')

class EcPaymentMedianetLocation(models.Model):
    _name = 'ec.payment.medianet.location'

    ec_payment_medianet_id = fields.Many2one('ec.payment.medianet', string='Medio de Pago Medianet')
    warehouse_id = fields.Many2one('stock.warehouse', string='Almacén', required=True)
    ip = fields.Char(string='IP', required=True)
    mid = fields.Char(string='MID', required=True)
    tid = fields.Char(string='TID', required=True)


class EcPaymentMedianet(models.Model):
    _name = 'ec.payment.medianet'

    name = fields.Char(string='Nombre', required=True)
    port = fields.Char(string='Puerto', required=True)
    location_ids = fields.Many2many('ec.payment.medianet.location', string='Ubicaciones')
    bank_id = fields.Many2one('res.bank', string='Banco Adquiriente', required=False)

class EcMedianetTransaction(models.Model):
    _name = 'ec.medianet.transaction'

    name = fields.Char(string='Nombre')
    trama_send = fields.Char(string='Trama')
    trama_result = fields.Char(string='Resultado')
    date = fields.Datetime(string='Fecha')
    pos_order_id = fields.Many2one('pos.order', string='Pedido')
    pos_payment_id = fields.Many2one('pos.payment', string='Pago')
    payment_medianet_location_id = fields.Many2one('ec.payment.medianet.location', string='Ubicación')
    payment_medianet_id = fields.Many2one('ec.payment.medianet', string='Medio de Pago Medianet')
    lote = fields.Char(string='Lote')
    referencia = fields.Char(string='Referencia')
    autorizacion = fields.Char(string='Autorización')
    type = fields.Selection([('compra_corriente', 'Compra Corriente'),
                             ('compra_diferido', 'Compra Diferdios'),
                             ('anulacion','Anulacion'),
                             ('reverso','Reverso')], string='Tipo')

    @api.model
    def send_trama_medianet(self, order, interes=False):
        interes_id = False
        if interes:
            if int(interes) != 0:
                interes_id = self.env['ec.payment.medianet.bank.interests'].browse(int(interes))
        medianet_id = self.env['ec.payment.medianet'].search([])
        sesson_id = self.env['pos.session'].browse(order['pos_session_id'])
        line_medinanet = False
        for line in medianet_id.location_ids:
            if line.warehouse_id.id == sesson_id.config_id.picking_type_id.warehouse_id.id:
                line_medinanet = line
        if not line_medinanet:
            raise ValidationError(_('No se ha configurado la ubicación de Medianet para la tienda'))
            return False
        trama = 'PP'
        tipo_transaccion = '01'
        if interes_id:
            tipo_transaccion = '02'
        tipo_red = '2' # 1: Datafast, 2: Medianet
        diferido = '00'
        if interes_id:
            if interes_id.with_interest:
                diferido = '01'
            else:
                diferido = '04'
        plazo_diferido = '00'
        if interes_id:
            plazo_diferido = interes_id.month_interest.zfill(2)
        meses_gracia = '00'
        if interes_id:
            if interes_id.month_interest_free:
                mgracia = interes_id.month_interest_free
                meses_gracia = mgracia.zfill(2)
        filler = ' '
        monto_order = ("{:.2f}".format(float_round(order['amount_total'],2))).replace('.', '')
        monto = str(monto_order).zfill(12)
        monto_subtotal_order = float_round(order['amount_total'],2) - float_round(order['amount_tax'],2)
        monto_subtotal_order = ("{:.2f}".format(float_round(monto_subtotal_order,2))).replace('.', '')
        monto_subtotal = str(monto_subtotal_order).zfill(12)
        monto_iva_order = ("{:.2f}".format(float_round(order['amount_tax'],2))).replace('.', '')
        monto_iva = str(monto_iva_order).zfill(12)
        monto_no_iva_order = 0.00
        monto_no_iva_order = ("{:.2f}".format(float_round(monto_no_iva_order,2))).replace('.', '')
        monto_no_iva = str(monto_no_iva_order).zfill(12)
        filler_todo = '                                          '
        import pytz
        from datetime import datetime
        user_tz = pytz.timezone('America/Guayaquil')
        now = pytz.utc.localize(datetime.now()).astimezone(user_tz)
        fecha = str(now.year)+str(now.month).zfill(2)+str(now.day).zfill(2)
        hora = str(now.hour).zfill(2)+str(now.minute).zfill(2)+str(now.second).zfill(2)
        filler_todo1 = '      '
        mid = line_medinanet.mid
        filler_todo2 = '   '
        tid = line_medinanet.tid
        name = 'CAJA1'.ljust(15, '0')
        filler_todo3 = '                    '
        trama = trama + tipo_transaccion + tipo_red + diferido + plazo_diferido + meses_gracia + filler + monto + monto_subtotal +  monto_no_iva + monto_iva + filler_todo +  hora + fecha + filler_todo1 + mid + filler_todo2 + tid + name + filler_todo3
        logging.info("TRAMA MEDIANET A ENVIAR")
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
            trama_reverso = 'PP'
            trama_reverso = trama_reverso + '04' + tipo_red + diferido + plazo_diferido + meses_gracia + filler + monto + monto_subtotal + monto_no_iva + monto_iva + filler_todo + hora + fecha + filler_todo1 + mid + filler_todo2 + tid + name + filler_todo3
            logging.info("TRAMA MEDIANET REVERSO")
            logging.info(trama_reverso)
            command = [JAVA_CMD,
                       '-XX:MaxMetaspaceSize=256M',
                       '-Xms512m',
                       '-Xmx1024m',
                       '-jar', java_path,  # Cambia -cp por -jar
                       trama_reverso, line_medinanet.ip, str(medianet_id.port)]
            try:
                timeout = 20
                result = subprocess.run(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,  # Lanza excepción si hay error
                    text=True,
                    timeout=timeout
                )
                return {'state': False, 'mensaje': 'No se recibió respuesta y se realizó un reverso de la transacción'}
            except subprocess.TimeoutExpired:
                logging.error("Timeout: No se recibió respuesta dentro de %s segundos.", timeout)
                return {'state': False, 'mensaje': 'No se recibió respuesta y no se pudo realizar un reverso de la transacción'}
            except subprocess.CalledProcessError as e:
                return {'state': False, 'mensaje': 'No se recibió respuesta y no se pudo realizar un reverso de la transacción'}
        except subprocess.CalledProcessError as e:
            # Capturar ambas salidas (stdout y stderr) incluso si están vacías
            logging.error("Error al ejecutar Java (exit code %d): %s", e.returncode,e.stderr.strip() or "No se proporcionó salida de error.")
            logging.info("Salida estándar (stdout): %s", e.stdout.strip() or "No se proporcionó salida estándar.")
        except Exception as e:
            logging.error("Excepción inesperada: %s", str(e))
        _logger.info("RESPUESTA DATAFAST")
        _logger.info(ret)
        result = ret
        # result = "PP011000000 000000000100000000000087000000000000000000000013                                          16240320240516      000000885145   DD043001CAJA10000000000                    \n', b'Entra a POS!\n', b'DATA SENDING 00d4PP011000000 000000000100000000000087000000000000000000000013                                          16240320240516      000000885145   DD043001CAJA10000000000                    E29CCB494F0DA9F387B9FD15D5912BFE\n', b'DATA RECEIVED:0202PP000200AUTORIZACION OK.    00000800000216240320240516121568DD043001000000885145                                                                                                                                VISA ELECT/DEB           07PAYWAVE/VISA                                        VISA DEBITO         A0000000031010      80                                   78D08895FB9132610000000000000047539500XXXX6442         2511B8D651C704F1839EFCD9D97D08597C52D5F1DE5DB15D67C0B853BF81DC725EAE                           9456312138CEFE52D6001CBB39DBBAD1"
        # transaccion exitosa
        # result = "0202PP00020000 AUTORIZACION OK. 0001630000102057072024062873311320414672000000888155                                                                                               004003                           MASTERCARD/MAES          01                                                                                                                                                               55366030XXXX6027         2610094FB1D63AADB9AE990BAA5C589D6555D537DC98EC60FFD07C96D76C78D0C9CF                           9159FE7611C89A8C7B56555DD26C18E6"
        # result = "0202PP00020000 AUTORIZACION OK. 0002680000182057072024080587681120414672000000888155   000000000000                                                                                004004                           MASTERCARD/MAES          07                                                    MASTERCARD          A0000000041010      80                                   7715C6778F2441E30000008001E00053005400XXXX4502         2509216A18C24F7EAD9EB9B3062158A34D8E70BEF536267EB9FEE40D7FEB2D574ECE                           D50A85731410178C59909B4CE1962053"
        # error
        # result = "PP202020    MID O TID INVALIDO        000022                    20413126000000841801                                                                                                                                                                                                                                                                                                                                                                                                                                                  7879E631C900541559B1A53BD6C506E7"
        if result[6:8] == '20':
            return {'state': False,'mensaje': result[8:38].strip()}
        else:
            respuesta = result[12:32]
            if 'OK' in respuesta:
                referencia = result[32:38]
                lote = result[38:44]
                autorizacion = result[58:64]
                # creo transacion
                self.create({'name': 'Transaccion Medianet',
                             'trama_send': trama,
                             'trama_result': result,
                             # 'date': now,
                             # 'pos_order_id': order['id'],
                             'payment_medianet_location_id': line_medinanet.id,
                             'payment_medianet_id': medianet_id.id,
                             'lote': lote,
                             'referencia': referencia,
                             'autorizacion': autorizacion,
                             })
                return {'state': True,
                        'data': {'referencia': referencia,
                                 'lote': lote,
                                 'autorizacion': autorizacion,
                                 'trama': result,
                                 'have_deferred': True if interes_id else False,
                                 'month_interest': interes_id.month_interest if interes_id else False,
                                 'month_interest_free': interes_id.month_interest_free if interes_id else False,
                                 'with_interest': interes_id.with_interest if interes_id else False
                                 }}
            else:
                return {'state': False, 'mensaje': respuesta}






