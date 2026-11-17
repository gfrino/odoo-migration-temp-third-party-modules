import { Component, onWillStart, proxy, useProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useSetupAction } from "@web/search/action_hook";
import { standardActionServiceProps } from "@web/webclient/actions/action_plugin";

const MODEL = "tw.littleinka.kpi.dashboard";

/**
 * Little Inka KPI: one screen, made for the phone first.
 * Pieces sold per family (Poké, Sushi, Bevande, Dessert…) split online / cassa,
 * revenue and orders, channels and sedi. Every card opens its details.
 */
export class LittleInkaKpiDashboard extends Component {
    static template = "tw_littleinka_kpi.Dashboard";
    // Same path as the ir.actions.client record: a reload of /odoo/littleinka-kpi?period=… gets its params.
    static path = "littleinka-kpi";
    props = useProps({ ...standardActionServiceProps });

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.periods = [
            { key: "today", label: _t("Oggi") },
            { key: "yesterday", label: _t("Ieri") },
            { key: "week", label: _t("Settimana") },
            { key: "month", label: _t("Mese") },
            { key: "last_month", label: _t("Mese scorso") },
            { key: "year", label: _t("Anno") },
            { key: "custom", label: _t("Date…") },
        ];
        // State saved in the URL and in the breadcrumb: flat strings only (see saveState).
        const saved = this.props.state || this.props.action.params || {};
        const family = saved.family === "none" ? false : parseInt(saved.family) || null;
        this.state = proxy({
            params: {
                period: this.periods.some((p) => p.key === saved.period) ? saved.period : "today",
                sede_ids: String(saved.sede || "")
                    .split(",")
                    .map((id) => parseInt(id))
                    .filter((id) => id > 0),
                date_from: saved.from || false,
                date_to: saved.to || false,
            },
            data: null,
            detail: null,
            detailFamily: family,
            sediOpen: false,
            loading: true,
        });
        // Coming back from a drill down (breadcrumb) restores period, sede and open family.
        useSetupAction({ getLocalState: () => this.flatState() });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        this.state.data = await this.orm.call(MODEL, "get_data", [this.state.params]);
        if (this.state.detailFamily !== null) {
            await this.loadDetail(this.state.detailFamily);
        }
        this.state.loading = false;
        this.saveState();
    }

    /** Period, sedi and open family survive reloads and the breadcrumb (they go in the URL, as strings). */
    saveState() {
        this.props.updateActionState?.(this.flatState());
    }

    flatState() {
        const { period, sede_ids, date_from, date_to } = this.state.params;
        const family = this.state.detailFamily;
        const state = { period };
        if (sede_ids.length) {
            state.sede = sede_ids.join(",");
        }
        if (period === "custom") {
            state.from = date_from || "";
            state.to = date_to || "";
        }
        if (family !== null) {
            state.family = family === false ? "none" : String(family);
        }
        return state;
    }

    async loadDetail(familyId) {
        this.state.detail = await this.orm.call(MODEL, "get_family_detail", [this.state.params, familyId]);
    }

    // ---------------------------------------------------------------- filters

    setPeriod(key) {
        const params = this.state.params;
        params.period = key;
        if (key === "custom" && !params.date_from) {
            const today = luxon.DateTime.now().toISODate();
            params.date_from = today;
            params.date_to = today;
        }
        this.load();
    }

    onDate(field, ev) {
        if (ev.target.value) {
            this.state.params[field] = ev.target.value;
            this.load();
        }
    }

    isSedeSelected(sedeId) {
        return this.state.params.sede_ids.includes(sedeId);
    }

    /** Tick or untick one sede in the filter: the numbers follow at once, the list stays open. */
    toggleSede(sedeId) {
        const selected = this.state.params.sede_ids;
        this.state.params.sede_ids = selected.includes(sedeId)
            ? selected.filter((id) => id !== sedeId)
            : [...selected, sedeId];
        this.load();
    }

    allSedi() {
        this.state.params.sede_ids = [];
        this.load();
    }

    /** A row of «Per sede»: show that sede alone. */
    pickSede(sedeId) {
        if (!sedeId) {
            return;
        }
        this.state.params.sede_ids = [sedeId];
        this.state.sediOpen = false;
        this.load();
    }

    async openFamily(family) {
        this.state.detailFamily = family.id;
        await this.loadDetail(family.id);
        this.saveState();
        window.scrollTo?.(0, 0);
    }

    closeFamily() {
        this.state.detailFamily = null;
        this.state.detail = null;
        this.saveState();
    }

    // ---------------------------------------------------------------- formatting

    money(value) {
        const currency = this.state.data?.currency || {};
        const digits = Math.abs(value) >= 1000 ? 0 : 2;
        const amount = new Intl.NumberFormat("de-CH", {
            minimumFractionDigits: digits,
            maximumFractionDigits: digits,
        }).format(value || 0);
        return currency.position === "before" ? `${currency.symbol} ${amount}` : `${amount} ${currency.symbol || ""}`;
    }

    qty(value) {
        return new Intl.NumberFormat("de-CH", { maximumFractionDigits: 1 }).format(value || 0);
    }

    pct(part, total) {
        return total ? Math.round((part / total) * 100) : 0;
    }

    delta(now, before) {
        if (!before) {
            return null;
        }
        const value = Math.round(((now - before) / Math.abs(before)) * 100);
        return { value, up: value >= 0, label: `${value >= 0 ? "▲" : "▼"} ${Math.abs(value)}%` };
    }

    /** What the percentages compare with, in words that fit one line on a phone. */
    get compareLabel() {
        const labels = {
            today: _t("su ieri"),
            yesterday: _t("sul giorno prima"),
            week: _t("sulla settimana prima"),
            month: _t("sul mese prima"),
            last_month: _t("sul mese prima"),
            year: _t("sull'anno prima"),
        };
        return labels[this.state.params.period] || _t("sul periodo prima");
    }

    get periodLabel() {
        const data = this.state.data;
        if (!data) {
            return "";
        }
        const fmt = (d) => luxon.DateTime.fromISO(d).toFormat("dd.MM.yyyy");
        return data.date_from === data.date_to ? fmt(data.date_from) : `${fmt(data.date_from)} – ${fmt(data.date_to)}`;
    }

    get sedeName() {
        const selected = this.state.params.sede_ids;
        const names = (this.state.data?.sedi || []).filter((s) => selected.includes(s.id)).map((s) => s.name);
        if (!names.length) {
            return _t("Tutte le sedi");
        }
        return names.length <= 2 ? names.join(", ") : _t("%s sedi", names.length);
    }

    get families() {
        return (this.state.data?.families || []).filter((f) => f.id || f.qty);
    }

    get maxChannel() {
        return Math.max(1, ...(this.state.data?.channels || []).map((c) => c.amount));
    }

    get maxSede() {
        return Math.max(1, ...(this.state.data?.by_sede || []).map((s) => s.amount));
    }

    get maxDay() {
        return Math.max(1, ...(this.state.detail?.days || []).map((d) => d.qty_online + d.qty_pos));
    }

    get maxDetailSede() {
        return Math.max(1, ...(this.state.detail?.sedi || []).map((s) => s.qty_online + s.qty_pos));
    }

    dayLabel(day) {
        return luxon.DateTime.fromISO(day).toFormat("dd.MM");
    }

    /** Label under a day bar: the day number, thinned out so the labels never overlap on a phone. */
    dayTick(day, index) {
        const count = this.state.detail?.days.length || 0;
        const step = count > 45 ? 7 : count > 20 ? 3 : count > 10 ? 2 : 1;
        return index % step === 0 ? luxon.DateTime.fromISO(day).toFormat("d") : "";
    }

    // ---------------------------------------------------------------- drill down

    _domain(extra = []) {
        const data = this.state.data;
        const domain = [
            ["date", ">=", data.utc_from],
            ["date", "<", data.utc_to],
        ];
        if (data.sede_ids.length) {
            domain.push(["sede_id", "in", data.sede_ids]);
        }
        return domain.concat(extra);
    }

    openSales(extra = [], name = _t("Vendite"), groupBy = ["sede_id"]) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: `${name} · ${this.periodLabel}`,
            res_model: "tw.littleinka.kpi.report",
            views: [
                [false, "list"],
                [false, "pivot"],
                [false, "graph"],
            ],
            domain: this._domain(extra),
            context: { group_by: groupBy },
        });
    }

    openProducts(extra = [], name = _t("Prodotti venduti")) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: `${name} · ${this.periodLabel}`,
            res_model: "tw.littleinka.kpi.report.line",
            views: [
                [false, "list"],
                [false, "pivot"],
                [false, "graph"],
            ],
            domain: this._domain(extra),
            context: { group_by: ["product_name"] },
        });
    }

    openFamilyProducts() {
        const family = this.state.detail.family;
        this.openProducts([["family_id", "=", family.id || false]], family.name);
    }

    openCategories() {
        this.action.doAction("tw_littleinka_kpi.action_kpi_category");
    }
}

registry.category("actions").add("tw_littleinka_kpi.dashboard", LittleInkaKpiDashboard);
