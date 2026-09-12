# Memory price source notes

Checked 2026-09-12. These notes distinguish source publication time from the time
our collector first observed an entry. Spot means **현물**, not a contract price.

## Sources and fields

- [TrendForce DRAM public tables](https://www.trendforce.com/price/dram/dram_spot): DRAM chip spot, DRAM module spot and DRAM contract averages.
- [TrendForce NAND public tables](https://www.trendforce.com/price/flash/flash_spot): NAND chip spot and NAND contract averages.
- [DRAMeXchange methodology and session schedule](https://www.dramexchange.com/service/faqs): spot/contract definitions, averaging, historical-data access and session release times.

The collector reads the visible public summary tables only, without authentication,
paid chart endpoints or paid-history access. It uses Session Average (or Average),
not the highest quote. Each density, generation, organization, speed and eTT grade
is a separate series. Chip quotes use USD per chip and module quotes USD per module.
The NAND chip table currently covers SLC/MLC products; it is not an aggregate
TLC/QLC SSD cost index, and it must not be labelled as such.

## Verified release clocks

The FAQ has two inconsistent schedule tables. Its detailed General vs. Silver+
table states **11:00, 14:40, 18:10 Asia/Taipei** for the general-access sessions.
These correspond to **12:00, 15:40, 19:10 Asia/Seoul**. Actual DRAM public-table
timestamps agree with 18:10. The older city table instead says 14:30 and 18:00;
do not configure the collector from that older table.

Silver+ early notices are 10:50, 14:20 and 17:50 Taipei, but this project has no
such subscription. Do not claim early-notice access from public summary data.

The FAQ says DRAM/NAND contract prices are generally published monthly. Neither
a fixed day nor fixed time for the public contract summary is confirmed.
For modules and NAND public summary tables, a separate exact publication schedule
has not been established. Rechecking at the general spot sessions is a polling
policy, not evidence that these individual tables refresh three times daily.

On 2026-09-12, the DRAM chip table was dated 2026-09-11 18:10 Taipei. Module and
NAND chip tables were dated 2026-08-31 14:40 Taipei. Public contract tables were
dated 2026-07-31, although separate paid-report announcements referenced August.
The UI must retain these older source dates and mark delayed public summaries.
Fetching a page today does not make its prices today's prices.

## History and missing data

`fetch_memory.py` keeps one latest session per source date. It preserves the first
observed time when the source timestamp/value are unchanged, rejects time-travel
source dates, preserves a later session when an older cache is returned, records
same-timestamp value revisions, and retains history on fetch/parse failure. There
is no fabricated price backfill. A first collection may contain only one point
per item; histories grow when new public observations are available.

The parser validates source timestamps, exact named average columns, positive
finite values and low <= average <= high. A missing section or changed layout
fails closed instead of silently switching to another column.

## Usage and deployment

[TrendForce terms, section 6](https://www.trendforce.com/about/terms) explicitly
discuss prior written permission for reproduction, public redistribution and
data-mining/crawler use. Merely being able to read a public table does not verify
permission for an automatically republished price database. No such permission
has been supplied in this task. `collection_policy.publication_permission` records
that fact; source attribution is required but is not itself authorization.

Offline parser checks: `python fetch_memory.py --self-test`.
One-time read-only inspection: `python fetch_memory.py --preview`.
Default metadata-only refresh (no network request, no numeric price copying):
`python fetch_memory.py`.

After provider permission explicitly covers automated extraction and public
redistribution, enable with `--provider-permission-confirmed` or the controlled
environment setting `MEMORY_PRICE_COLLECTION_ALLOWED=true`. A basic paid research
subscription alone is not evidence of those rights. With permission absent,
series are `permission_required`, contain empty points, and have `refresh.enabled`
set to false. The 2026-09-12 source-date audit remains visible in the catalog.
Previously collected history is retained if execution permission is removed,
but `display_prices: false` and `permission_required` mark it as hidden/inactive.
The current initial public dataset has no numeric observations at all.

Use `--only-if-changed` in a scheduled collector to avoid rewriting the file when
only `checked_at` or the computed source age changed. Source updates, permissions,
status transitions, quote revisions and new dates still produce a file change.

Any deployment enabling recurring extraction/publication should resolve the
provider's applicable permission first. Scheduled execution delay and upstream
caching also mean an exact release-second update cannot be guaranteed by cron.
