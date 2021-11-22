FROM python:3.10.0-slim-bullseye
RUN pip install --no-cache-dir smbprotocol 

#Include bash-script and make it executable
COPY filemover.py /

CMD ["python3", "-u", "filemover.py"]