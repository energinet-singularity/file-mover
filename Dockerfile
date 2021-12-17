# LAYER 1 / Select base-image
FROM python:3.10.0-slim-bullseye

# LAYER 2 / Load python requirements, install them and clean up.
COPY app/requirements.txt /
RUN pip3 install --upgrade pip && pip3 install -r requirements.txt --no-cache-dir && rm requirements.txt

# LAYER 3 / Copy required files into container
COPY app/filemover.py /

# LAYER 4 / Run the application
CMD ["python3", "-u", "filemover.py"]
