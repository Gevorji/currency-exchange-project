DROP TABLE IF EXISTS currency;
DROP TABLE IF EXISTS exchange_rates;
PRAGMA foreign_keys=ON;

CREATE TABLE currency(
	
	currency_id INTEGER PRIMARY KEY,
	code TEXT,
	full_name TEXT,
	currency_sign TEXT
	
	);
	
CREATE TABLE exchange_rates (

	exchange_rate_id INTEGER PRIMARY KEY,
	base_currency_id INTEGER REFERENCES currency (currency_id),
	target_currency_id INTEGER REFERENCES currency (currency_id),
	rate REAL
	
	);

CREATE UNIQUE INDEX unique_currency_code_idx ON currency(code);
CREATE UNIQUE INDEX unique_exchange_pair_idx ON exchange_rate(base_currency_id, target_currency_id);