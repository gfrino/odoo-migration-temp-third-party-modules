# Porting Odoo 20

Questi moduli sono stati portati e collaudati su Odoo 20.0-20261026. Il salto
OpenUpgrade 19→20 utilizzato nello staging richiede ancora framework e script
sperimentali: il collaudo dello staging è necessario prima della produzione.
Il codice dei fornitori con licenza proprietaria resta nella copia privata del
cliente e non è incluso in questo repository.

## Provenienza

| Moduli | Base del porting |
| --- | --- |
| `tw_extend`, `tw_incentivo` | Codice cliente dalla versione 16; API, viste, sicurezza e report adattati a 20 |

I moduli di terze parti (OCA e simili) che abbiamo portato a 20 **non stanno più in questo
repository**: sono nel repo privato transitorio
[`odoo-migration-temp-third-party-modules`](https://github.com/gfrino/odoo-migration-temp-third-party-modules),
ramo `20.0`, con la tabella delle basi di porting (repo e commit di origine). Quando esce la
versione ufficiale si installa quella e si toglie il modulo dal repo transitorio.
Questo repository contiene solo moduli ticinoWEB (`tw_*`).

Dipendenze già disponibili per 20 usate nel collaudo:
`web_responsive` da OCA/web `6ac74409cd559529374236476353d453d5568c5e`,
`project_department` da OCA/project `7e05a3d4fb1eedab13ac1001a9aa731dffb025c5`,
`spreadsheet_dashboard_purchase_oca` da OCA/spreadsheet
`3ee75a1555aac49fb69ad1a39d130f2555eb638d`.

## Comportamento e migrazione

- Sicurezza adattata al modello nativo `ir.access` della versione 20.
- `project_role` estende il modello nativo, conservandone le relazioni utente.
- Viste elenco, card, nomi dei campi, API Owl e parametri di configurazione aggiornati.
- Sconti sequenziali, IVA aggiuntiva e incentivi mantengono la logica del cliente.
  La contabilizzazione applica gli aggiustamenti prima del passaggio allo stato registrato.
- Il wizard di pagamento supporta il contesto `active_ids` e mantiene la gestione
  nativa per lotti e conversioni di valuta.
- Gli allegati prodotto vengono aggiunti al compositore del singolo preventivo;
  il modello email condiviso non viene modificato.
- I campi ritirati dal core necessari ai dati originali sono conservati in
  `migration_compat.py`, compresi mobile separato e indirizzi privati.
- `mail_tracking` conserva i valori tecnici storici. `legacy_chatter.py` li rende
  leggibili senza modificare i testi originali dei messaggi e applica i controlli
  nativi di accesso ai campi per il destinatario effettivo.
- Lo script post-migrazione marca i messaggi precedenti alla versione 20 e
  conserva tipo, etichetta e valuta originali. Non marcare allo stesso modo i
  nuovi messaggi nativi, che contengono già lo storico nel corpo HTML.
- I report usano le macro QWeb native 20; la stampa standard svizzera riserva
  una pagina alla QR-bill. I PDF storici allegati non vanno rigenerati. Il riepilogo standard riporta
  i valori degli sconti, dell’IVA personalizzata e del totale contabile originale.

Il porting dei moduli non sostituisce la migrazione dei dati: occorrono i singoli
salti OpenUpgrade e la conversione delle autorizzazioni, dei campi e delle
relazioni ritirati dal core. Occorre ripristinare anche formato, testi aziendali e imposte predefinite
dallo snapshot: l’inizializzazione di un modulo standard può sostituirli.
Gli script operativi, i confronti e i backup sono
conservati separatamente in area privata; non contengono segreti nel repository.

## Validazione eseguita

Controlli sintattici Python/XML e manifest; installazione su riferimento nativo
20 e aggiornamento della copia migrata senza patch permissive alle viste.
Collaudi con rollback: sconti fissi/percentuali con IVA, incentivi, preparazione
fattura, compositore email, quattro report personalizzati, contabilizzazione e
pagamento completo di una copia di fattura. Verificati accesso degli utenti
originali, blocco dell'autoattribuzione degli indirizzi privati e revoca immediata.

Prove browser: login, lista vendite, ridimensionamento delle colonne e
persistenza dopo ricaricamento, chatter in basso, modulo Solare e visualizzazione dei valori
prima/dopo nello storico. Verificate anche le stampe PDF dei tre preventivi,
della fattura personalizzata e della fattura standard con QR-bill.
I confronti con lo snapshot originale verificano contabilità, riconciliazioni,
contatori, password, dati custom, messaggi e hash dei file.
