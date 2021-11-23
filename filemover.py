#Import dependencies
import os, sys, gzip, smbclient, sched, time, smbclient.path as smb_path #Not sure why .path is not directly accessible

#Load/set variables
smb_username = os.environ.get('SMB_USERNAME')                                       #No default value
smb_password = os.environ.get('SMB_PASSWORD')                                       #No default value
smb_inputpath = os.environ.get('SMB_INPUTPATH','/input')                            #Default /input (assume it was mapped as volume)
smb_outputpath = os.environ.get('SMB_OUTPUTPATH','/output')                         #Default /output (assume it was mapped as volume)
read_wait = int(os.environ.get('SLEEPTIME', 5))                                     #Default to 5 seconds between each read
verbose = (os.environ.get('VERBOSE', 'FALSE')).upper() != 'FALSE'                   #Default to False (not writing extra logging messages)
print_file = (os.environ.get('MEGAVERBOSE', 'FALSE')).upper() != 'FALSE'            #Default to False (do NOT use this unless testing - it is extremely verbose!)
remove_input = (os.environ.get('CLEAR_INPUT', 'TRUE')).upper() == 'TRUE'            #Default to True (move - not copy)
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
print('')

#Initialize client and scheduler
if smb_username != None:
    smbclient.ClientConfig(username=smb_username, password=smb_password)
timer = sched.scheduler(time.time, time.sleep)

#Function that does the actual moving
def move_files(input_path, output_path, dryrun=False):
    #This function takes two paths as input and moves all files from input_path to output_path
    #Subfolders are currently ignored, files will be deleted from input folder based on the variable remove_input.
    #If 'dryrun' is set, nothing happens, it will only verbose expected actions.

    #Initialize variables
    filedict = {} 
    global filemove_count

    #Load variables related to the input-side
    if input_path[0:2] == r'\\' or input_path[0:2] == '//':
        #Add a slash/backslash to end if not there
        if input_path[-1] != input_path[0]: input_path = f"{input_path}{input_path[0]}"

        #Import relevant parts with alias'
        from smbclient import listdir as listdir_in, remove as remove_in, open_file as open_in
        isdir_in = smb_path.isdir
    else:
        #Add a slash/backslash to end if not there
        input_path = os.path.join(input_path, '')

        #Import relevant parts with alias'
        from os import listdir as listdir_in, remove as remove_in
        from os.path import isdir as isdir_in
        open_in = open
    
    #Load variables related to the output-side
    if output_path[0:2] == r'\\' or output_path[0:2] == '//':
        #Add a slash/backslash to end if not there
        if output_path[-1] != output_path[0]: output_path = f"{output_path}{output_path[0]}"

        #Import relevant parts with alias'
        from smbclient import open_file as open_out
        isdir_out = smb_path.isdir
    else:
        #Add a slash/backslash to end if not there
        output_path = os.path.join(output_path, '')

        #Import relevant parts with alias'
        from os.path import isdir as isdir_out
        open_out = open
    
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

    #Read files into a dictionary
    for input_file in listdir_in(input_path):
        try:
            filedict[input_file] = open_in(input_path + input_file, "rb").read()
        except Exception as e:
            print("Error when trying to read file '{}'. Skipping it for now.".format(input_file))
        else:
            if remove_input and not dryrun: remove_in(input_path + input_file)
        if verbose or dryrun: print(f"Read file '{input_file}' from input folder.")

    #Unpack gzip'd files
    for output_file in filedict:
        if output_file[-3:] == '.gz':
            filedict[output_file[:-3]] = gzip.decompress(filedict.pop(output_file))

    #Write files from directory
    for output_file in filedict:
        if not dryrun: open_out(output_path + output_file, "wb").write(filedict[output_file])
        if verbose or dryrun: print(f"Written file '{output_file}' to output folder.")
        if print_file: print(filedict[output_file])

    filemove_count += len(filedict)

    #Set another timer in 'read_wait' seconds to run again.
    if verbose: print(f'Timer set to {read_wait} seconds - going to sleep..')
    timer.enter(read_wait, 1, move_files, (input_path,output_path,dryrun))

def log_alive():
    print('√v^√v^√v -- I have moved {} files until now..'.format(filemove_count))
    timer.enter(heartbeat_time, 1, log_alive)

#Main code
print("Initialization complete - Starting loop..")
timer.enter(0, 1, move_files, (smb_inputpath,smb_outputpath))
timer.enter(heartbeat_time, 1, log_alive)
timer.run()