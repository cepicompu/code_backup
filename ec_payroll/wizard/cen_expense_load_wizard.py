# -*- coding: utf-8 -*-
#############################################################################
#                                                                           #
# Copyright (C) CEN-ERP, Inc - All Rights Reserved                          #
# Unauthorized copying of this file, via any medium is strictly prohibited  #
# Proprietary and confidential                                              #
# Written by Ing. Darwin Vélez <dvelez@cenecuador.edu.ec>, 2023 - 2024      #
#                                                                           #
#############################################################################
import logging
from datetime import timedelta
from functools import partial
import json
import os
import tempfile
import unicodedata
import xlrd
import requests
import psycopg2
import pytz

from odoo import api, fields, models, tools, _
from odoo.tools import float_is_zero
from odoo.exceptions import UserError
from datetime import date, datetime, timedelta
from odoo.http import request
from odoo.osv.expression import AND
import base64
try:
    from odoo.tools.misc import xlsxwriter
except ImportError:
    import xlsxwriter

_logger = logging.getLogger(__name__)


class CenExpenseLoadWizard(models.TransientModel):
    '''
    Asistente para Cargar egresos
    '''

    _name = 'cen.expense.load.wizard'
    _description = 'Asistente para Cargar egresos'

    name = fields.Char(string=u'Nama', required=False)
    file = fields.Binary("Archivo Excel Para Importar",
                         help=u"Seleccionar el archivo que contien las facturas, debe ser un arvhivo excel.",
                         required=False, filters="*.xml,*.xlsx")


    def action_import(self):
        filename, extension_iess = os.path.splitext(self.name)
        contador = 1
        datas = base64.decodestring(self.file).decode(encoding="latin1").split('\n')
        for data in datas:
            linea = data.split(';')
            if len(linea) != 1 and len(linea) != 0:
                if len(linea)==9:
                    if linea[0]=="TRABAJADOR":
                        contador += 1
                        pass
                    else:
                        if not linea[4] and not linea[5] and not linea[6] and not linea[7]:
                            contador += 1
                        else:
                            if len(linea[3]) == 0:
                                raise UserError(_("El campo FECHA esta en blanco en la fila %s, por favor revise.") % contador)
                            fecha = datetime.strptime(linea[3], "%d/%m/%Y").date()
                            if len(linea[0]) == 0:
                                raise UserError(_("El campo TRABAJADOR esta en blanco en la fila %s, por favor revise.") % contador)
                            nombre = str(linea[0]).lstrip().rstrip()
                            cedula = str(linea[2]).lstrip().rstrip()
                            if len(linea[2])==9:

                                cedula = str(linea[2]).zfill(10).lstrip().rstrip()
                            horas_50 = 0
                            horas_100 = 0
                            horas_nocturnas = 0
                            horas_ordinarias = 0
                            if len(linea[8]) == 0:
                                raise UserError(_("El campo DETALLE esta en blanco en la fila %s, por favor revise.") % contador)
                            observation = str(linea[8])
                            if linea[4]:
                                horas_50 = float(linea[4])
                            if linea[5]:
                                horas_100 = float(linea[5])
                            if linea[6]:
                                horas_nocturnas = float(linea[6])
                            if linea[7]:
                                horas_ordinarias = float(linea[7])
                            employee_id = self.env['hr.employee'].search([('identification_id', '=', cedula),("active","=",True)],limit=1)
                            if len(employee_id) != 0:
                            #    raise UserError(
                            #        _(u"La cédula %s del empleado %s en la fila %s no existe, por favor revise que este escrita correctamente.") % (
                            #        cedula, nombre, contador))
                            #else:
                                contract = self.env['hr.contract'].search([('employee_id', '=', employee_id.id)])

                                request_object=self.env["request.overtime"]
                                dct={"employee_id":employee_id.id,
                                     "date_from":fecha,
                                     "date_to":fecha,
                                     "reason":observation,
                                     "contract_id":contract[0].id,
                                     "cant_hours_suple":horas_50,
                                     "cant_hours_ext":horas_100,
                                     "cant_hours_night":horas_nocturnas}
                                id_over=request_object.create(dct)
                                id_over.action_request()
                                id_over.action_done()
                                contador += 1
                else:

                    if len(linea[0])==0:
                        raise UserError(_("El campo FECHA esta en blanco en la fila %s, por favor revise.") % contador)
                    if len(linea[2])==0:
                        raise UserError(_("El campo CEDULA esta en blanco en la fila %s, por favor revise.") % contador)
                    if len(linea[3])==0:
                        raise UserError(_("El campo REGLA esta en blanco en la fila %s, por favor revise.") % contador)
                    if len(linea[4])==0:
                        raise UserError(_("El campo VALOR esta en blanco en la fila %s, por favor revise.") % contador)

                    scheduled = self.env['hr.scheduled.transaction']

                    fecha = datetime.strptime(linea[0], "%d/%m/%Y").date()
                    cedula = str(linea[2]).lstrip().rstrip()
                    regla = str(linea[3]).upper()
                    valor = round(float(linea[4]),2)
                    observation = str(linea[6])
                    employee_id = self.env['hr.employee'].search([('identification_id', '=', cedula)])
                    if len(employee_id) == 0:
                        raise UserError(_(u"La cédula %s del empleado %s en la fila %s no existe, por favor revise que la cédula del empleado sea la correcta.") % (cedula,linea[1],contador))
                    transaction = self.env['hr.scheduled.transaction.category'].search([('name', '=', regla)])
                    if len(transaction) == 0:
                        raise UserError(_("La regla %s en la fila %s no existe, por favor revise.") % (regla,contador))
                    contador += 1
                    scheduled.create({'employee_id': employee_id[0].id,
                                      'category_transaction_id': transaction[0].id,
                                      'date': fecha,
                                      'amount': valor,
                                      'observation': observation,
                                      'name': str(transaction[0].name) + " " + str(employee_id[0].name),
                                      'code': str(transaction[0].code) + "/" + str(fields.Datetime.now())+ "/" + str(cedula),
                                      })


        return {'type': 'ir.actions.client',
                'tag': 'reload', }
