#!/usr/bin/env python

import xlwings
import os
import re
import logging

from glob import glob
from types import SimpleNamespace

from prodctrlcore.io import HeaderParser

ENG_DIR = r"\\hssieng\DATA\HS\JOBS"
part_mark_pattern = re.compile(r'[a-zA-Z][0-9]+[a-zA-Z]+')

skip = SimpleNamespace()
skip.books = ['Products', 'JobStandards', 'ShipPieces']
skip.sheets = ['Special', 'Template', 'Total', 'L Weights']
skip.types = [      # cSpell:disable
    'Anch Bolt',
    'Anch Wash',
    'Bronze Pl',
    'Elast Brg',
    'Fab Pad',
    'Grating',
    'HS Bolt',
    'HSS',
    'Nut',
    'RB',
    'Rebar',
    'Screw',
    'Std Wash',
    'Stud',
    'Valid Comms.',
    'DTI Wash',
    'STD. WASH',
    'HS BOLT',
    'NUT',
]                   # cSpell:enable

eng_data_maps = SimpleNamespace()
eng_data_maps.THICKNESS = {
    '10 GA.': 0.125,
    '16 GA.': 0.062,
}
eng_data_maps.GRADE = {  # (spec, grade, test)
    'A606 Type 4': ('A606', 'TYPE4', 'N/A'),
}

force_cvn_mode = False


class BomDataCollector:

    def __init__(self, job, shipment, requires_full_load=False, force_cvn=False):
        self.job = job
        self.shipment = shipment

        self.parts = dict()
        self.bom = dict()
        self.null_part = Part(grade=None, thickness=0)

        self.get_job_folder()

        self.fetched_job_standards = False
        self.fetched_full_bom = False

        if force_cvn:
            force_cvn_mode = True

        if requires_full_load:
            self.load_bom()

    def get_part_data(self, part_name):
        if part_name not in self.parts.keys():
            if part_mark_pattern.match(part_name):
                if not self.fetched_job_standards:
                    self.load_job_standards()
            else:
                if not self.fetched_full_bom:
                    self.load_bom()

        try:
            return self.parts[part_name]
        except KeyError:
            return self.null_part

    def load_bom(self):
        # TODO: Cross reference JobStandards with rest of data?

        # fetch full bom
        xl_app = xlwings.App()
        for bom_file in self.get_bom_files():
            wb = xl_app.books.open(bom_file)

            for sheet in wb.sheets:
                if sheet.name not in skip.sheets:
                    try:
                        self.extract_sheet_data(sheet)
                    except:
                        logging.exception(
                            "Error at workbook {} sheet {}".format(wb.name, sheet.name))

            wb.close()
        xl_app.quit()

        self.fetched_full_bom = True

    def load_job_standards(self):
        # fetch job standards data
        xl_app = xlwings.App()
        xl_file = glob(os.path.join(self.job_folder, "JobStandards.xls*"))[0]
        wb = xl_app.books.open(xl_file)

        for sheet in wb.sheets:
            if sheet.name not in skip.sheets:
                try:
                    self.extract_sheet_data(sheet, skip_bom_processing=True)
                except:
                    logging.exception(
                        "Error at workbook {} sheet {}".format(wb.name, sheet.name))

            wb.close()
        xl_app.quit()

        self.fetched_job_standards = True

    def get_job_folder(self):
        # find path
        base_folder = os.path.join(ENG_DIR, self.job)
        for folder in glob(base_folder + '-*'):
            folder_shipment = folder.split('-')[1]
            if folder_shipment.isalpha():
                continue
            if str(int(self.shipment)) in folder_shipment:
                self.job_folder = os.path.join(folder, 'BOM')
                break
        else:
            self.job_folder = os.path.join(base_folder, 'BOM')
        logging.info(
            "Using engineering BOM folder: {}".format(self.job_folder))

    def get_bom_files(self):
        # workbook list generator
        for entry in os.scandir(self.job_folder):
            if entry.is_file() and entry.name.split('.')[0] not in skip.books:
                yield entry.path

    def extract_sheet_data(self, sheet, skip_bom_processing=False):
        end = sheet.range('Print_Area').last_cell.row

        # assemblies queue
        assemblies = list()

        previous_line_type = 'ASSEMBLY'
        header_rng = sheet.range("B2:AB2").value
        header = self.process_header(HeaderParser(header=header_rng))
        for row in sheet.range("B4:AB{}".format(end)).value:
            line = self.process_line(header.parse_row(row))

            if skip_bom_processing:
                continue

            if type(line) is Assembly:
                if previous_line_type == 'PART':
                    while len(assemblies) > 0:
                        _assembly = assemblies.pop()
                        self.bom[_assembly.mark] = _assembly

                    previous_line_type = 'ASSEMBLY'

                assemblies.append(line)

            elif type(line) is Part:
                is_main_component = (not part_mark_pattern.match(line.mark))
                for assembly in assemblies:
                    if is_main_component:   # add to all parts as parent-component
                        proper_mark = "{parent}-{component}".format(
                            parent=assembly.mark, component=line.mark)
                        self.parts[proper_mark] = line
                    assembly.add_part(line, row[header.QTY])

                if is_main_component:
                    del self.parts[line.mark]
                previous_line_type = 'PART'

    def process_header(self, header):
        ALIASES = dict(
            name='MARK',
            type='COMM',
            thickness='Description',
            thk='Description',
            weight='SHIP WT'
        )

        header.add_header_aliases(ALIASES)
        header.indexes['Width'] = header.thk + 2
        header.indexes['Length Inches'] = header.length + 1

        if "LBS" in header.weight:
            header.units = "IMPERIAL"
        elif "KG" in header.weight:
            header.units = "METRIC"

    def process_line(self, line):

        if line.mark is None or line.type in skip.types:
            return None

        if type is None:    # ASSEMBLY

            return Assembly(line)

        # ~~~~~~~~~~~~~~~~~~ PART (not previously parsed/created) ~~~~~~~~~~~~~~~~~~~~~~~
        if line.mark not in self.parts.keys():
            # length
            if line.header.units == 'IMPERIAL':
                _feet = line.length
                _inches = line.length_inches
                length = _feet * 12 + _inches
            else:
                length = line.length

            if line.spec in eng_data_maps.GRADE.keys():
                _spec, _grade, _test = eng_data_maps.GRADE[line.spec]
                line.spec = _spec
                line.grade = _grade
                line.test = _test

            # data.remarks = line[header.REMARKS]
            self.parts[line.mark] = Part(
                parsed_row=line, len=length, length=length)

        return self.parts[line.mark]


class Part:

    def __init__(self, *args, **kwargs):
        self.assemblies = list()    # assemblies that part occurs on

        self.__dict__.update(kwargs)

        if type(self.thk) is str:
            self.thk = eng_data_maps.THICKNESS[self.thk]

    def __repr__(self):
        return "[{qty}]|{part} ({grade})".format(qty=self.qty, part=self.name, grade=self.material_grade)

    def __getattr__(self, attr):
        if attr in self.__dict__:
            return self.__dict__[attr]

        return getattr(self.parsed_row, attr)

    @property
    def material_grade(self):
        if self.grade is None:
            return None

        if 'HPS' in self.grade:
            self.zone = 3
        else:
            self.zone = 2

        if type(self.grade) in (float, int):     # float -> int  i.e. 50 -> '50'
            self.grade = int(self.grade)

        grade = "{spec}-{grade}".format(spec=self.spec, grade=self.grade)
        if self.test == 'N/A':
            return grade
        elif self.test:
            return grade + "{test}{zone}".format(test=self.test[0], zone=self.zone)
        elif force_cvn_mode:
            return grade + "T2"
        return grade

    @property
    def qty(self):
        total = 0
        for assembly, qty in self.assemblies:
            total += assembly.qty * qty

        return total

    def add_assembly(self, assembly, part_qty):
        self.assemblies.append((assembly, part_qty))

        return self


class Assembly:

    def __init__(self, *args, **kwargs):
        self.parts = list()

        self.__dict__.update(kwargs)

    def add_part(self, part, qty):
        part.add_assembly(self, qty)
        self.parts.append(part)

    def __getattr__(self, attr):
        if attr in self.__dict__:
            return self.__dict__[attr]

        return getattr(self.parsed_row, attr)
