DROP TABLE IF EXISTS currency;
DROP TABLE IF EXISTS exchange_rates;
DROP TABLE IF EXISTS rates_info_source;
PRAGMA foreign_keys=ON;

CREATE TABLE currency(
	
	currency_id INTEGER PRIMARY KEY,
	code TEXT NOT NULL,
	full_name NOT NULL,
	currency_sign NOT NULL
	
	);

CREATE TABLE rates_info_source(
		 
		 source_id INTEGER PRIMARY KEY,
		 src_path TEXT,
		 src_type TEXT,
		 days_valid INTEGER,
		 last_appeal
		 
	     );
	
CREATE TABLE exchange_rates (

	exchange_rate_id INTEGER PRIMARY KEY,
	base_currency_id INTEGER REFERENCES currency (currency_id),
	target_currency_id INTEGER REFERENCES currency (currency_id),
	rate REAL NOT NULL,
	source_id int REFERENCES rates_info_source(source_id)
	);

CREATE UNIQUE INDEX unique_currency_code_idx ON currency(code);
CREATE UNIQUE INDEX unique_exchange_pair_idx ON exchange_rates(base_currency_id, target_currency_id);