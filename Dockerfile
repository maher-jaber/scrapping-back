FROM python:3.11-slim

# Installer dépendances Linux + utilitaires
RUN apt-get update && apt-get install -y \
    wget gnupg2 unzip curl ca-certificates xvfb \
    libnss3 libxss1 libasound2 libatk1.0-0 libcups2 libgtk-3-0 \
    libx11-xcb1 libxcomposite1 libxcursor1 libxdamage1 libxrandr2 libgbm1 \
    fonts-liberation libappindicator3-1 xdg-utils \
    --no-install-recommends && rm -rf /var/lib/apt/lists/*

# Installer Google Chrome stable depuis le dépôt officiel
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor > /usr/share/keyrings/google-linux-signing-key.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-linux-signing-key.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
       > /etc/apt/sources.list.d/google.list \
    && apt-get update && apt-get install -y google-chrome-stable --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Installer ChromeDriver compatible avec Chrome
RUN CHROME_VERSION=$(google-chrome --version | awk '{print $3}') \
    && CHROME_MAJOR=$(echo $CHROME_VERSION | cut -d '.' -f1) \
    && LATEST_DRIVER=$(wget -qO- "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$CHROME_MAJOR") \
    && wget -O /tmp/chromedriver.zip "https://chromedriver.storage.googleapis.com/${LATEST_DRIVER}/chromedriver_linux64.zip" \
    && unzip /tmp/chromedriver.zip -d /usr/local/bin/ \
    && chmod +x /usr/local/bin/chromedriver \
    && rm /tmp/chromedriver.zip

# Copier et installer l’app Python
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Variables d'environnement pour Selenium headless
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
ENV DISPLAY=:99

# Lancer FastAPI
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
