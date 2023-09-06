from odoo import models, fields, api, _
from odoo.exceptions import AccessError,ValidationError

class AccountMove(models.Model):
    _inherit = "account.move"
    warning_msg = fields.Char()
    cheque_ids = fields.One2many('sale_custom.cheque', 'invoice_id', string='Chèques')


    # @api.model
    # def _check_balanced(self):
    #     # Custom logic here if needed
    #     return True

    @api.constrains("partner_id")
    def check_unpaid_invoices(self):
        for move in self:
            if (
                move.state == "draft"
                and move.move_type == "out_invoice"
                and move.partner_id
            ):
                unpaid_invoices = self.env["account.move"].search(
                    [
                        ("partner_id", "=", move.partner_id.id),
                        ("state", "=", "posted"),
                        ("move_type", "=", "out_invoice"),
                        ("amount_residual", ">", 0.0),
                        # ("id", "!=", move.id),  # Exclude the current invoice
                    ]
                )
                if unpaid_invoices:
                    self.warning_msg = _("Attention ce client a des factures impayées.")
                else:
                    self.warning_msg = "NON"
                # move.message_post(body=warning_msg)

    def action_post(self):
        result = super(AccountMove, self).action_post()

        if self.warning_msg != "NON":
            #print(self.warning_msg)
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Factures impayées!"),
                    "type": "warning",
                    "message": self.warning_msg,
                    "sticky": True,
                    "next": {
                        "type": "ir.actions.act_window",
                        "res_model": "account.move",
                        "res_id": self.id,
                        "views": [(False, "form")],
                    },
                },
            }

class SaleOrderInherit(models.Model):
    _inherit = "sale.order"
    vendeur = fields.Many2one('sale_custom.vendeur',required=True, string='Vendeur')#,domain=lambda self: self._get_partner_domain())


    @api.model
    def fields_view_get(self, view_id=None, view_type="form", toolbar=False, submenu=False):
        res = super(SaleOrderInherit, self).fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu
        )
    
        if view_type == "form":
            if self.env.user.name == "Caisse Combani":
                domain = [("magasin", "=", "combani")]
                res["fields"]["vendeur"]["domain"] = domain
            if self.env.user.name == "Caisse Mamoudzou":
                domain = [("magasin", "=", "mamoudzou")]
                res["fields"]["vendeur"]["domain"] = domain
            if self.env.user.name == "Caisse Petite Terre":
                domain = [("magasin", "=", "labattoir")]
                res["fields"]["vendeur"]["domain"] = domain

        return res

    def create_invoice_from_quotation(self):
        #print(self.env.user.id.name)
        self.action_confirm()
        invoice = self._create_invoices()
        invoice.action_post()
        return {
            "name": "Invoice",
            "view_mode": "form",
            "res_model": "account.move",
            "type": "ir.actions.act_window",
            "res_id": invoice.id,
        }




class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # Add the field to store the standard price of the product
    product_standard_price = fields.Float(
        related='product_id.list_price',
        string='Standard Price',
        readonly=True,
        store=True,
    )

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.price_unit = self.product_standard_price
class CustomAccountPayment(models.Model):
    _inherit = 'account.payment'

    amount_company_currency_signed = fields.Monetary(
        currency_field='company_currency_id', compute='_compute_amount_company_currency_signed', store=True)
    @api.depends("amount_total_signed", "payment_type")
    def _compute_amount_company_currency_signed(self):
        for payment in self:
            liquidity_lines = payment._seek_for_lines()[0]
            payment.amount_company_currency_signed = sum(liquidity_lines.mapped("balance"))
    amount_signed = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_amount_signed",
        tracking=True,
        help="Negative value of amount field if payment_type is outbound",
        store=True
    )
    @api.depends("amount", "payment_type")
    def _compute_amount_signed(self):
        for payment in self:
            if payment.payment_type == "outbound":
                payment.amount_signed = -payment.amount
            else:
                payment.amount_signed = payment.amount

class Vendeur(models.Model):
    _name = 'sale_custom.vendeur'
    _description = 'Vendeur'
    _rec_name = 'name'

    name = fields.Char(compute='_compute_name', store="True", string="Vendeur")
    name_or = fields.Char(string='Nom')
    magasin = fields.Selection([("admin", "Admin"),("mamoudzou", "Mamoudzou"),
                                ("combani", "Combani"),
                                ("labattoir", "Labattoir")]
                               ,string='Magasin')
    order_ids = fields.One2many('sale.order', 'vendeur', string='Devis')

    @api.depends("name_or", "magasin")
    def _compute_name(self):
        for record in self:
            record.name = ""
            record.name = (
                str(record.magasin)
                + " "
                + str(record.name_or)
            )

    @api.model
    def _check_group(self):
        """Check if the current user is an administrator."""
        if not self.env.user.has_group("base.group_erp_manager"):
            raise AccessError("Seuls les administrateurs peuvent ajouter ou modifier des vendeurs.")
    
    
    @api.model
    def create(self, vals):
        self._check_group()
        return super(Vendeur, self).create(vals)
    
    
    def write(self, vals):
        self._check_group()
        return super(Vendeur, self).write(vals)

    def unlink(self):
        self._check_group()
        return super(Vendeur, self).unlink()


class Cheque(models.Model):
    _name = 'sale_custom.cheque'
    _description = 'Gestion des Chèques'

    number = fields.Char(string='Numéro de Chèque')
    date = fields.Date(string='Date de Chèque')
    state = fields.Selection([
        ('issued', 'À encaisser'),
        ('cleared', 'Encaissé'),
        ('returned', 'Retourné')
    ], string='État', default='issued')
    amount = fields.Float(string='Montant')
    invoice_id = fields.Many2one('account.move', string='Facture')
    client = fields.Char(related='invoice_id.partner_id.name')

    
    @api.model
    def _check_group(self):
        """Check if the current user is an administrator."""
        if not self.env.user.has_group("base.group_erp_manager"):
            raise AccessError("Seuls les administrateurs peuvent ajouter ou modifier des cheques.")
    
    
    @api.model    
    def write(self, vals):
        self._check_group()
        return super(Cheque, self).write(vals)

    def unlink(self):
        self._check_group()
        return super(Cheque, self).unlink()

    @api.constrains('date')
    def _check_date_range(self):
        for record in self:
            if record.date.day != 1 and record.date.day != 10:
                print(record.date.day)
                raise ValidationError("Le jour du mois doit être soit 1 ou 10.")


