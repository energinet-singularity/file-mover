# Import dependencies
import os
import sys
import gzip
import smbclient
import sched
import time

# Load/set variables
# - SMB Username and Password, if SMB is used
smb_username = os.environ.get('SMB_USERNAME')
smb_password = os.environ.get('SMB_PASSWORD')

# - Inputpath and outputpath. Taken from env. variables if specified
smb_inputpath = os.environ.get('SMB_INPUTPATH', '/input')
smb_outputpath = os.environ.get('SMB_OUTPUTPATH', '/output')

# - Runtime-relevant variables (most loaded from environment)
read_wait = int(os.environ.get('SLEEPTIME', 5))
verbose = (os.environ.get('VERBOSE', 'FALSE')).upper() != 'FALSE'
print_file = (os.environ.get('MEGAVERBOSE', 'FALSE')).upper() != 'FALSE'
remove_input = (os.environ.get('CLEAR_INPUT', 'FALSE')).upper() != 'FALSE'
use_memory = (os.environ.get('USE_MEMORY', 'TRUE')).upper() == 'TRUE'
heartbeat_time = 60
filemove_count = 0

# Output the current state to the log
print('Starting filemover script with following settings:')
print(f'- SMB_USERNAME: {smb_username}')
print(f'- SMB_PASSWORD: {"<HIDDEN>" if smb_password != None else smb_password}')
print('- SMB_INPUTPATH: {}'.format("<SMB SHARE>" if smb_inputpath[0:2] == r"\\" else smb_inputpath))
print('- SMB_OUTPUTPATH: {}'.format("<SMB SHARE>" if smb_outputpath[0:2] == r"\\" else smb_outputpath))
print(f'- SLEEPTIME: {read_wait}')
print(f'- VERBOSE: {verbose}')
print(f'- CLEAR_INPUT: {remove_input}')
print(f'- USE_MEMORY: {use_memory}')
print('')

# Initialize client and scheduler
if smb_username is not None:
    smbclient.ClientConfig(username=smb_username, password=smb_password)
timer = sched.scheduler(time.time, time.sleep)

# Add a slash/backslash to end of filepaths if not there
if smb_inputpath[-1] != smb_inputpath[0]:
    smb_inputpath = f"{smb_inputpath}{smb_inputpath[0]}"
if smb_outputpath[-1] != smb_outputpath[0]:
    smb_outputpath = f"{smb_outputpath}{smb_outputpath[0]}"

# Load functions related to the input-side (smbclient does not allow refering nested objects for some reason)
if smbclient._os.is_remote_path(smb_inputpath):
    from smbclient import (
        open_file as open_in,
        listdir as listdir_in,
        remove as remove_in)
    from smbclient.path import (
        isfile as isfile_in,
        isdir as isdir_in,
        getmtime as getmtime_in)
else:
    from os import (
        listdir as listdir_in,
        remove as remove_in)
    from os.path import (
        isfile as isfile_in,
        isdir as isdir_in,
        getmtime as getmtime_in)
    open_in = open

# Load file_out module related to the output-side
if smbclient._os.is_remote_path(smb_outputpath):
    from smbclient import open_file as open_out
    from smbclient.path import isdir as isdir_out
else:
    from os.path import isdir as isdir_out
    open_out = open

# Verify folders are found - handle errors as intelligent as possible.
try:
    if not isdir_in(smb_inputpath):
        raise FileNotFoundError(f"'{smb_inputpath}' is not a valid directory.")
    if not isdir_out(smb_outputpath):
        raise FileNotFoundError(f"'{smb_outputpath}' is not a valid directory.")
except FileNotFoundError as e:
    print(e)
    sys.exit(1)
except ValueError as e:
    print("SMB server not found. {}".format(str(e).split(":")[-1]))
    sys.exit(1)
except Exception as e:
    if type(e).__name__ == 'SMBAuthenticationError':
        print("Authentication error when connecting to fileshare.")
        print(e)
    elif type(e).__name__ == 'SMBException' or type(e).__name__ == 'NotFound':
        print(e)
    else:
        print("An unhandled exception of type {0} occurred. Arguments:\n{1!r}".format(type(e).__name__, e.args))
    sys.exit(1)

# Load file-memory
file_memory = {smb_inputpath+fi: getmtime_in(smb_inputpath+fi)
               for fi in listdir_in(smb_inputpath) if isfile_in(smb_inputpath+fi)}


# Function that unpacks binaries in case they are gzip'd
def unpack_binary(filedict):
    # Unpack gzip'd files
    keylist = list(filedict.keys())
    for output_file in keylist:
        if output_file[-3:] == '.gz':
            try:
                # Note - uses 'pop' to remove the entry from the dictionary
                filedict[output_file[:-3]] = gzip.decompress(filedict.pop(output_file))
            except Exception:
                print(f"Warning: Could not unpack '{output_file}' - skipping it.")
                try:
                    del filedict[output_file]
                except Exception:
                    pass
    return filedict


# Write files from directory
def read_files(input_path, file_memory):
    filedict = {}

    for input_file_name in [fi for fi in listdir_in(input_path) if isfile_in(input_path+fi)]:
        input_file = input_path+input_file_name
        if not (input_file in file_memory.keys() and file_memory[input_file] == getmtime_in(input_file)):
            try:
                with open_in(input_file, "rb") as in_file:
                    filedict[input_file_name] = in_file.read()
                file_memory[input_file] = getmtime_in(input_file)
                if verbose:
                    print(f"Read file '{input_file}' from input folder.")
            except Exception:
                print(f"Error when trying to read file '{input_file}'. Will retry next time.")
            else:
                if remove_input:
                    try:
                        remove_in(input_file)
                    except Exception:
                        print(f"Warning: Was not allowed to delete file '{input_file}'.")

    # Unpack binary files
    filedict = unpack_binary(filedict)

    # Return the dictionary
    return filedict


# Write files from directory
def write_file(filedict, output_path):
    for output_file in filedict:
        try:
            with open_out(output_path + output_file, "wb") as out_file:
                out_file.write(filedict[output_file])
            if verbose:
                print(f"Written file '{output_file}' to output folder ({output_path}).")
            if print_file:
                print(filedict[output_file])
        except Exception:
            print(f"Warning: Could not write file '{output_file}', skipping it.")


# Function that does the actual moving
def move_files(input_path, output_path, file_memory=None):
    # This function takes two paths as input and moves all files from input_path to output_path
    # Subfolders are currently ignored, files will be deleted from input folder based on the variable remove_input.

    global filemove_count

    # Read files into a dictionary
    filedict = read_files(input_path, file_memory)

    # Write files
    write_file(filedict, output_path)

    filemove_count += len(filedict)

    # Set another timer in 'read_wait' seconds to run again.
    if verbose:
        print(f'Timer set to {read_wait} seconds - going to sleep..')
    timer.enter(read_wait, 1, move_files, (input_path, output_path, file_memory))


def log_alive():
    print('√v^√v^√v -- I have moved {} files until now..'.format(filemove_count))
    timer.enter(heartbeat_time, 1, log_alive)


# Main code
print("Initialization complete - Starting loop..")
timer.enter(0, 1, move_files, (smb_inputpath, smb_outputpath, file_memory))
timer.enter(heartbeat_time, 1, log_alive)
timer.run()