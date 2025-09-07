#!/usr/bin/env python3
import struct
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
import sys

FIT_EPOCH = datetime(1989, 12, 31, 0, 0, 0)

base_formats = {
    0: 'B',  # enum
    1: 'b',  # sint8
    2: 'B',  # uint8
    3: 'h',  # sint16
    4: 'H',  # uint16
    5: 'i',  # sint32
    6: 'I',  # uint32
    7: 's',  # string
    8: 'f',  # float32
    9: 'd',  # float64
    10: 'B', # uint8z
    11: 'H', # uint16z
    12: 'I', # uint32z
    13: 'B', # byte
    14: 'q', # sint64
    15: 'Q', # uint64
    16: 'Q', # uint64z
}

class FitParser:
    def __init__(self, data):
        self.data = data
        self.pos = 0
        self.defs = {}
        self.last_timestamp = None

    def read(self, size):
        b = self.data[self.pos:self.pos+size]
        self.pos += size
        return b

    def parse(self):
        header_size = self.data[0]
        data_size = struct.unpack_from('<I', self.data, 4)[0]
        self.pos = header_size
        end = header_size + data_size
        records = []
        while self.pos < end:
            header = self.read(1)[0]
            if header & 0x80:  # compressed timestamp header
                local_msg = (header >> 5) & 0x3
                time_offset = header & 0x1F
                if self.last_timestamp is None:
                    self.last_timestamp = 0
                ts = (self.last_timestamp & ~0x1F) + time_offset
                if ts <= self.last_timestamp:
                    ts += 0x20
                self.last_timestamp = ts
                fields = self.parse_data_message(local_msg)
                fields[253] = ts
                if self.get_global(local_msg) == 20:
                    records.append(fields)
            else:
                is_def = header & 0x40
                local_msg = header & 0x0F
                if is_def:
                    self.parse_definition(local_msg)
                else:
                    fields = self.parse_data_message(local_msg)
                    if 253 in fields:
                        self.last_timestamp = fields[253]
                    elif self.last_timestamp is not None:
                        fields[253] = self.last_timestamp
                    if self.get_global(local_msg) == 20:
                        records.append(fields)
        return records

    def get_global(self, local_msg):
        d = self.defs.get(local_msg)
        return d['global'] if d else None

    def parse_definition(self, local_msg):
        self.read(1)  # reserved
        arch = self.read(1)[0]
        endian = '>' if arch else '<'
        global_msg = struct.unpack(endian + 'H', self.read(2))[0]
        num_fields = self.read(1)[0]
        fields = []
        for _ in range(num_fields):
            field_def = self.read(1)[0]
            size = self.read(1)[0]
            base_type = self.read(1)[0]
            fields.append((field_def, size, base_type))
        self.defs[local_msg] = {'global': global_msg, 'fields': fields, 'endian': endian}

    def parse_data_message(self, local_msg):
        d = self.defs.get(local_msg)
        if not d:
            raise ValueError('Missing definition for local message %d' % local_msg)
        endian = d['endian']
        fields = {}
        for field_def, size, base_type in d['fields']:
            raw = self.read(size)
            value = self.parse_value(raw, base_type, endian)
            fields[field_def] = value
        return fields

    def parse_value(self, raw, base_type, endian):
        base_num = base_type & 0x1F
        fmt = base_formats.get(base_num)
        if not fmt:
            return raw
        size = struct.calcsize(fmt)
        count = len(raw) // size
        fmt = endian + fmt * count
        vals = struct.unpack(fmt, raw)
        if base_type == 7:  # string
            return vals[0].decode('utf-8').rstrip('\x00')
        return vals[0] if count == 1 else vals

def records_to_gpx(records, out_path):
    gpx = ET.Element('gpx', version='1.1', creator='fit2gpx')
    trk = ET.SubElement(gpx, 'trk')
    trkseg = ET.SubElement(trk, 'trkseg')
    for r in records:
        if 0 in r and 1 in r:
            lat = r[0] * 180 / 2**31
            lon = r[1] * 180 / 2**31
            trkpt = ET.SubElement(trkseg, 'trkpt', lat=f"{lat:.6f}", lon=f"{lon:.6f}")
            if 2 in r:
                alt = r[2] / 5.0 - 500
                ET.SubElement(trkpt, 'ele').text = f"{alt:.2f}"
            if 253 in r:
                time = FIT_EPOCH + timedelta(seconds=r[253])
                ET.SubElement(trkpt, 'time').text = time.isoformat() + 'Z'
    ET.ElementTree(gpx).write(out_path, encoding='utf-8', xml_declaration=True)

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('Usage: fit2gpx.py input.fit output.gpx')
        sys.exit(1)
    with open(sys.argv[1], 'rb') as f:
        data = f.read()
    parser = FitParser(data)
    records = parser.parse()
    records_to_gpx(records, sys.argv[2])
