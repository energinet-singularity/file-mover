# Select base-image
FROM python:3.10.0-slim-bullseye

# Load python requirements, install them and clean up.
COPY requirements.txt /
RUN pip3 install --upgrade pip && pip3 install -r requirements.txt --no-cache-dir && rm requirements.txt

# Copy required files into container
COPY filemover.py /

# Run the application
CMD ["python3", "-u", "filemover.py"]
