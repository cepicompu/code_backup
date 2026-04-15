{
    'name': 'Reportes Ministerio de Trabajo',
    'version': '16.0.1.1.0',
    'summary': 'Reportes legales para el Ministerio de Trabajo (Décimo Tercero, Décimo Cuarto)',
    'category': 'Human Resources/Payroll',
    'depends': ['ec_payroll', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/payroll_report_views.xml',
        'wizard/wizard_ministry_report_view.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
