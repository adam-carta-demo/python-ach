import math
from data_types import (Header, FileControl, BatchHeader, BatchControl,
                        EntryDetail, AddendaRecord) 
from settings import *

from datetime import datetime
from pprint import pprint

class AchFile(object):

    """
    Holds:

    Header (1)
    Batch  (n) <-- multiple
    Footer (1)

    What else this needs to do:
        - Calculate Control fields and credate a FileControl object
            - get_batch_count
            - get_block_count
            - get_entry_add_count
            - get_entry_hash
            - get_total_debit
            - get_total_credit
    """

    def __init__(self, file_id_mod):
        """
        args: header (Header), batches (List[FileBatch]), control (FileControl)t
        """

        self.header  = Header(IMMEDIATE_DEST,IMMEDIATE_ORG,file_id_mod,IMMEDIATE_DEST_NAME,
                                IMMEDIATE_ORG_NAME,)
        self.batches = list()

    def add_batch(self,std_ent_cls_code,batch_info=list(),credits=True,debits=False):

        entry_desc = self.get_entry_desc(std_ent_cls_code)

        batch_count = len(self.batches) + 1

        datestamp = datetime.today().strftime('%y%m%d') #YYMMDD

        if credits and debits:
            serv_cls_code = '200'
        elif credits:
            serv_cls_code = '220'
        elif debits:
            serv_cls_code = '225'

        batch_header = BatchHeader(serv_cls_code=serv_cls_code,company_name=IMMEDIATE_ORG_NAME,
                                    company_id=COMPANY_ID, std_ent_cls_code=std_ent_cls_code,
                                    entry_desc=entry_desc, desc_date='', eff_ent_date=datestamp,
                                    orig_stat_code='1', orig_dfi_id=ORIG_DFI_ID,batch_id=batch_count)

        entries = list()
        entry_counter = 1

        for record in batch_info:
            entry = EntryDetail(std_ent_cls_code)
            pprint(record)

            entry.transaction_code = record['type']
            entry.recv_dfi_id = record['routing_number']
            
            if len(record['routing_number']) < 9:
                entry.calc_check_digit()
            else:
                entry.check_digit = record['routing_number'][8]

            entry.dfi_acnt_num  = record['account_number']
            entry.amount        = int(round(float(record['amount']), 2) * 100)
            entry.ind_name      = record['name'].upper()[:22]
            entry.trace_num     = ORIG_DFI_ID + entry.validate_numeric_field(entry_counter, 7)

            entries.append(entry)
            entry_counter += 1

        self.batches.append( FileBatch( batch_header, entries ) )
        self.set_control()


    def set_control(self):

        batch_count     = len(self.batches)
        block_count     = self.get_block_count(self.batches)
        entry_hash      = self.get_entry_hash(self.batches)
        entadd_count    = self.get_entadd_count(self.batches)
        debit_amount    = self.get_debit_amount(self.batches)
        credit_amount   = self.get_credit_amount(self.batches)
        print block_count
        self.control = FileControl(batch_count, block_count, entadd_count, entry_hash, debit_amount, credit_amount)

    def get_block_count(self, batches):

        return int(math.ceil(self.get_lines(batches)/10.0))

    def get_lines(self, batches):
        header_count    = 1
        control_count   = 1
        batch_header_count = len(batches)
        batch_footer_count = batch_header_count

        entadd_count = self.get_entadd_count(batches)

        lines = header_count + control_count + batch_header_count + batch_footer_count + entadd_count

        return lines

    def get_entadd_count(self, batches):
        entadd_count = 0

        for batch in batches:
            entadd_count = entadd_count + int(batch.batch_control.entadd_count)

        return entadd_count

    def get_entry_hash(self, batches):
        entry_hash = 0

        for batch in batches:
            entry_hash = entry_hash + int(batch.batch_control.entry_hash)

        if len(str(entry_hash)) > 10:
            pos = len(str(entry_hash)) - 10
            entry_hash = str(entry_hash)[pos:]
        else:
            entry_hash = str(entry_hash)

        return entry_hash

    def get_debit_amount(self, batches):
        debit_amount = 0

        for batch in batches:
            debit_amount = debit_amount + int(batch.batch_control.debit_amount)

        return debit_amount

    def get_credit_amount(self, batches):
        credit_amount = 0

        for batch in batches:
            credit_amount = credit_amount + int(batch.batch_control.credit_amount)

        return credit_amount

    def get_nines(self, rows):
        nines = ''

        for i in range(rows):
            for l in range(94):
                nines += '9'
            if i == rows - 1: continue
            nines += "\n"

        return nines

    def get_entry_desc(self, std_ent_cls_code):

        if std_ent_cls_code == 'PPD':
            entry_desc = 'PAYROLL'
        elif std_ent_cls_code == 'CCD':
            entry_desc = 'DUES'
        else:
            entry_desc = 'OTHER'

        return entry_desc

    def render_to_string(self):
        """
        Renders a nacha file as a string
        """

        ret_string = self.header.get_row() + "\n"

        for batch in self.batches:
            ret_string += batch.render_to_string()

        ret_string += self.control.get_row() + "\n"

        lines = self.get_lines(self.batches)

        nine_lines = int(10 * (math.ceil(lines / 10.0) - (lines / 10.0)));

        ret_string += self.get_nines(nine_lines)

        return ret_string

class FileBatch(object):

    """
    Holds:

    BatchHeader  (1)
    Entry        (n) <-- multiple
    BatchControl (1)
    """

    def __init__(self, batch_header, entries):
        """
        args: batch_header (BatchHeader), entries (List[FileEntry])
        """

        self.batch_header   = batch_header
        self.entries        = entries

        #set up batch_control 

        batch_control = BatchControl(self.batch_header.serv_cls_code)

        batch_control.entadd_count  = len(self.entries);
        batch_control.entry_hash    = self.get_entry_hash(self.entries)
        batch_control.debit_amount  = self.get_debit_amount(self.entries)
        batch_control.credit_amount = self.get_credit_amount(self.entries)
        batch_control.company_id    = self.batch_header.company_id
        batch_control.orig_dfi_id   = self.batch_header.orig_dfi_id
        batch_control.batch_id      = self.batch_header.batch_id

        self.batch_control = batch_control

    def get_entry_hash(self, entries):

        entry_hash = 0

        for entry in entries:
            entry_hash = entry_hash + int(entry.recv_dfi_id)

        if len(str(entry_hash)) > 10:
            pos = len(str(entry_hash)) - 10
            entry_hash = str(entry_hash)[pos:]
        else:
            entry_hash = str(entry_hash)

        return entry_hash

    def get_debit_amount(self, entries):
        debit_amount = 0

        for entry in entries:
            if str(entry.transaction_code) in ['27','37','28','38']:
                debit_amount = debit_amount + int(entry.amount)

        return debit_amount 

    def get_credit_amount(self, entries):
        credit_amount = 0

        for entry in entries:
            if str(entry.transaction_code) in ['22','32','23','33']:
                credit_amount = credit_amount + int(entry.amount)

        return credit_amount 


    def render_to_string(self):
        """
        Renders a nacha file batch to string
        """

        ret_string = self.batch_header.get_row() + "\n"

        for entry in self.entries:
            ret_string += entry.get_row() + "\n"

        ret_string += self.batch_control.get_row() + "\n"

        return ret_string

class FileEntry(object):

    """
    Holds:

    EntryDetail (1)
    AddendaRecord (n) <-- for some types of entries there can be more than one
    """

    def __init__(self, entry_detail, addenda_record):
        """
        args: entry_detail( EntryDetail), addenda_record (List[AddendaRecord])
        """

        self.entry_detail   = entry_detail
        self.addenda_record = addenda_record

    def render_to_string(self):
        """
        Renders a nacha batch entry and addenda to string
        """
        
        ret_string = self.entry_detail.get_row() + "\n"
        
        for addenda in self.addenda_record:
            ret_string += addenda.get_row() + "\n"

        return ret_string