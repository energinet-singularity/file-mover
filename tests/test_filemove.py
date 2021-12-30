#!/usr/bin/python3

# import pytest
import logging
import app.filemover
import os
import gzip
import re

log = logging.getLogger(__name__)


def test_filemove(tmpdir, caplog):
    # ------ INITIALIZATION ------
    caplog.set_level(logging.DEBUG)

    path_in = tmpdir.mkdir('input').strpath
    path_archive = tmpdir.mkdir('output').mkdir('archive').strpath
    path_out = os.path.dirname(path_archive)
    os.environ["ARCHIVE"] = "TRUE"

    # Create simple file-contents
    fc = "This is line 1\nThis is line 2\n"

    # Create a file that can be moved
    with open(os.path.join(path_in, "basefile.txt"), "w") as file_in:
        file_in.write(fc)

    # Create a file that should be ignored
    fp = os.path.join(path_in, "basefile_ignore.txt")
    with open(fp, "w") as file_in:
        file_in.write(fc)
    file_ignore = {fp: os.path.getmtime(fp)}
    ignorelist_pre = file_ignore.copy()

    # Create a compressed file that can be uncompressed and moved
    with open(os.path.join(path_in, "basefile_zip.txt.gz"), "wb") as file_in:
        file_in.write(gzip.compress(bytes(fc, 'utf-8')))

    # ------ VERIFICATION OF 'MOVE_FILES' FUNCTION START ------

    # Move files from input to output - and check how many files were moved
    filelist_in_pre = [os.path.join(path_in, file) for file in os.listdir(path_in)
                       if os.path.isfile(os.path.join(path_in, file))]

    # Actual function call is here!
    filedict = app.filemover.move_files(path_in, path_out, path_archive, file_ignore, True)

    filelist_out = [os.path.join(path_out, file) for file in os.listdir(path_out) if
                    os.path.isfile(os.path.join(path_out, file))]
    filelist_arc = [os.path.join(path_archive, file) for file in os.listdir(path_archive)
                    if os.path.isfile(os.path.join(path_archive, file))]

    # Verify files were deleted - and correct amount of files were moved and archived
    assert len(os.listdir(path_in)) == len(filelist_in_pre)-len(filedict), \
        "One or more files were not deleted from the input folder."
    assert len(filelist_out) == len(filelist_in_pre)-len(ignorelist_pre), \
        "One or more files were not transferred as expected."
    assert len(filelist_out) == len(filelist_arc), \
        "One or more files were not archived as expected."

    for file in filelist_in_pre:
        if file not in ignorelist_pre.keys():
            if file[-3:].upper() == ".GZ":
                file = file[:-3]

            # Check expected files were transferred, and they contain the correct data
            assert os.path.basename(file) in os.listdir(path_out), \
                f"File {file} was not transferred to output path."
            assert open(os.path.join(path_out, os.path.basename(file))).read() == fc, \
                f"File {file} does not contain the expected data."

            # Check expected files were archived (and named correctly)
            was_archived = False
            pattern = re.compile(f"^[\\d_-]+{re.escape(os.path.basename(file))}$")
            for file_arch in filelist_arc:
                if pattern.match(os.path.basename(file_arch)):
                    was_archived = True
                    assert open(file_arch).read() == fc, f"Archived file {file} does not contain the expected data."

            assert was_archived, f"File {file} could not be found in the archive."
