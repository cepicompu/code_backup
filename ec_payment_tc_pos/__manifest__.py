##############################################################################
#
#    Copyright (C) 2022-Present Speeduplight (<https://speeduplight.com>)
#
##############################################################################
{
    "name": "Pago Tarjeta de Crédito POS",
    "version": "16.0.1",
    "category": "Point of Sale",
    'license': 'OPL-1',
    "author": "HackSystem",
    "description": """""",
    "website": "https://hacksystem.tech",
    "depends": ['base', 'point_of_sale', 'ec_payment_tc', 'ec_pos'],
    "data": [
        'views/pos_config.xml',
        'views/account_payment_tc_view.xml'
    ],
    'assets': {
        'point_of_sale.assets': [
            'ec_payment_tc_pos/static/src/js/Popups/CreditCardPopUp.js',
            'ec_payment_tc_pos/static/src/js/*.js',
            'ec_payment_tc_pos/static/src/xml/pos.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
