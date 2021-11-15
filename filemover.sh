#!/bin/bash
#This script will move all files from /input to /output each 5 seconds
#Map /input and /output by using volume mount or by specifying the SMB_INPUT or SMB_OUTPUT environment variables
#To Do: Include optional way of getting password - i.e. from a file!

#Valid environment variables:
# - SMB_USER            Samba username                      : required if using SMB
# - SMB_PASS            Samba password                      : required if using SMB
# - SMB_INPUT           Input folder to mount               : must be defined if /input is not mapped to a volume
# - SMB_OUTPUT          Output folder to mount              : must be defined if /output is not mapped to a volume
# - SLEEPTIME           Delay between each scan in seconds. : will default to 5 seconds if not set

#Verify folders have been mapped - otherwise asume they need SMB mounting
if [ ! -d "/output" ] || [ ! -d "/input" ]; then

    echo "/input and/or /output was not mapped, trying to mount SMB share."

    #Verify username and password have been set
    if [ ${SMB_USER-notset} = 'notset' -o ${SMB_PASS-notset} = 'notset' ]; then
        echo "ERROR: Username and/or password was not set. Please use -e SMB_PASS=xxx and -e SMB_USER=yyy when initiating the container." 1>&2
        exit 1
    fi

    #Mount input dir if relevant
    if [ ! ${SMB_INPUT-notset} = 'notset' ] && [ ! -d "/input" ]; then
        mkdir /input
        echo "Trying to mount ${SMB_INPUT} to /input"
        mount -t cifs -o username=${SMB_USER},password=${SMB_PASS} "${SMB_INPUT}" /input
        if [ $? -ne 0 ]; then
            echo "Mount failed. Waiting 5 seconds and trying again."
            sleep 5
            mount -t cifs -o username=${SMB_USER},password=${SMB_PASS} "${SMB_INPUT}" /input
            if [ $? -ne 0 ]; then
                echo "ERROR: Mount of /input failed."
                exit 1
            fi
        fi
    fi

    #Mount output dir if relevant
    if [ ! ${SMB_OUTPUT-notset} = 'notset' ] && [ ! -d "/output" ]; then
        mkdir /output
        echo "Trying to mount ${SMB_OUTPUT} to /output"
        mount -t cifs -o username=${SMB_USER},password=${SMB_PASS} "${SMB_OUTPUT}" /output
        if [ $? -ne 0 ]; then
            echo "Mount failed. Waiting 5 seconds and trying again."
            sleep 5
            mount -t cifs -o username=${SMB_USER},password=${SMB_PASS} "${SMB_OUTPUT}" /output
            if [ $? -ne 0 ]; then
                echo "ERROR: Mount of /output failed." 1>&2
                exit 1
            fi            
        fi
    fi
fi

#One last check before moving on..
if [ ! -d "/output" ] || [ ! -d "/input" ]; then
    echo "ERROR: /output and/or /input has not been mounted. Please map using volume and/or -e SMB_INPUT=dirpath / -e SMB_OUTPUT=dirpath or check mounting error output." 1>&2
    exit 1
fi

#Start moving files (incl. subdirs) from /input to /output
ERR_COUNT=0
echo "Starting loop to check for files each ${SLEEPTIME-5} seconds."
until [ $ERR_COUNT -gt 4 ]; do
    #First unzip gz-files, if any
    if ls /input/*.gz 1> /dev/null 2>&1; then
        echo "Running gzip -d on following files:"
        ls /input/*.gz
        find /input/*.gz -exec gzip -d {} \;
    fi

    #If any files, move them to the output folder
    if [ "$(ls -A /input)" ]; then
        echo "Moving following files from /input to /output:"
        ls /input/
        mv /input/* /output/
        if [ $? -ne 0 ]; then
            ((ERR_COUNT=ERR_COUNT+1))
            echo "Move caused an error - count is now: $ERR_COUNT"
        else
            ERR_COUNT=0
        fi
    else
        echo "Nothing to do - going back to sleep.."
    fi
    sleep ${SLEEPTIME-5}
done

echo "ERROR: Could not move files. Retried 5 times and then gave up." 1>&2
exit 1