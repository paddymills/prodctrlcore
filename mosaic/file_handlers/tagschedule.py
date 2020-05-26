
from os import makedirs
from os.path import join, exists
from xlwings import Book

TAGSCHED_DIR = r"\\hssfileserv1\HSSShared\HSSI Lean\CAD-CAM\TagSchedule"
TEMPLATE = join(TAGSCHED_DIR, "TagSchedule_Template.xls")


class TagSchedule(Book):

    def __init__(self, job_shipment, **kwargs):
        self.job_shipment = job_shipment
        self.job_year = '20' + self.job_shipment[1:3].zfill(2)

        self.year_folder = join(TAGSCHED_DIR, self.job_year)
        self.file = join(self.year_folder, '{}.xls'.format(self.job_shipment))

        if exists(self.file):
            self.init_file(self.file, **kwargs)
        else:
            self.init_file(TEMPLATE, **kwargs)
            if not exists(self.year_folder):
                makedirs(self.year_folder)
            self.save(self.file)

    def init_file(self, file, **kwargs):
        super().__init__(file, **kwargs)

    @ property
    def webs(self):
        header = self.sheets['WEBS'].range("C1:N1").value
        header += self.sheets['WEBS'].range("O2:Q2").value

        return self.sheets['WEBS'].range("C4:P4").expand('down').value

    @webs.setter
    def webs(self):
        # update webs tab
        pass

    @ property
    def flanges(self):
        header = self.sheets['FLANGES'].range("C1:N1").value
        header += self.sheets['FLANGES'].range("O2:Q2").value

        return self.sheets['FLANGES'].range("C4:P4").expand('down').value

    @flanges.setter
    def flanges(self):
        # update flanges tab
        pass

    @ property
    def code_delivery(self):
        header = self.sheets['CODE DELIVERY'].range("A1:G1").value

        return self.sheets['CODE DELIVERY'].range("A2:G2").expand('down').value

    @code_delivery.setter
    def code_delivery(self):
        # update code delivery tab
        pass