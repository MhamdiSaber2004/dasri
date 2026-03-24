from odoo import fields, models, tools


class DasriKpiReport(models.Model):
    _name = 'dasri.kpi.report'
    _description = 'DASRI KPI Report'
    _auto = False
    _rec_name = 'period_month'
    _order = 'period_month desc, partner_id'

    period_month = fields.Date('Mois', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Etablissement', readonly=True)
    contract_id = fields.Many2one('dasri.contract', string='Contrat', readonly=True)
    mission_count = fields.Integer('Missions', readonly=True)
    trips_count = fields.Integer('Passages', readonly=True)
    qty_kg_total = fields.Float('Tonnage (KG)', readonly=True)
    revenue_estimated = fields.Float('CA estime', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    row_number() OVER () AS id,
                    date_trunc('month', b.date)::date AS period_month,
                    b.partner_id AS partner_id,
                    b.contract_id AS contract_id,
                    COUNT(DISTINCT b.mission_id) AS mission_count,
                    COUNT(b.id) AS trips_count,
                    COALESCE(SUM(b.qty_kg), 0.0) AS qty_kg_total,
                    COALESCE(SUM(
                        CASE c.pricing_type
                            WHEN 'weight' THEN COALESCE(b.qty_kg, 0.0) * COALESCE(c.price_kg, 0.0)
                            WHEN 'trip' THEN COALESCE(c.price_trip, 0.0)
                            WHEN 'mixed' THEN
                                (COALESCE(b.qty_kg, 0.0) * COALESCE(c.price_kg, 0.0)) + COALESCE(c.price_trip, 0.0)
                            ELSE 0.0
                        END
                    ), 0.0) AS revenue_estimated
                FROM dasri_bordereau b
                LEFT JOIN dasri_contract c ON c.id = b.contract_id
                WHERE b.state IN ('validated', 'archived')
                GROUP BY
                    date_trunc('month', b.date)::date,
                    b.partner_id,
                    b.contract_id
            )
        """)
