FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc g++ curl wget git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=100 -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

RUN python -m spacy download en_core_web_sm

COPY . .

# Fix potential Windows CRLF line ending issues in start.sh and make it executable
RUN sed -i 's/\r$//' start.sh && chmod +x start.sh

EXPOSE 8000

CMD ["./start.sh"]
