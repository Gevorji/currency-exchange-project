import json
import sqlite3
import sys

currencies_json = json.load(open('currencies.json'))

db_name = sys.argv[1]

conn = sqlite3.connect(db_name)
cur = conn.cursor()

for currency_code in currencies_json:
    db_record = (currency_code, currencies_json[currency_code]['name'],
                 currencies_json[currency_code]['units']['major']['symbol'])

    cur.execute('INSERT INTO currency(code, full_name, currency_sign) VALUES (?,?,?)', db_record)

conn.commit()
conn.close()
cur.execute('INSERT INTO currency(code, full_name, currency_sign) VALUES ('AUD','aUSTRALLIAN DOLL', '$')')
