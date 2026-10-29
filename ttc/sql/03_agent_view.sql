-- 03_agent_view.sql
-- The view the agent queries. Duplicates are already removed in the clean table;
-- is_duplicate is kept as FALSE so queries that filter NOT is_duplicate keep working.
--
-- Replace YOUR_PROJECT with your Google Cloud project id.

CREATE OR REPLACE VIEW `YOUR_PROJECT.ttc.bus_delays` AS
SELECT *, FALSE AS is_duplicate
FROM `YOUR_PROJECT.ttc.bus_delays_clean`;
