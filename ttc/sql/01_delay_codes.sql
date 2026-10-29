-- 01_delay_codes.sql
-- Lookup table of TTC bus delay codes, from the City of Toronto Open Data
-- "TTC Bus Delay Data" package (resource: Code Descriptions).
-- The source file has garbled dash characters ("â") in some descriptions;
-- they are written here as plain hyphens.
--
-- Replace YOUR_PROJECT with your Google Cloud project id.

CREATE SCHEMA IF NOT EXISTS `YOUR_PROJECT.ttc` OPTIONS (location = 'US');

CREATE OR REPLACE TABLE `YOUR_PROJECT.ttc.delay_codes`
OPTIONS (description = 'TTC bus delay reason codes (City of Toronto Open Data). Garbled dash characters fixed on load.') AS
SELECT code, description FROM UNNEST([
  STRUCT('EFB' AS code, 'BODY' AS description), ('EFCAN', 'CANCELLATION'), ('EFD', 'DOORS'),
  ('EFDB', 'DISC BRAKES'), ('EFHV', 'HIGH VOLTAGE'), ('EFHVA', 'HEAT / VENT / AC'),
  ('EFLV', 'LOW VOLTAGE'), ('EFO', 'OTHER'), ('EFP', 'PROPULSION'), ('EFRA', 'RAMP ISSUES'),
  ('EFT', 'TRUCKS'), ('EFTB', 'TRACK BRAKES'),
  ('MFCN', 'CLEANING'), ('MFDV', 'ON DIVERSION'), ('MFESA', 'NO OPERATOR AVAILABLE DUE TO ESA'),
  ('MFFD', 'FARE DISPUTE'), ('MFLD', 'LABOUR DISPUTE'), ('MFO', 'OTHER'),
  ('MFPI', 'COLLISION/PERSONAL INJURY - TTC NOT INVOLVED'), ('MFPR', 'HELD BY PARADES/MARCHES'),
  ('MFS', 'FIRE / SMOKE'), ('MFSAN', 'UNSANITARY'), ('MFSH', 'USED AS SHUTTLE BUS'),
  ('MFTO', 'ILL OPERATOR & NON CHARGEABLE OPERATOR ISSUES'), ('MFUI', 'ILL CUSTOMER - TRANSPORTED'),
  ('MFUIR', 'ILL CUSTOMER - TRANSPORTATION DECLINED'), ('MFUS', 'UNABLE TO MAINTAIN SCHEDULE'),
  ('MFVIS', 'VISION ISSUES'), ('MFWEA', 'WEATHER RELATED'),
  ('PFO', 'OTHER'), ('PFPD', 'TTC COLLISION - PROPERTY DAMAGE'),
  ('SFAE', 'ASSAULT - EMPLOYEE'), ('SFAP', 'ASSAULT - PATRON'), ('SFBT', 'BOMB THREAT'),
  ('SFDP', 'DISORDERLY PATRON'), ('SFO', 'OTHER'), ('SFPOL', 'HELD DUE TO POLICE INVESTIGATION'),
  ('SFSA', 'ASSAULT - SEXUAL'), ('SFSP', 'SUSPICIOUS PACKAGE'),
  ('TFCNO', 'NO OPERATOR AVAILABLE'), ('TFLF', 'LATE ENTERING SERVICE - FIRST VEHICLE'),
  ('TFLL', 'LATE VEHICLE - ROUTE'), ('TFO', 'OTHER - SWITCH VIOLATION'), ('TFOI', 'ON BOARD INJURY'),
  ('TFPD', 'TTC COLLISION - PROPERTY DAMAGE'), ('TFPI', 'TTC COLLISION - PERSONAL INJURY')
]);
