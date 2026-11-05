"""Regresión del JSON cloud_access y los estados de consulta SIA."""

import csv
import io
import json
import unittest
from xml.sax.saxutils import escape

from test_data import parse_sia_votable


def response(rows="", status="OK", message=""):
    return f'''<?xml version="1.0"?>
<VOTABLE version="1.3" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE type="results">
<INFO name="QUERY_STATUS" value="{status}">{message}</INFO>
<TABLE>
<FIELD name="access_url" datatype="char" arraysize="*"/>
<FIELD name="cloud_access" datatype="char" arraysize="*"/>
<FIELD name="t_min" datatype="double"/>
<FIELD name="upload_row_id" datatype="int"/>
<DATA><TABLEDATA>{rows}</TABLEDATA></DATA>
</TABLE></RESOURCE></VOTABLE>'''.encode("utf-8")


class SiaResponseTests(unittest.TestCase):
    def test_json_commas_preserved_and_csv_roundtrip(self):
        cloud = '{"aws": {"bucket_name": "nasa-irsa-spherex", "key": "qr3/example.fits", "region": "us-east-1"}}'
        rows = parse_sia_votable(response(
            f"<TR><TD>https://irsa.ipac.caltech.edu/example.fits</TD>"
            f"<TD>{escape(cloud)}</TD><TD>61268.630812</TD><TD>1</TD></TR>"), "spherex_qr3")
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(json.loads(row["cloud_access"])["aws"]["region"], "us-east-1")
        self.assertEqual(float(row["t_min"]), 61268.630812)
        self.assertEqual(row["upload_row_id"], "1")
        self.assertEqual(row["collection"], "spherex_qr3")
        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
        stream.seek(0)
        self.assertEqual(next(csv.DictReader(stream)), row)

    def test_empty_result_is_not_error(self):
        self.assertEqual(parse_sia_votable(response(), "spherex_qr3_deep"), [])

    def test_service_error_is_not_empty_result(self):
        with self.assertRaisesRegex(ValueError, "invalid collection"):
            parse_sia_votable(response(status="ERROR", message="invalid collection"), "bad")

    def test_non_xml_response_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "XML VOTable"):
            parse_sia_votable(b"service unavailable", "spherex_qr3")


if __name__ == "__main__":
    unittest.main()
