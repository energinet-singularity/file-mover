# File-mover

A container that moves all files from one folder to another, either locally (via mounts) or network drives (SMB/Samba). The intent of the container is to move files from outside a docker-environment into a shared volume, but it can be used in other configurations as well.

## Description

This repo contains a python-script that will move files from an input-folder to an output-folder. By default the folders are '/input' and '/output' and can, for instance if running as a docker-container, be mapped to volumes. They can also be changed using environment variables - for instance to a windows network directory. The script is intended to be run as part of a container/kubernetes, so a Dockerfile is provided as well, as is a set of helm charts with a default configuration.

### Exposed environment variables:

| Name | Default value | Description |
|--|--|--|
|SMB_INPUTPATH|/input|The path where files are read from (local or SMB)[^1]|
|SMB_OUTPUTPATH|/output|The path where files are delivered to (local or SMB)[^1]|
|SMB_USERNAME|None|The username to use for reading/writing files in case SMB is used|
|SMB_PASSWORD|None|The password to use for reading/writing files in case SMB is used|
|ARCHIVE|FALSE|If not 'FALSE', archiving will be enabled (see [Archiving](#archiving))|
|ARCHIVE_CLEAN_INTERVAL_H|24|Interval in hours between each archive-folder scan (check for old files)|
|ARCHIVE_MAX_AGE_D|60|Maximum allowed age of archive-files (in days) before they are deleted|
|SLEEPTIME|5|Time between each scan of the input-folder, and thereby file-move|
|CLEAR_INPUT|FALSE|If not 'FALSE', files will be deleted after being read in 'input' folder|

[^1]: The variable name is misleading - both smb and local paths can be specified here (variable name will probably change in coming versions). SMB paths must be fully qualified - and remember to escape backslash and similar characters.

### Scanning the input folder

Every 'SLEEPTIME' seconds the 'SMB_INPUTPATH' folder is scanned for new files. All new files are loaded into memory and any file with the '.gz' extension is unpacked. The list of files and their read-time is stored (updated) in a variable, so any one file will not be read multiple times (unless it has changed). In case 'CLEAR_INPUT' is true, the script will try to delete the file after reading it.

### Writing files to the output folder

Files are written to the output path - if the file exists, it is overwritten. 

### Archiving

If 'ARCHIVE' is not FALSE, all files that are written to the output folder will be copied to an 'archive' subfolder. The file-name will be prepended with a timestamp (so files that are modified will be saved at each write-time). As part of the archiving feature is a built-in cleanup cycle that is run each 'ARCHIVE_CLEAN_INTERVAL_H' hours. All files found to be older than 'ARCHIVE_MAX_AGE_D' days will be removed from the archive-folder.

## Getting Started

The quickest way to have something running is through docker (see the section [Running container](#running-container)).

Feel free to either import the python-file as a lib or run it directly - or use HELM to spin it up as a pod in kubernetes. These methods are not documented and you will need the know-how yourself (the files have been prep'ed to our best ability though).

### Dependencies

The container will technically function as-is, but is not useful without configuring in- and output folders that somehow reach outside the confines of the container itself. This is not technically a dependency but will be covered in short in the following sections.
  
#### Python (if not run as part of the container)

The python script can probably run on any python 3.9+ version, but your best option will be to check the Dockerfile and use the same version as the container. Further requirements (python packages) can be found in the app/requirements.txt file.
  
The '[smbclient](https://github.com/jborean93/smbprotocol)' library by jborean93 is used for handling smb connections.

#### Docker

Built and tested on version 20.10.7.

The container should have /input and /output folders mapped - either by use of volume (-v someVolume:/output) or SMB_INPUTPATH/SMB_OUTPUTPATH environment variables (-e SMB_INPUTPATH="//myserver/path"). In case SMB is used, remember to specify the SMB_USERNAME and SMB_PASSWORD parameters as well.

Example:
```sh
docker run file-mover -v someVolume:/output -e SMB_USERNAME=smith -e SMB_USERNAME=secretpassword -e SMB_INPUTPATH="\\\\myserver\\path"
```

#### HELM (only relevant if using HELM for deployment)

Built and tested on version 3.7.0.

The default helm values/properties are set in a way that allows the helm chart to be installed and run without crashes, but it will not be useful. To spin up the environment with helm, make sure to set (or overwrite) the following values to something meaningful.

Example[^2]:

```yaml
folderMounts:
  input:
    enabled: false
  output:
    volume:
      persistentVolumeClaim:
        claimName: filedrop
smbUserName: foo
smbPassword: bar
smbInputPath: "//localhost/source"
````

[^2]: Remember to set up the persistentVolumeClaim!

### Running container

1. Clone the repo to a suitable place
````bash
git clone https://github.com/energinet-singularity/file-mover.git
````

2. Build the container and create a volume
````bash
docker build file-mover/ -t file-mover:latest
docker volume create filedrop
````

3. Start the container in docker (change paths and credentials to fit your environment)
````bash
docker run -v filedrop:/output -e SMB_USERNAME=foo -e SMB_PASSWORD=bar -e SMB_INPUTPATH=\\\\localhost\\source\\ -it --rm file-mover:latest
````

If you have a samba-share, provide the relevant credentials and path (slash is an escape-character, so it must be doubled!) - otherwise remove the three environment variables and map another volume using '-v sourcevolume:/input'.

The container will now be running interactively and you will be able to see the log output. By placing a file in the source share (in samba or volume depending on your specific configuration) you should soon after see the file appear in the output volume/folder.

To test, you can do a manual file-move (on the host-machine) to the volume (please verify volume-path is correct before trying this):
````bash
sudo cp testfile.txt.gz /var/lib/docker/volumes/filedrop/_data/
````

If the output path is a volume, you can use ls (on the host-machine) to verify the output (please verify volume-path is correct before trying this):
````bash
sudo ls /var/lib/docker/volumes/sourcevolume/_data/
````

## Help

See the [open issues](https://github.com/energinet-singularity/file-mover/issues) for a full list of proposed features (and known issues).
If you are facing unidentified issues with the application, please submit an issue or ask the authors.

## Version History

* 1.1.2:
    * First production-ready version
    <!---* See [commit change]() or See [release history]()--->

Older versions are not included in the README version history. For detauls on them, see the main-branch commit history, but beware: it was the early start and it was part of the learning curve, so it is not pretty. They are kept as to not disturb the integrity of the history.

## License

This project is licensed under the Apache-2.0 License - see the LICENSE and NOTICE file for details
