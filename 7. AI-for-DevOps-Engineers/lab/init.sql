CREATE TABLE IF NOT EXISTS veriqta_users (id integer PRIMARY KEY, name text NOT NULL);
INSERT INTO veriqta_users VALUES (1,'veriqta-alpha'),(2,'veriqta-beta') ON CONFLICT DO NOTHING;
