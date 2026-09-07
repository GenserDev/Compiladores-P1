FROM ubuntu:latest

RUN apt-get update && apt-get install -y \
    openjdk-17-jdk \
    python3-pip \
    python3-tk \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN pip install -r requirements.txt --break-system-packages
RUN ./generar_parser.sh

CMD ["python3", "Driver.py", "program/ejemplo.cps", "--tabla"]
