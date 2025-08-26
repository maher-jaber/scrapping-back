FROM python:3.11-slim

# 1️⃣ Installer dépendances Linux + Chrome
RUN apt-get update && apt-get install -y \
    wget gnupg unzip curl xvfb \
    libnss3 libxss1 libasound2 libatk1.0-0 libcups2 libgtk-3-0 libx11-xcb1 libxcomposite1 libxcursor1 libxdamage1 libxrandr2 libgbm1 \
    && rm -rf /var/lib/apt/lists/*

# Installer Google Chrome
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google.list \
    && apt-get update && apt-get install -y google-chrome-stable

# Installer ChromeDriver
RUN CHROME_VERSION=$(google-chrome --version | awk '{print $3}' | cut -d '.' -f1) \
    && wget https://chromedriver.storage.googleapis.com/${CHROME_VERSION}.0.0/chromedriver_linux64.zip \
    && unzip chromedriver_linux64.zip -d /usr/local/bin/ \
    && rm chromedriver_linux64.zip

# 2️⃣ Copier le code
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# 3️⃣ Lancer FastAPI
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
