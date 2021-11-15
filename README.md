# file-mover
Small container that moves all files from /input to /output with a fixed interval. Directories can be mapped to volumes or mounted as SMB.

### Container prerequisites
The container needs to have /input and /output folders mapped - either by use of volume (-v someVolume:/output) or SMB_INPUTPATH/SMB_OUTPUTPATH environment variables (-e SMB_INPUTPATH="//myserver/path/"). In case SMB is used, remember to specify the SMB_USERNAME and SMB_PASSWORD parameters as well.
This is an example of how to list things you need to use the software and how to install them.

```sh
docker run file-mover -v someVolume:/output -e SMB_USERNAME="smith" -e SMB_USERNAME="secretpassword" -e SMB_INPUTPATH="//myserver/path/"
```

### Helm prerequisites
Will come soon..

### Roadmap

- [x] Load first version to github
- [ ] Decide what to do next

See the [open issues](https://github.com/energinet-singularity/file-mover/issues) for a full list of proposed features (and known issues)
