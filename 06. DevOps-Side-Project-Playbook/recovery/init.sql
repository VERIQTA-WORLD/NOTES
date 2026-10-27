CREATE TABLE IF NOT EXISTS veriqta_records (
 id integer PRIMARY KEY,
 name text NOT NULL,
 committed_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
INSERT INTO veriqta_records(id,name) VALUES (1,'veriqta-alpha'),(2,'veriqta-beta'),(3,'veriqta-gamma') ON CONFLICT DO NOTHING;
