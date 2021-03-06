
import inflection

from xlwings import Range
from re import compile as regex

PARAM_RE = regex(r'(?P<text>[a-zA-Z_]+)(?P<id>[0-9]*)')


class HeaderParser:

    """
        HeaderParser: A class to parse an excel header row

        Can be used multiple ways:
        1) To access column ids based off of header text
        2) To access items of a row based off of header text

        To access row items, must parse the row before use

        Can also pass in partial header names to access columns
        for example:
            'op1' matches 'Operation1'
            'matl' matches 'Material'
        In these methods, trailing ids (if applicable) must match
    """

    def __init__(self, header=None, sheet=None, header_range="A1", expand_header=True):

        if header:
            self.header = header
        else:
            rng = sheet.range(header_range)
            if expand_header:
                rng = rng.expand('right')

            self.header = rng.value

        self.indexes = dict()
        self._init_header()

    def __getattr__(self, name):
        return self.get_index(name)

    def get_index(self, key):
        try:
            index = self.indexes[key]
        except KeyError:
            index = self.infer_key(key)

        return index

    def _init_header(self):
        if type(self.header[0]) is not list:
            # header is single row
            self.header = [self.header]

        for row in self.header:
            for index, column in enumerate(row):
                if column:
                    # not empty cell
                    self.add_column_index(column, index)

    def add_column_index(self, key, index):
        self.indexes[key] = index
        self.indexes[key.lower()] = index
        self.indexes[to_(key)] = index

    def add_header_aliases(self, mapping=dict(), **kwargs):
        mapping.update(kwargs)
        for k, v in mapping.items():
            self.add_header_alias(k, v)

    def add_header_alias(self, column, header_val):
        try:
            index = self.get_index(header_val)

            self.add_column_index(column, index)
        except KeyError:
            pass

    def parse_row(self, row):
        if type(row) is Range:
            row = row.value

        return ParsedRow(row, self)

    def infer_key(self, key):
        key = key.lower()

        _m = PARAM_RE.match(key)
        key_text = _m.group('text')
        key_id = _m.group('id')

        # infer based on key that has the
        # - str.startswith match
        # - same trailing ID (if applicable)
        for col in self.indexes:
            _m = PARAM_RE.match(col)
            col_text = _m.group('text')
            col_id = _m.group('id')

            if key_id == col_id:
                if col_text.startswith(key_text):
                    return self.indexes[col]

        # infer based on key that has the
        # - key is found in column text
        # - same trailing ID (if applicable)
        # - CRITICAL: can only have one match
        match = None
        for col in self.indexes:
            _m = PARAM_RE.match(col)
            col_text = _m.group('text')
            col_id = _m.group('id')

            if key_id == col_id:
                if semi_sequential_match(key_text, col_text):
                    if match:
                        raise KeyError(
                            "Multiple matching keys found when inferring column headers. Key={}".format(key))
                    return self.indexes[col]

        raise KeyError


class ParsedRow:

    def __init__(self, row, header):
        self._data = row
        self.header = header

    def __getattr__(self, name):
        return self.get_item(name)

    def __setattr__(self, name, value):
        try:
            index = self.header.get_index(name)
            self._data[index] = value
        except KeyError:
            self.__dict__[name] = value

    def __eq__(self, other):
        for i in self.header.indexes.values():
            if self._data[i] != other._data[i]:
                return False

        return True

    def get_item(self, header_val):
        index = self.header.get_index(header_val)

        return self._data[index]


def to_(text):
    return inflection.parameterize(text, separator='_')


def semi_sequential_match(find_str, within_str):
    """
        Returns if find string exists in
        search string sequentially.

        Find string can skip characters in
        search string.

        i.e. find 'matl' in 'material'
    """

    find_chars = list(find_str)
    current_char = find_chars.pop(0)
    for char in within_str:
        if char == current_char:
            if find_chars:
                char = find_chars.pop(0)
            else:
                return False

    return True
