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
2. **Famiglie di prodotti**: Poké, Sushi, Bevande, Dessert e Accessori di partenza, con parole chiave
   modificabili. La famiglia con «Raccoglie il resto» (Accessori) prende le categorie che nessuna parola
   chiave riconosce: niente resta «Da assegnare».
3. **Categorie**: le categorie del sito e della cassa compaiono da sole, già assegnate: con le parole
   chiave, altrimenti con la famiglia della categoria madre della cassa («M» sotto «Crea la tua Poke»),
   altrimenti in Accessori. La famiglia si cambia a mano. «Conta nei pezzi» è spento per le aggiunte
   (categorie con «extra» nel nome): il loro incasso resta nella famiglia, ma una poké con base extra
   è un pezzo solo. Nel dettaglio della famiglia le aggiunte hanno un elenco a parte.
4. **Prodotti con famiglia propria**: un prodotto della cassa che non segue la sua categoria, per
   esempio sacchetti e posate venduti dal tasto «Extras» (creati da soli quando il nome del prodotto
   contiene una parola chiave di un'altra famiglia).
5. Nel sito di ogni sede, «Ordini già fatti → Invia a Odoo» per avere anche lo storico (nessun doppione).

## Modelli

- `tw.littleinka.kpi.sede`, `tw.littleinka.kpi.family`, `tw.littleinka.kpi.category`, `tw.littleinka.kpi.product`
- `tw.littleinka.kpi.order` / `.order.line`: ordini online (upsert per sede + ID WooCommerce)
- `tw.littleinka.kpi.report` / `.report.line`: viste SQL (online + cassa) per pivot, grafici e dashboard
- `tw.littleinka.kpi.dashboard`: dati della client action `tw_littleinka_kpi.dashboard` (`/odoo/littleinka-kpi`)

Gruppi: «Vede la dashboard» e «Amministratore» (sedi, chiavi, famiglie, categorie).

## Test

`odoo -d test_<db> -i tw_littleinka_kpi --test-enable --test-tags /tw_littleinka_kpi --stop-after-init`
(solo su un database di prova: chiave, ricezione ordini, rimborsi, famiglie, dashboard, casse in una sola sede).
