# Little Inka KPI (`tw_littleinka_kpi`)

Vendite di tutte le sedi in un'unica dashboard Odoo 20, pensata prima per il telefono:
pezzi per famiglia (Poké, Sushi, Bevande, Dessert…) divisi tra online e cassa,
fatturato, ordini, scontrino medio, sito/app e sedi. Ogni riquadro apre i dettagli.

## Da dove arrivano i dati

| Vendite | Sorgente | Come |
|---|---|---|
| Online (sito, app) | WooCommerce della sede, child theme Little Inka (`inc/odoo-kpi.php`) | POST `/tw_littleinka_kpi/v1/orders` con `Authorization: Bearer <chiave della sede>`, in coda (Action Scheduler) dopo ogni pagamento, cambio di stato e rimborso |
| Cassa | Punto vendita di Odoo | le casse (`pos.config`) collegate alla sede, ordini pagati o registrati |

Gli ordini presi al telefono si battono in cassa: non esiste un canale «Telefono». Un ordine inserito a mano in WooCommerce conta come «Sito».

Nessun dato personale dei clienti: il sito invia un codice anonimo (HMAC dell'e-mail), CAP e località.

## Configurazione (Little Inka KPI → Configurazione)

1. **Sedi**: una per sede, con le sue casse. «Crea la chiave per il sito» mostra indirizzo di Odoo
   e chiave una volta sola (in Odoo resta solo l'hash); vanno incollati nel sito della sede in
   WooCommerce → Odoo KPI → «Salva e prova».
2. **Famiglie di prodotti**: Poké, Sushi, Bevande, Dessert di partenza, con parole chiave modificabili.
3. **Categorie**: le categorie del sito e della cassa compaiono da sole; le parole chiave le assegnano
   alla famiglia, il resto si sceglie a mano (filtro «Da assegnare»).
4. Nel sito di ogni sede, «Ordini già fatti → Invia a Odoo» per avere anche lo storico (nessun doppione).

## Modelli

- `tw.littleinka.kpi.sede`, `tw.littleinka.kpi.family`, `tw.littleinka.kpi.category`
- `tw.littleinka.kpi.order` / `.order.line`: ordini online (upsert per sede + ID WooCommerce)
- `tw.littleinka.kpi.report` / `.report.line`: viste SQL (online + cassa) per pivot, grafici e dashboard
- `tw.littleinka.kpi.dashboard`: dati della client action `tw_littleinka_kpi.dashboard` (`/odoo/littleinka-kpi`)

Gruppi: «Vede la dashboard» e «Amministratore» (sedi, chiavi, famiglie, categorie).

## Test

`odoo -d test_<db> -i tw_littleinka_kpi --test-enable --test-tags /tw_littleinka_kpi --stop-after-init`
(solo su un database di prova: chiave, ricezione ordini, rimborsi, famiglie, dashboard, casse in una sola sede).
