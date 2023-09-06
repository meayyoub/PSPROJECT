{
    "name": "ALL Custom UPDATES",
    "version": "1.0",
    "category": "Sales",
    "author": "Med AYYOUB",
    "depends": ["base", "sale", "account"],  # Add any other dependencies
    "data": [
        "security/ir.model.access.csv",
        "views/sale_order_inherit.xml",
        "views/invoice_cheque_report.xml",
        ## "views/assets.xml",
    ],
    "installable": True,
    "auto_install": False,
}
