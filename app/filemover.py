#!/usr/bin/python3

import logging
import os
from os import path as os_path
import gzip
import smbclient
from smbclient import path as smb_path
from sched import scheduler
import time
import datetime

# Initialize log
log = logging.getLogger(__name__)

# Global variable to remember/show files count of files moved
filemove_count = 0


def read_files(path: str, file_ignore: dict = None, delete_files: bool = False) -> dict:
    """This function will read files from path and return them in a dict

    Function will determine if path is remote or local and act accordingly.
    Files in file_ignore will be ignored if they have the same modified
    timestamp. Files with .gz extension will be unpacked using gzip.

    :param str path: The path to read files from (excl. subdirs)
    :param file_ignore: Dictionary in style {'path/to/file.txt': <modified timestamp>}
    :type file_ignore: dict(str, time)
    :param bool delete_files: Bool to determine if files should be deleted.
    :return: Dictionary of files in style {'filen.ame': <filecontents>, ..}
    :rtype: dict(str, str)
    """

    # Initialize empty dictionary and an empty dummy-dict in case ignore-list was not provided.
    filedict = {}
    if file_ignore is None:
        file_ignore = {}

    # Load relevant lib into local variables
    if smbclient._os.is_remote_path(path):
        client = smbclient
        client_path = smb_path
        read_func = smbclient.open_file
    else:
        client = os
        client_path = os_path
        read_func = open

    # Go through the files in the directory
    for input_file_name in [fi for fi in client.listdir(path) if client_path.isfile(client_path.join(path, fi))]:
        input_file = client_path.join(path, input_file_name)
        log.debug(f"Accessing file '{input_file}'")

        if not (input_file in file_ignore.keys() and file_ignore[input_file] == client_path.getmtime(input_file)):
            try:
                with read_func(input_file, "rb") as in_file:
                    if input_file_name[:3] == ".gz":
                        log.debug(f'Reading and unzipping file {input_file}')
                        filedict[input_file_name[:-3]] = gzip.decompress(in_file.read())
                    else:
                        log.debug(f'Reading file {input_file}')
                        filedict[input_file_name] = in_file.read()

            except Exception:
                log.exception(f"Could not read file '{input_file}' from '{path}'. Will retry next time.")

            else:
                # Update ignore dictionary (this will update orig. dict. if one was passed)
                file_ignore[input_file] = client_path.getmtime(input_file)

                # Delete files if they delete_files is true
                if delete_files:
                    try:
                        client.remove(input_file)

                    except Exception:
                        log.exception(f"Was not allowed to delete file '{input_file}'.")

    # Return the dictionary
    return filedict


def write_file(path: str, filedict: dict, filename_prepend: str = ''):
    """This function will output files from filedict to path

    :param str path: Path where the files will be written
    :param filedict: Dictionary in form {'file.txt': <filecontents>, ..}
    :type filedict: dict(str, str)
    :param str filename_prepend: String to prepend filename, ie. for archiving
    """

    # Load relevant lib into local variables
    if smbclient._os.is_remote_path(path):
        client_path = smb_path
        write_func = smbclient.open_file
    else:
        client_path = os_path
        write_func = open

    # Iterate through elements in the dictionary
    for output_file in filedict:
        try:
            with write_func(client_path.join(path, filename_prepend + output_file), "wb") as out_file:
                out_file.write(filedict[output_file])
            log.debug(f"File '{filename_prepend + output_file}' written to output folder '{path}'.")
        except Exception:
            log.exception(f"Was not allowed to write file '{filename_prepend + output_file}' to '{path}'.")


def move_files_timer(timer: scheduler, input_path: str, output_path: str, archive_path: str = '', file_ignore: dict = None,
                     delete_files: bool = False, read_wait: int = 5):
    """This function is a wrapper for 'move_files'

    The function calls 'move_files' each 'read_wait' seconds.

    :param timer: Scheduler to use for scheduling further calls
    :param int read_wait: Seconds between each consecutive read
    :param str input_path: See 'move_files' function
    :param str output_path: See 'move_files' function
    :param str archive_path: See 'move_files' function
    :param file_ignore: See 'move_files' function
    :type file_ignore: dict(str, time)
    :param bool delete_files: See 'move_files' function
    """

    # Update global variable filemove_count to keep a score of how many files have been moved
    global filemove_count
    filemove_count += len(move_files(input_path, output_path, archive_path, file_ignore, delete_files))
    log.info(f'Moved a total of {filemove_count} files so far..')

    # Set another timer in 'read_wait' seconds to run again.
    timer.enter(read_wait, 1, move_files_timer, (timer, input_path, output_path, archive_path, file_ignore,
                                                 delete_files, read_wait))

    log.debug(f'Timer set to {read_wait} seconds - going to sleep..')


def move_files(input_path: str, output_path: str, archive_path: str = '', file_ignore: dict = None,
               delete_files: bool = False) -> dict:
    """This function will move files from input_path to output_path

    Files will be read from input_path and either moved or copied to
    output_path folder. If files are specified in file_ignore
    (see below) and timestamps match, they will be ignored.
    If 'delete_files' is set, the files will be "moved", otherwise they
    will be "copied".


    Samba/SMB
    If path is remote (samba/smb) it is necessary to specify the username
    and password for the smbclient. Use smbclient.clientconfig.


    Archive
    If archive_path is specified, files will be archived to this path
    as well. The files will be prepended with a formatted timestring.


    :param str input_path: Path to read files from
    :param str output_path: Path to write files to
    :param str atchive_path: Path to archive files ('' = no archiving)
    :param file_ignore: Dict with files to ignore {'/path/to/file.txt': <mtime>, ..}
    :type file_ignore: dict(str, time)
    :param bool delete_files: If set, files will be removed if possible
    """

    # Load files from input_path into a dict
    filedict = read_files(input_path, file_ignore)

    # Archive files if archiving is enabled
    if archive_path != '':
        filename_prepend = f"{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_"
        write_file(archive_path, filedict, filename_prepend)

    # Write files
    write_file(output_path, filedict)

    return filedict


def path_cleanup_timer(timer: scheduler, cleanup_interval: int, path: str, max_file_age_days: int):
    """This function is a wrapper for 'path_cleanup'

    The function calls 'path_cleanup' each 'cleanup_interval' hours.

    :param timer: Scheduler to use for scheduling further calls
    :param int cleanup_interval: Time between each consecutive cleanup in hours
    :param str path: See 'path_cleanup' function
    :param int max_file_age_days: See 'path_cleanup' function
    """

    file_count, del_count = path_cleanup(path, max_file_age_days)
    log.info(f'Cleaning "{path}" - found a total of {file_count} files and deleted {del_count} of them.')

    timer.enter(cleanup_interval*3600, 1, path_cleanup_timer, (timer, cleanup_interval, path, max_file_age_days))


def path_cleanup(path: str, max_file_age_days: int) -> (int, int):
    """Removes files older than 'max_file_age_days' from 'path'

    The modified time of all files within path (excluding subdirs)
    are compared to max_file_age_days and deleted and found to be
    older than specified age.

    :param str path: Path to clean up
    :param int max_file_age_days: Max allowed age of files in days
    """

    # Load relevant lib into local variables
    if smbclient._os.is_remote_path(input_path):
        client = smbclient
        client_path = smb_path
    else:
        client = os
        client_path = os_path

    # Iterate over files in path and check their age agains max_file_age_days
    file_del_count = 0
    filelist = [client_path.join(path, fi) for fi in client.listdir(path) if client_path.isfile(client_path.join(path, fi))]
    for file in filelist:
        if (time.time() - os.path.getmtime(file))/86400 > max_file_age_days:
            try:
                client.remove(file)
                file_del_count += 1
            except Exception:
                log.exception(f"Was not allowed to delete file '{file}'.")

    return len(filelist), file_del_count


def validate_path(path: str):
    # Load relevant lib into local variables
    if smbclient._os.is_remote_path(path):
        client_path = smb_path
    else:
        client_path = os_path

    # Verify path exists and is reachable - handle errors as intelligent as possible.
    try:
        if not client_path.isdir(path):
            raise FileNotFoundError(f"'{path}' is not a valid directory.")
    except FileNotFoundError:
        log.exception("File not found")
        return False
    except ValueError as e:
        log.exception("SMB server not found. {}".format(str(e).split(":")[-1]))
        return False
    except Exception as e:
        if type(e).__name__ == 'SMBAuthenticationError':
            log.exception("Authentication error when connecting to fileshare.")
        elif type(e).__name__ == 'SMBException' or type(e).__name__ == 'NotFound':
            log.exception(e)
        else:
            log.exception("An unhandled exception of type {0} occurred. Arguments:\n{1!r}".format(type(e).__name__, e.args))
        return False
    else:
        return True


# Main code
if __name__ == "__main__":
    # Setup logging for client output
    logging.basicConfig(format="%(levelname)s:%(asctime)s:%(name)s - %(message)s", level=logging.INFO)

    # Initialize scheduler
    timer = scheduler(time.time, time.sleep)

    # SMB Username and Password, if SMB is used
    smb_username = os.environ.get('SMB_USERNAME')
    smb_password = os.environ.get('SMB_PASSWORD')
    if smb_username is not None:
        smbclient.ClientConfig(username=smb_username, password=smb_password)

    # Paths (Add a slash/backslash to end of filepaths if not there)
    input_path = os.environ.get('SMB_INPUTPATH', '/input')
    if input_path[-1] != input_path[0]:
        input_path = f"{input_path}{input_path[0]}"
    if not validate_path(input_path):
        raise FileNotFoundError(f"Error: Something is wrong with input directory ({input_path})")

    output_path = os.environ.get('SMB_OUTPUTPATH', '/output')
    if output_path[-1] != output_path[0]:
        output_path = f"{output_path}{output_path[0]}"
    if not validate_path(output_path):
        raise FileNotFoundError(f"Error: Something is wrong with output directory ({output_path})")

    archive = (os.environ.get('ARCHIVE', 'FALSE')).upper() != 'FALSE'
    if archive:
        archive_path = f"{output_path}archive{output_path[0]}"
        archive_cleanup_hours = int(os.environ.get('ARCHIVE_CLEAN_INTERVAL_H', 24))
        archive_max_age_days = int(os.environ.get('ARCHIVE_MAX_AGE_D', 60))
        if not validate_path(archive_path):
            raise FileNotFoundError(f"Error: Something is wrong with archive directory ({archive_path})")
        timer.enter(300, 1, path_cleanup_timer, (timer, archive_cleanup_hours, archive_path, archive_max_age_days))
    else:
        archive_path = ''

    # Runtime-relevant variables (most loaded from environment)
    read_wait = int(os.environ.get('SLEEPTIME', 5))
    verbose = (os.environ.get('VERBOSE', 'FALSE')).upper() != 'FALSE'
    delete_files = (os.environ.get('CLEAR_INPUT', 'FALSE')).upper() != 'FALSE'

    # Output the initial state to the log
    log.info('Starting filemover script with following settings:')
    log.info(f'- SMB USERNAME: {smb_username}')
    log.info(f'- SMB PASSWORD: {"<HIDDEN>" if smb_password != None else smb_password}')
    log.info(f'- INPUT PATH: {input_path}')
    log.info(f'- OUTPUT PATH: {output_path}')
    if archive:
        log.info('- ARCHIVING: ENABLED')
        log.info(f'- - PATH: {archive_path}')
        log.info(f'- - CLEAN INTERVAL: {archive_cleanup_hours} hours')
        log.info(f'- - MAX AGE: {archive_max_age_days} days')
    else:
        log.info('- ARCHIVING: DISABLED')
    log.info(f'- SLEEPTIME: {read_wait}')
    log.info(f'- VERBOSE: {verbose}')
    log.info(f'- DELETE FILES: {delete_files}')

    # Initialize ignore/memory
    file_ignore = {}

    log.info("Initialization complete - Starting loop..")
    timer.enter(0, 1, move_files_timer, (timer, input_path, output_path, archive_path, file_ignore,
                                         delete_files, read_wait))

    timer.run()
