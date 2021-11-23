# file-mover
Small container that moves all files from /input to /output with a fixed interval. Directories can be mapped to volumes or mounted as SMB.

### Container prerequisites
The container needs to have /input and /output folders mapped - either by use of volume (-v someVolume:/output) or SMB_INPUTPATH/SMB_OUTPUTPATH environment variables (-e SMB_INPUTPATH="//myserver/path/"). In case SMB is used, remember to specify the SMB_USERNAME and SMB_PASSWORD parameters as well.

Example:
```sh
docker run file-mover -v someVolume:/output -e SMB_USERNAME="smith" -e SMB_USERNAME="secretpassword" -e SMB_INPUTPATH="//myserver/path/"
```

### Helm prerequisites

The default helm values/properties are set in a way that allows the helm chart to be installed and run without crashes, but it will not be useful. To spin up the environment with helm, make sure to set (or overwrite) the following values to something meaningful.

Example[^1]:
```yaml
folderMounts:
  input:
    enabled: false
  output:
    volume:
      persistentVolumeClaim:
        claimName: <my-pvc>
smbUserName: <username>
smbPassword: <password>
smbInputPath: <//this/is/a/path>
```

[^1]: Remember to set up the persistentVolumeClaim!

### Roadmap

- [x] Load first version to github
- [ ] Decide what to do next

See the [open issues](https://github.com/energinet-singularity/file-mover/issues) for a full list of proposed features (and known issues)
