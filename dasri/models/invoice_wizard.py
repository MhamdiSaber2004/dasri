from datetime import date
import calendar

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class DasriInvoiceWizard(models.TransientModel):
    _name = 'dasri.invoice.wizard'
    _description = 'Wizard Facturation Mensuelle DASRI'

    contract_id = fields.Many2one(
        'dasri.contract',
        string='Contrat',
        required=True,
        domain=[('state', '=', 'active')],
    )
    month = fields.Selection(
        [(str(i), calendar.month_name[i]) for i in range(1, 13)],
        string='Mois',
        required=True,
        default=lambda self: str(date.today().month),
    )
    year = fields.Integer(string='Annee', required=True, default=lambda self: date.today().year)

    def action_generate_invoice(self):
        self.ensure_one()
        contract = self.contract_id
        if contract.state != 'active':
            raise ValidationError("Le contrat doit etre actif pour facturer.")
        period_start, period_end = self._get_period_dates()
        self._check_contract_dates(contract, period_start, period_end)
        bordereaux = self._get_bordereaux(contract, period_start, period_end)
        if not bordereaux:
            raise ValidationError("Aucun bordereau a facturer pour cette periode.")
        invoice = self._create_invoice(contract, bordereaux, period_start, period_end)
        bordereaux.write({'invoice_id': invoice.id})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': invoice.id,
        }

    def _get_period_dates(self):
        month = int(self.month)
        year = int(self.year)
        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, 1), date(year, month, last_day)

    def _check_contract_dates(self, contract, period_start, period_end):
        if contract.date_start and contract.date_start > period_end:
            raise ValidationError("La periode est avant la date de debut du contrat.")
        if contract.date_end and contract.date_end < period_start:
            raise ValidationError("La periode est apres la date de fin du contrat.")

    def _get_bordereaux(self, contract, period_start, period_end):
        bordereaux = self.env['dasri.bordereau'].search([
            ('contract_id', '=', contract.id),
            ('date', '>=', period_start),
            ('date', '<=', period_end),
            ('state', 'in', ['validated', 'archived']),
            ('invoice_id', '=', False),
        ])
        # Backward compatibility for old records that do not carry contract_id.
        unlinked = self.env['dasri.bordereau'].search([
            ('partner_id', '=', contract.partner_id.id),
            ('date', '>=', period_start),
            ('date', '<=', period_end),
            ('state', 'in', ['validated', 'archived']),
            ('invoice_id', '=', False),
            ('contract_id', '=', False),
        ])
        if unlinked:
            unlinked = unlinked.filtered(
                lambda b: (
                    (not contract.date_start or contract.date_start <= b.date)
                    and (not contract.date_end or contract.date_end >= b.date)
                )
            )
        return bordereaux | unlinked

    def _get_service_product(self):
        product = self.env['product.product'].search([('name', '=', 'جمع dasri')], limit=1)
        if product:
            return product
        tmpl = self.env['product.template'].create({
            'name': 'جمع dasri',
            'type': 'service',
        })
        return tmpl.product_variant_id

    def _prepare_invoice_lines(self, contract, bordereaux, product):
        qty_total = sum(bordereaux.mapped('qty_kg'))
        trips_total = len(bordereaux)
        lines = []
        total_amount = 0.0

        if contract.pricing_type in ('weight', 'mixed'):
            if qty_total:
                amount = qty_total * contract.price_kg
                total_amount += amount
                lines.append((0, 0, {
                    'product_id': product.id,
                    'name': 'Collecte DASRI (KG)',
                    'quantity': qty_total,
                    'price_unit': contract.price_kg,
                }))
        if contract.pricing_type in ('trip', 'mixed'):
            if trips_total:
                amount = trips_total * contract.price_trip
                total_amount += amount
                lines.append((0, 0, {
                    'product_id': product.id,
                    'name': 'Collecte DASRI (Passage)',
                    'quantity': trips_total,
                    'price_unit': contract.price_trip,
                }))
        if contract.monthly_min and total_amount < contract.monthly_min:
            lines.append((0, 0, {
                'product_id': product.id,
                'name': 'Minimum mensuel',
                'quantity': 1,
                'price_unit': contract.monthly_min - total_amount,
            }))
        if not lines:
            raise ValidationError("Aucune ligne de facturation valide pour cette periode.")
        return lines

    def _create_invoice(self, contract, bordereaux, period_start, period_end):
        product = self._get_service_product()
        lines = self._prepare_invoice_lines(contract, bordereaux, product)
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': contract.partner_id.id,
            'invoice_date': period_end,
            'invoice_origin': f'{contract.name} {period_start.strftime("%Y-%m")}',
            'invoice_line_ids': lines,
        })
        return invoice
