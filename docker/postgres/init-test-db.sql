-- Local-only pytest database. The fixture independently refuses any database name that does not
-- end in `_test`, so a misconfigured test run cannot truncate the development catalog.
CREATE DATABASE semiskill_test;
