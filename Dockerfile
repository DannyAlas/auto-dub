FROM ubuntu:20.04
# ENV DEBIAN_FRONTEND noninteractive
RUN apt-get update
RUN apt-get install -y python3.9
RUN apt-get install -y python3-pip
RUN python3.9 -m pip install --upgrade pip
RUN apt-get install -y ffmpeg

COPY . .

# RUN pip install -r requirements.txt
RUN --mount=type=cache,target=/root/.cache \
    pip install -r requirements.txt
# ENTRYPOINT [ "python3.9" ]
CMD ["python3.9", "-u", "main.py"]