# Event-log contract and validation

Each CSV row describes one recorded event. Column names are case-sensitive after leading and trailing whitespace is removed.

| Column | Required | Meaning |
|---|---|---|
| `case_id` | Yes | One order identifier shared by its events. |
| `activity` | Yes | Exact event label. `Payment Received` marks completion; `Order Approved` and `Order Edited` define approval rework. |
| `timestamp` | Yes | ISO 8601 date/time, preferably with UTC offset. |
| `resource` | No | Person or system that produced the event; displayed in case details. |
| `department` | No | Department label; displayed in case details. |
| `cost` | No | Numeric event attribute; displayed, not aggregated into savings. |
| `order_value` | No | Numeric order attribute; displayed, not treated as revenue. |
| `event_order` | No | Integer order for events sharing a timestamp in one case. |

Validation stops the import for missing required columns, blank required values, invalid timestamps, or nonnumeric supplied numeric values. Errors identify the source row. Exact duplicate rows are retained and reported because automatically deleting them could change the recorded process. Tied timestamps are reported; if `event_order` is absent or insufficient, original CSV row order is used and the case is flagged as sequence-ambiguous.

Timezone-aware timestamps are converted to UTC. Naive timestamps use the timezone selected during import; UTC is the default. Dates during ambiguous or nonexistent local daylight-saving times fail validation until made explicit.

All process analytics use events through the first `Payment Received`. A case without that event is open. Later events are visible in the case inspector and reported as excluded. Completed cycle duration is first-event to first-payment elapsed calendar time. No business-hours calendar is applied.

Transition occurrences count every adjacent pair in every case. Transition cases count unique cases containing that pair. Node occurrences likewise count every event; node cases count unique cases visiting the activity. Variants count complete observed sequences through payment (or the last event of an open case).
