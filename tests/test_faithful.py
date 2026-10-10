"""With no cleaning options, a download must be identical to the upload.

For well-formed files with a consistent style, the download must match byte for byte.
For files that aren't a clean table, refusing with a message is also acceptable.
Silently changing anything is not.
"""

import csv
import io

import pytest

from datawrangler.app import create_app

# Well-formed files: the download must match exactly.
WELL_FORMED = {
    "spaces around column names": " First Name ,Last Name\nAda,Lovelace\n",
    "column names differing only by case": "Name,name\nAda,ada\n",
    "identical column names": "x,x\n1,2\n",
    "leading zeros": "id,phone\n007,07700900123\n",
    "commas and line breaks inside quotes": 'name,note\nAda,"Hello, world"\nAlan,"Line one\nLine two"\n',
    "spaces around values": "name\n Ada \n",
    "text that looks like missing values": "name\nNULL\nNA\nnan\nNone\n",
    "accented and non-Latin text": "name\nCafé\n日本\n",
    "everything is text": "name,city\nAda,London\nAlan,Leeds\n",
    "everything is numbers": "1,2\n3,4\n",
    "Windows line endings": "name,city\r\nAda,London\r\n",
    "byte order mark": "\ufeffname,city\nAda,London\n",
    "no line break at the end": "name,city\nAda,London",
    "every value quoted": '"name","city"\n"Ada","London"\n',
    "Windows line endings with a line break inside a value": 'name,note\r\nAda,"one\ntwo"\r\n',
    "empty lines at the end": "name,city\nAda,London\n\n\n",
}

# Not a clean table: the download must match, or the app must refuse the file.
IRREGULAR = {
    "title line above the table": "Report generated today\nname,city\nAda,London\n",
    "row with too few values": "a,b\n1\n",
    "empty line between rows": "name,city\nAda,London\n\nAlan,Leeds\n",
}


def _rows(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text, newline="")))


def _download(text: str):  # type: ignore[no-untyped-def]
    client = create_app().test_client()
    data = {"file": (io.BytesIO(text.encode()), "test.csv")}
    return client.post("/download", data=data, content_type="multipart/form-data")


@pytest.mark.parametrize("text", WELL_FORMED.values(), ids=WELL_FORMED.keys())
def test_well_formed_files_come_back_unchanged(text: str) -> None:
    response = _download(text)
    assert response.status_code == 200
    assert response.data == text.encode()


@pytest.mark.parametrize("text", IRREGULAR.values(), ids=IRREGULAR.keys())
def test_irregular_files_come_back_unchanged_or_are_refused(text: str) -> None:
    response = _download(text)
    if response.status_code == 200:
        assert _rows(response.data.decode()) == _rows(text)
    else:
        assert response.status_code == 400
