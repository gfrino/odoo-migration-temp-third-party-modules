from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from odoo import api, fields, models
from odoo.tools import SQL

from .kpi_order import CHANNELS

PERIODS = ("today", "yesterday", "week", "month", "last_month", "year", "custom")


class LittleInkaKpiDashboard(models.AbstractModel):
    """Numbers for the «Little Inka KPI» dashboard (client action tw_littleinka_kpi.dashboard)."""

    _name = "tw.littleinka.kpi.dashboard"
    _description = "Little Inka KPI: dashboard"

    # ------------------------------------------------------------------ period

    def _tz(self):
        name = self.env.context.get("tz") or self.env.user.tz or "UTC"
        try:
            return ZoneInfo(name)
        except Exception:  # noqa: BLE001 - unknown time zone name: fall back to UTC
            return ZoneInfo("UTC")

    def _range(self, params):
        """(local first day, local last day) of the requested period, both included."""
        today = datetime.now(self._tz()).date()
        period = params.get("period") if params.get("period") in PERIODS else "today"
        if period == "yesterday":
            start = end = today - timedelta(days=1)
        elif period == "week":
            start, end = today - timedelta(days=today.weekday()), today
        elif period == "month":
            start, end = today.replace(day=1), today
        elif period == "last_month":
            end = today.replace(day=1) - timedelta(days=1)
            start = end.replace(day=1)
        elif period == "year":
            start, end = today.replace(month=1, day=1), today
        elif period == "custom":
            start = fields.Date.to_date(params.get("date_from")) or today
            end = fields.Date.to_date(params.get("date_to")) or start
            start, end = min(start, end), max(start, end)
            end = min(end, start + timedelta(days=731))
        else:
            start = end = today
        return period, start, end

    def _utc(self, day):
        """Local midnight of a day as naive UTC datetime (the format of the Datetime columns)."""
        local = datetime.combine(day, time.min, tzinfo=self._tz())
        return local.astimezone(timezone.utc).replace(tzinfo=None)

    def _bounds(self, start, end):
        return self._utc(start), self._utc(end + timedelta(days=1))

    def _where(self, alias, start, end, sede_id):
        date_from, date_to = self._bounds(start, end)
        clauses = [
            SQL("%s.date >= %s", SQL.identifier(alias), date_from),
            SQL("%s.date < %s", SQL.identifier(alias), date_to),
            SQL("(%s.company_id IS NULL OR %s.company_id = ANY(%s))", SQL.identifier(alias), SQL.identifier(alias), self.env.companies.ids),
        ]
        if sede_id:
            clauses.append(SQL("%s.sede_id = %s", SQL.identifier(alias), int(sede_id)))
        return SQL(" AND ").join(clauses)

    def _rows(self, query):
        self.env.cr.execute(query)
        return self.env.cr.dictfetchall()

    def _check(self):
        self.env["tw.littleinka.kpi.report"].check_access("read")
        self.env["tw.littleinka.kpi.report.line"].check_access("read")

    # ------------------------------------------------------------------ data

    def _totals(self, start, end, sede_id):
        rows = self._rows(SQL(
            """SELECT sales_type, channel, COALESCE(sum(amount_total), 0) AS amount,
                      COALESCE(sum(order_count), 0) AS orders, COALESCE(sum(item_count), 0) AS items
                 FROM tw_littleinka_kpi_report r WHERE %s GROUP BY sales_type, channel""",
            self._where("r", start, end, sede_id),
        ))
        totals = {"amount": 0.0, "amount_online": 0.0, "amount_pos": 0.0, "orders": 0, "orders_online": 0, "orders_pos": 0, "items": 0.0}
        channels = {key: {"key": key, "amount": 0.0, "orders": 0} for key, _label in CHANNELS}
        for row in rows:
            suffix = "online" if row["sales_type"] == "online" else "pos"
            totals["amount"] += row["amount"]
            totals["orders"] += row["orders"]
            totals["items"] += row["items"]
            totals[f"amount_{suffix}"] += row["amount"]
            totals[f"orders_{suffix}"] += row["orders"]
            if row["channel"] in channels:
                channels[row["channel"]]["amount"] += row["amount"]
                channels[row["channel"]]["orders"] += row["orders"]
        totals["avg_ticket"] = totals["amount"] / totals["orders"] if totals["orders"] else 0.0
        labels = dict(CHANNELS)
        return totals, [dict(ch, label=labels[ch["key"]]) for ch in channels.values()]

    def _families(self, start, end, sede_id):
        rows = self._rows(SQL(
            """SELECT family_id, sales_type, COALESCE(sum(quantity), 0) AS qty, COALESCE(sum(amount_total), 0) AS amount
                 FROM tw_littleinka_kpi_report_line r WHERE %s GROUP BY family_id, sales_type""",
            self._where("r", start, end, sede_id),
        ))
        families = self.env["tw.littleinka.kpi.family"].search([])
        result = {
            family.id: {"id": family.id, "name": family.name, "color": family.color,
                        "qty": 0.0, "qty_online": 0.0, "qty_pos": 0.0, "amount": 0.0, "amount_online": 0.0, "amount_pos": 0.0}
            for family in families
        }
        unassigned = {"id": False, "name": self.env._("Da assegnare"), "color": 0,
                      "qty": 0.0, "qty_online": 0.0, "qty_pos": 0.0, "amount": 0.0, "amount_online": 0.0, "amount_pos": 0.0}
        for row in rows:
            target = result.get(row["family_id"], unassigned)
            suffix = "online" if row["sales_type"] == "online" else "pos"
            target["qty"] += row["qty"]
            target["amount"] += row["amount"]
            target[f"qty_{suffix}"] += row["qty"]
            target[f"amount_{suffix}"] += row["amount"]
        out = list(result.values())
        if unassigned["qty"] or unassigned["amount"]:
            out.append(unassigned)
        return out

    def _by_sede(self, start, end):
        rows = self._rows(SQL(
            """SELECT sede_id, sales_type, COALESCE(sum(amount_total), 0) AS amount, COALESCE(sum(order_count), 0) AS orders
                 FROM tw_littleinka_kpi_report r WHERE %s GROUP BY sede_id, sales_type""",
            self._where("r", start, end, False),
        ))
        sedi = {s.id: {"id": s.id, "name": s.name, "amount_online": 0.0, "amount_pos": 0.0, "orders_online": 0, "orders_pos": 0}
                for s in self.env["tw.littleinka.kpi.sede"].search([])}
        other = {"id": False, "name": self.env._("Casse senza sede"), "amount_online": 0.0, "amount_pos": 0.0, "orders_online": 0, "orders_pos": 0}
        for row in rows:
            target = sedi.get(row["sede_id"], other)
            suffix = "online" if row["sales_type"] == "online" else "pos"
            target[f"amount_{suffix}"] += row["amount"]
            target[f"orders_{suffix}"] += row["orders"]
        out = list(sedi.values())
        if other["amount_pos"] or other["orders_pos"]:
            out.append(other)
        for row in out:
            row["amount"] = row["amount_online"] + row["amount_pos"]
        return out

    @api.model
    def get_data(self, params=None):
        self._check()
        params = params or {}
        self.env["tw.littleinka.kpi.category"].sudo()._refresh_pos()
        period, start, end = self._range(params)
        sede_id = params.get("sede_id") or False
        prev_end = start - timedelta(days=1)
        prev_start = prev_end - (end - start)
        totals, channels = self._totals(start, end, sede_id)
        prev_totals, _channels = self._totals(prev_start, prev_end, sede_id)
        families = self._families(start, end, sede_id)
        prev_families = {f["id"]: f for f in self._families(prev_start, prev_end, sede_id)}
        for family in families:
            family["prev_qty"] = prev_families.get(family["id"], {}).get("qty", 0.0)
        date_from, date_to = self._bounds(start, end)
        currency = self.env.company.currency_id
        return {
            "period": period,
            "date_from": fields.Date.to_string(start),
            "date_to": fields.Date.to_string(end),
            "utc_from": fields.Datetime.to_string(date_from),
            "utc_to": fields.Datetime.to_string(date_to),
            "sede_id": sede_id,
            "sedi": [{"id": s.id, "name": s.name} for s in self.env["tw.littleinka.kpi.sede"].search([])],
            "currency": {"symbol": currency.symbol, "position": currency.position, "digits": currency.decimal_places},
            "totals": totals,
            "prev_totals": prev_totals,
            "channels": channels,
            "families": families,
            "by_sede": self._by_sede(start, end) if not sede_id else [],
            "unassigned_categories": self.env["tw.littleinka.kpi.category"].search_count([("family_id", "=", False)]),
            "is_manager": self.env.user.has_group("tw_littleinka_kpi.group_kpi_manager"),
        }

    @api.model
    def get_family_detail(self, params=None, family_id=False):
        """Details of one family (or of the products without family) for the selected period and sede."""
        self._check()
        params = params or {}
        _period, start, end = self._range(params)
        sede_id = params.get("sede_id") or False
        where = self._where("r", start, end, sede_id)
        family = SQL("r.family_id = %s", int(family_id)) if family_id else SQL("r.family_id IS NULL")
        sql_qty = SQL("COALESCE(sum(r.quantity) FILTER (WHERE r.sales_type = 'online'), 0) AS qty_online, "
                      "COALESCE(sum(r.quantity) FILTER (WHERE r.sales_type = 'pos'), 0) AS qty_pos, "
                      "COALESCE(sum(r.amount_total), 0) AS amount")
        products = self._rows(SQL(
            "SELECT r.product_name AS name, %s FROM tw_littleinka_kpi_report_line r WHERE %s AND %s "
            "GROUP BY r.product_name HAVING COALESCE(sum(r.extra_quantity), 0) = 0 "
            "ORDER BY sum(r.quantity) DESC NULLS LAST, r.product_name LIMIT 40",
            sql_qty, where, family,
        ))
        # Additions (extra topping, extra protein…): sold with a piece, never counted as one.
        extras = self._rows(SQL(
            "SELECT r.product_name AS name, "
            "COALESCE(sum(r.extra_quantity) FILTER (WHERE r.sales_type = 'online'), 0) AS qty_online, "
            "COALESCE(sum(r.extra_quantity) FILTER (WHERE r.sales_type = 'pos'), 0) AS qty_pos, "
            "COALESCE(sum(r.amount_total), 0) AS amount "
            "FROM tw_littleinka_kpi_report_line r WHERE %s AND %s "
            "GROUP BY r.product_name HAVING COALESCE(sum(r.extra_quantity), 0) <> 0 "
            "ORDER BY sum(r.extra_quantity) DESC, r.product_name LIMIT 40",
            where, family,
        ))
        sedi = self._rows(SQL(
            "SELECT r.sede_id AS id, %s FROM tw_littleinka_kpi_report_line r WHERE %s AND %s GROUP BY r.sede_id",
            sql_qty, where, family,
        ))
        names = {s.id: s.name for s in self.env["tw.littleinka.kpi.sede"].with_context(active_test=False).search([])}
        for row in sedi:
            row["name"] = names.get(row["id"]) or self.env._("Casse senza sede")
        sedi.sort(key=lambda row: -(row["qty_online"] + row["qty_pos"]))
        channels = self._rows(SQL(
            "SELECT r.channel AS key, COALESCE(sum(r.quantity), 0) AS qty FROM tw_littleinka_kpi_report_line r "
            "WHERE %s AND %s GROUP BY r.channel",
            where, family,
        ))
        labels = dict(CHANNELS)
        for row in channels:
            row["label"] = labels.get(row["key"], row["key"])
        tz = self.env.context.get("tz") or self.env.user.tz or "UTC"
        days = self._rows(SQL(
            "SELECT to_char(date_trunc('day', (r.date AT TIME ZONE 'UTC') AT TIME ZONE %s), 'YYYY-MM-DD') AS day, %s "
            "FROM tw_littleinka_kpi_report_line r WHERE %s AND %s GROUP BY 1 ORDER BY 1",
            tz, sql_qty, where, family,
        ))
        record = self.env["tw.littleinka.kpi.family"].browse(int(family_id)) if family_id else None
        return {
            "family": {"id": family_id or False, "name": record.name if record else self.env._("Da assegnare")},
            "products": products,
            "extras": extras,
            "sedi": sedi,
            "channels": sorted(channels, key=lambda row: -row["qty"]),
            "days": days,
        }
