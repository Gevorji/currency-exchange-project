from html.parser import HTMLParser
import re


class HtmlTableDataExtractor(HTMLParser):

    useless_data_patterns = [
        '\\s*'
    ]
    for p in useless_data_patterns:
        re.compile(p)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.table_tag_is_opened = False
        self.extracted_tables = []

    def feed(self, data: str) -> tuple:
        super().feed(data)
        return tuple(self.extracted_tables)

    def close(self) -> None:
        self.extracted_tables = []
        super().close()

    def handle_starttag(self, tag, attrs):

        if tag == 'table':
            self.table_tag_is_opened = True
            self.current_table = []

        if tag == 'tr':
            self.current_row = []

        if tag == 'th':
            pass

        if tag == 'td':
            if len(self.current_table) == 0:
                self.current_table.append([])

    def is_valid_data(self, data):
        for is_match in filter(None, (re.fullmatch(p, data) for p in self.useless_data_patterns)):
            if is_match:
                return False
        return True

    def handle_data(self, data: str) -> None:
        if self.get_starttag_text() in ('<td>', '<th>') and self.is_valid_data(data):
            self.current_row.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == 'table':
            self.extracted_tables.append(tuple(self.current_table))
            self.current_table.clear()
            self.table_tag_is_opened = False

        if tag == 'tr':
            self.current_table.append(tuple(self.current_row))
            self.current_row.clear()






if __name__ == '__main__':

    from urllib.request import urlopen

    # html = urlopen('https://www.cbr.ru/currency_base/daily/').read().decode('utf-8')

    html = open(r'C:\Users\User\Desktop\html.txt').read()

    parser = HtmlTableDataExtractor()

    for table in parser.feed(html):
        print(len(table), table)
        


