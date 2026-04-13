# -*- coding: utf-8 -*-#
#############################################################################
#                                                                           #
#Copyright (C) HackSystem, Inc - All Rights Reserved                        #
#Unauthorized copying of this file, via any medium is strictly prohibited   #
#Proprietary and confidential                                               #
#Written by Ing. Harry Alvarez <halvarezg@hacksystem.es>, 2023              #
#                                                                           #
#############################################################################
{
    'name' : 'Ecuadorian Payment TC',
    'version' : '1.0',
    'summary': 'Module that personalizes and improves the processes of Credit Cards, of the Ecuadorian tax model',
    'sequence': 10,
    'description': """
    Module that personalizes and improves the processes of Credit Cards, of the Ecuadorian tax model
    """,
    'category': 'Accounting',
    'author': '',
    'images' : [],
    'depends' : ['base',
                 'ec_account_base',
                 'ec_account_edi',
                 'ec_sri_authorizathions',
                 'ec_withholding',
                 'account_payment',
                 'ec_account_payment'
                 ],
    'data': [
        'security/ir.model.access.csv',
        'security/ec_payment_tc_security.xml',
        'views/account_payment_tc_view.xml',
        'views/account_journal_view.xml',
        'views/account_payment_view.xml',
        'views/res_config_view.xml',
        'wizard/wizard_conciliation_tc_view.xml',
        'wizard/report_differences_by_load_wizard_view.xml',
        'views/res_bank_view.xml',
        'views/account_move_view.xml',
        'views/sale_shop_view.xml',
    ],
    'demo': [
    ],
    'qweb': [
    ],
    'installable': True,
    'license': 'LGPL-3',
}
