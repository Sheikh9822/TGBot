FROM python:3.10-slim

# Install aria2
RUN apt-get update && apt-get install -y aria2 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run aria2 RPC daemon and then start the bot
CMD aria2c --enable-rpc --rpc-listen-all=true --rpc-allow-origin-all=true --daemon && python main.py
