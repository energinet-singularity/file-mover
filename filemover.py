#Import dependencies
import os, sys, gzip, smbclient, sched, time

#Load/set variables
smb_username = os.environ.get('SMB_USERNAME')                                       #No default value
smb_password = os.environ.get('SMB_PASSWORD')                                       #No default value
smb_inputpath = os.environ.get('SMB_INPUTPATH','/input')                            #Default /input (assume it was mapped as volume)
smb_outputpath = os.environ.get('SMB_OUTPUTPATH','/output')                         #Default /output (assume it was mapped as volume)
read_wait = int(os.environ.get('SLEEPTIME', 5))                                     #Default to 5 seconds between each read
verbose = (os.environ.get('VERBOSE', 'FALSE')).upper() != 'FALSE'                   #Default to False (not writing extra logging messages)
print_file = (os.environ.get('MEGAVERBOSE', 'FALSE')).upper() != 'FALSE'            #Default to False (do NOT use this unless testing - it is extremely verbose!)
remove_input = (os.environ.get('CLEAR_INPUT', 'FALSE')).upper() != 'FALSE'          #Default to False (do not try to delete files)
use_memory = (os.environ.get('USE_MEMORY', 'TRUE')).upper() == 'TRUE'               #Default to True (remember which files have been handled and ignore them)
heartbeat_time = 60                                                                 #Heartbeat to show logline each x seconds
filemove_count = 0                                                                  #Global counter to present at heatbeat

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

#Initialize client and scheduler
if smb_username != None:
    smbclient.ClientConfig(username=smb_username, password=smb_password)
timer = sched.scheduler(time.time, time.sleep)

#Add a slash/backslash to end of filepaths if not there
if smb_inputpath[-1] != smb_inputpath[0]: smb_inputpath = f"{smb_inputpath}{smb_inputpath[0]}"
if smb_outputpath[-1] != smb_outputpath[0]: smb_outputpath = f"{smb_outputpath}{smb_outputpath[0]}"

#Load functions related to the input-side (smbclient does not allow refering nested objects for some reason)
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

#Load file_out module related to the output-side
if smbclient._os.is_remote_path(smb_outputpath):
    from smbclient import open_file as open_out
    from smbclient.path import isdir as isdir_out
else:
    from os.path import isdir as isdir_out
    open_out = open

#Function that does the actual moving
def move_files(input_path, output_path, dryrun=False, file_memory=None):
    #This function takes two paths as input and moves all files from input_path to output_path
    #Subfolders are currently ignored, files will be deleted from input folder based on the variable remove_input.
    #If 'dryrun' is set, nothing happens, it will only verbose expected actions.

    #Initialize variables
    filedict = {} 
    global filemove_count
    
    #Verify folders are found - handle errors as intelligent as possible.
    try:
        if not isdir_in(input_path): raise FileNotFoundError(f"'{input_path}' is not a valid directory.")
        if not isdir_out(output_path): raise FileNotFoundError(f"'{output_path}' is not a valid directory.")
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

    #Load file-memory at first run if used
    if file_memory is None and use_memory:
        file_memory = {input_path+fi:getmtime_in(input_path+fi) for fi in listdir_in(input_path) if isfile_in(input_path+fi)}

    #Read files into a dictionary
    for input_file_name in [fi for fi in listdir_in(input_path) if isfile_in(input_path+fi)]:
        input_file = input_path+input_file_name
        if not (input_file in file_memory.keys() and file_memory[input_file] == getmtime_in(input_file)):
            try:
                with open_in(input_file, "rb") as in_file:
                    filedict[input_file_name] = in_file.read()
                file_memory[input_file] = getmtime_in(input_file)
                if verbose or dryrun: print(f"Read file '{input_file}' from input folder.")
            except Exception as e:
                print(f"Error when trying to read file '{input_file}'. Skipping it for now.")
            else:
                if remove_input and not dryrun:
                    try:
                        remove_in(input_file)
                    except Exception as e:
                        print(f"Warning: Was not allowed to delete file '{input_file}'.")

    #Unpack gzip'd files
    keylist = list(filedict.keys())
    for output_file in keylist:
        if output_file[-3:] == '.gz':
            filedict[output_file[:-3]] = gzip.decompress(filedict.pop(output_file))

    #Write files from directory
    for output_file in filedict:
        if not dryrun: 
            with open_out(output_path + output_file, "wb") as out_file:
                out_file.write(filedict[output_file])
        if verbose or dryrun: print(f"Written file '{output_file}' to output folder.")
        if print_file: print(filedict[output_file])

    filemove_count += len(filedict)

    #Set another timer in 'read_wait' seconds to run again.
    if verbose: print(f'Timer set to {read_wait} seconds - going to sleep..')
    timer.enter(read_wait, 1, move_files, (input_path,output_path,dryrun,file_memory))

def log_alive():
    print('√v^√v^√v -- I have moved {} files until now..'.format(filemove_count))
    timer.enter(heartbeat_time, 1, log_alive)

#Main code
print("Initialization complete - Starting loop..")
timer.enter(0, 1, move_files, (smb_inputpath,smb_outputpath))
timer.enter(heartbeat_time, 1, log_alive)
timer.run()
