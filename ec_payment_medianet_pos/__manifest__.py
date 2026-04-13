# -*- coding: utf-8 -*-#
#############################################################################
#                                                                           #
#Copyright (C) HackSystem, Inc - All Rights Reserved                        #
#Unauthorized copying of this file, via any medium is strictly prohibited   #
#Proprietary and confidential                                               #
#Written by Ing. Harry Alvarez <halvarezg@hacksystem.tech>, 2024            #
#                                                                           #
#############################################################################
{
	'name' : 'EC PAYMENT MEDIANET POS',
	'version' : '1.0',
	'author' : '',
	'category' : 'Account',
	'description' : u"""Integración de pagos con Medianet POS en Odoo""",
	'images' : [
	],
	'depends' : [
		'base',
		'account',
		'point_of_sale',
		'ec_payment_tc_pos',
		'ec_tools'
	],
	'data': [
		'security/ir.model.access.csv',
		'report/session_pinpad.xml',
		'report/cancel_medianet.xml',
		'views/pos_config.xml',

	],
	'assets': {
		'point_of_sale.assets': [
			'ec_payment_medianet_pos/static/src/js/Popups/Medianet.js',
			'ec_payment_medianet_pos/static/src/js/PaymentScreen.js',
			'ec_payment_medianet_pos/static/src/xml/pos.xml',
			'ec_payment_medianet_pos/static/src/xml/order_receipt.xml',
		],
	},
	'qweb' : [
	],
	'demo': [
	],
	'test': [
	],
	'installable': True,
	'auto_install': False,
	'license': 'LGPL-3',
}
